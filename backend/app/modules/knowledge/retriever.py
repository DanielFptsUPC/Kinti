"""Búsqueda híbrida sobre conocimiento publicado.

Combina búsqueda léxica (`tsvector` en español) y semántica (`pgvector`) mediante
Reciprocal Rank Fusion. La léxica acierta en términos institucionales exactos
—«SIS», «consentimiento»— y falla ante paráfrasis; la semántica hace lo
contrario. RRF las fusiona por *rango*, sin tener que calibrar dos escalas de
puntaje que no son comparables entre sí.

Los filtros de estado y vigencia se aplican **dentro de SQL**, antes de cualquier
ranking. No son un detalle de presentación: un documento retirado o en borrador
no puede llegar a una familia, y confiar eso al prompt sería confiarlo a la
suerte.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.assistant.ports import RetrievalFilters, RetrievedChunk

#: Constante de RRF. 60 es el valor del artículo original y funciona bien sin
#: ajuste cuando las listas son cortas.
RRF_K = 60


@dataclass(frozen=True)
class _Candidate:
    chunk_id: str
    document_id: str
    version_id: str
    document_title: str
    document_version: str
    section: str | None
    page: int | None
    content: str
    rank: int


#: Predicado de visibilidad. Se repite en ambas ramas de la búsqueda a propósito:
#: cualquier consulta que olvide aplicarlo devolvería material no aprobado.
_VISIBLE = """
    v.status = 'published'
    AND (v.valid_from IS NULL OR v.valid_from <= :now)
    AND (v.valid_until IS NULL OR v.valid_until >= :now)
    AND d.is_active = true
    AND d.audience = :audience
    AND d.language = :language
    -- El cast es necesario: sin él, asyncpg no puede inferir el tipo de un
    -- parámetro que llega como NULL y falla con AmbiguousParameterError.
    AND (CAST(:category AS text) IS NULL OR d.category = CAST(:category AS text))
"""

# La consulta léxica usa OR entre raíces, no AND.
#
# `plainto_tsquery` exige que **todas** las palabras aparezcan, y eso descarta
# cualquier paráfrasis: «qué papeles llevo» no casaría con un documento que dice
# «debes llevar tu documento», pese a compartir la raíz «llev».
#
# Convertir la pregunta a su propio `tsvector` descarta las palabras vacías y
# deja sólo raíces significativas; unirlas con `|` permite coincidencia parcial.
# Una pregunta que sólo contiene palabras vacías («y eso cómo es») produce una
# consulta vacía y no recupera nada — que es justo lo que debe pasar.
_LEXICAL_SQL = f"""
WITH q AS (
    SELECT array_to_string(
        tsvector_to_array(to_tsvector('spanish', :query)), ' | '
    ) AS terms
)
SELECT c.id::text AS chunk_id, c.document_id::text, c.version_id::text,
       d.title, v.version, c.section, c.page, c.content,
       row_number() OVER (
           ORDER BY ts_rank_cd(
               c.content_tsv, to_tsquery('spanish', (SELECT terms FROM q))
           ) DESC
       ) AS rank
FROM knowledge_chunks c
JOIN knowledge_document_versions v ON v.id = c.version_id
JOIN knowledge_documents d ON d.id = c.document_id
WHERE {_VISIBLE}
  AND (SELECT terms FROM q) <> ''
  AND c.content_tsv @@ to_tsquery('spanish', (SELECT terms FROM q))
ORDER BY rank
LIMIT :limit
"""

_SEMANTIC_SQL = f"""
SELECT c.id::text AS chunk_id, c.document_id::text, c.version_id::text,
       d.title, v.version, c.section, c.page, c.content,
       row_number() OVER (ORDER BY c.embedding <=> CAST(:embedding AS vector)) AS rank
FROM knowledge_chunks c
JOIN knowledge_document_versions v ON v.id = c.version_id
JOIN knowledge_documents d ON d.id = c.document_id
WHERE {_VISIBLE}
  AND c.embedding IS NOT NULL
ORDER BY rank
LIMIT :limit
"""


class PostgresKnowledgeRetriever:
    """Recuperador sobre PostgreSQL con `pgvector`.

    Funciona igual en el contenedor local (`pgvector/pgvector:pg16`) y en
    Supabase: usa sólo SQL estándar y la extensión, ninguna función propietaria.
    """

    def __init__(self, session: AsyncSession, *, require_lexical_support: bool = True) -> None:
        self._session = session
        # Umbral del §12.2, expresado como exigencia de anclaje léxico.
        self._require_lexical = require_lexical_support

    async def search(
        self,
        query: str,
        embedding: list[float],
        filters: RetrievalFilters,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        params = {
            "query": query,
            "now": filters.now or utcnow(),
            "audience": filters.audience,
            "language": filters.language,
            "category": filters.category,
            # Se recupera de más en cada rama para que la fusión tenga con qué
            # trabajar; el recorte a `top_k` ocurre al final.
            "limit": max(top_k * 4, 20),
        }

        lexical = await self._run(_LEXICAL_SQL, params)
        semantic = await self._run(
            _SEMANTIC_SQL, {**params, "embedding": _vector_literal(embedding)}
        )

        return _fuse(lexical, semantic, top_k, require_lexical=self._require_lexical)

    async def _run(self, sql: str, params: dict) -> list[_Candidate]:
        result = await self._session.execute(text(sql), params)
        return [
            _Candidate(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                version_id=row.version_id,
                document_title=row.title,
                document_version=row.version,
                section=row.section,
                page=row.page,
                content=row.content,
                rank=int(row.rank),
            )
            for row in result
        ]


def _vector_literal(embedding: list[float]) -> str:
    """pgvector acepta el literal textual `[a,b,c]`."""
    return "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"


def _fuse(
    lexical: list[_Candidate],
    semantic: list[_Candidate],
    top_k: int,
    *,
    require_lexical: bool = True,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion: score = Σ 1/(k + rango) sobre las listas.

    Con `require_lexical`, un fragmento sólo es citable si las palabras de la
    pregunta aparecen realmente en él (raíces en español). Es el umbral que exige
    el §12.2, expresado de la forma más explicable posible.

    Sin él, la rama semántica siempre devuelve `top_k` resultados ordenados por
    distancia — incluso para «y eso cómo es», que no pregunta nada concreto — y
    el sistema acabaría citando un fragmento sin relación. Preferimos abstenernos.

    Se puede desactivar cuando el proveedor de embeddings esté validado y se
    quiera recuperar paráfrasis sin raíces compartidas.
    """
    from uuid import UUID

    lexical_ids = {c.chunk_id for c in lexical}
    scores: dict[str, float] = {}
    seen: dict[str, _Candidate] = {}

    for candidates in (lexical, semantic):
        for candidate in candidates:
            if require_lexical and candidate.chunk_id not in lexical_ids:
                continue
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + 1.0 / (
                RRF_K + candidate.rank
            )
            seen.setdefault(candidate.chunk_id, candidate)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

    return [
        RetrievedChunk(
            chunk_id=UUID(chunk_id),
            document_id=UUID(seen[chunk_id].document_id),
            version_id=UUID(seen[chunk_id].version_id),
            document_title=seen[chunk_id].document_title,
            document_version=seen[chunk_id].document_version,
            section=seen[chunk_id].section,
            page=seen[chunk_id].page,
            content=seen[chunk_id].content,
            score=score,
        )
        for chunk_id, score in ordered
    ]

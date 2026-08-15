"""Corpus institucional real (`app/modules/knowledge/content.py`) y su siembra.

Dos niveles de comprobación:

- **Estáticas, sin base de datos.** Reglas de redacción que no dependen de
  Postgres: nada de estacionamiento (el caso `amb-02` del set de evaluación
  depende de que ese tema *no* tenga evidencia), nada de vocabulario clínico
  prohibido, slugs únicos.
- **Contra Postgres real.** Que `seed_knowledge` deje todo publicado y
  recuperable, y que sea idempotente: correrlo dos veces no debe duplicar nada
  ni fallar la segunda vez.
"""

import re

from sqlalchemy import func, select

from app.modules.assistant.evaluation import FORBIDDEN_IN_ANSWERS
from app.modules.assistant.fakes import _summarize
from app.modules.assistant.providers import build_embeddings, reset_for_testing
from app.modules.knowledge import ingestion
from app.modules.knowledge.content import DOCUMENTS
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocumentVersion
from app.seed_knowledge import seed_knowledge

# ------------------------------------------------------------------ estáticas


def test_every_document_has_a_unique_slug():
    slugs = [doc.slug for doc in DOCUMENTS]
    assert len(slugs) == len(set(slugs))


def test_every_document_targets_caregivers():
    # El orquestador filtra por `audience="caregiver"` de forma fija (§4 de la
    # Fase 3): un documento con otra audiencia sería contenido muerto, nunca
    # recuperable desde el chat de cuidadores.
    assert all(doc.audience == "caregiver" for doc in DOCUMENTS)


def test_no_document_mentions_parking():
    """El caso `amb-02` de evaluación exige abstención ante el estacionamiento.

    Si algún documento lo mencionara aunque fuera de pasada, ese caso dejaría de
    probar una abstención real: probaría, sin querer, una respuesta que resultó
    correcta por casualidad.
    """
    corpus = " ".join(doc.text.lower() for doc in DOCUMENTS)
    assert "estacionamiento" not in corpus
    assert "parqueo" not in corpus


def test_no_document_uses_forbidden_clinical_language():
    corpus = " ".join(doc.text.lower() for doc in DOCUMENTS)
    for term in FORBIDDEN_IN_ANSWERS:
        assert term not in corpus, f"«{term}» no debe aparecer en contenido para cuidadores"


def test_every_section_opens_with_a_self_contained_sentence():
    """El proveedor determinístico cita literalmente la primera oración del
    fragmento mejor rankeado: si no responde por sí sola, ninguna respuesta lo
    hará hasta que haya un modelo real.
    """
    for doc in DOCUMENTS:
        for section in doc.text.split("\n# ")[1:] or [doc.text]:
            body = section.split("\n", 1)[1] if "\n" in section else ""
            first_sentence = body.strip().split(". ", 1)[0]
            assert len(first_sentence) >= 40, (
                f"«{doc.slug}»: una sección abre con una oración demasiado corta "
                "para responder algo por sí sola"
            )


def test_no_fragment_truncates_mid_abbreviation():
    """`_summarize` corta en la primera coincidencia de `[.!?]\\s+`.

    «7:00 a. m.» se leyó una vez como fin de oración en «a.» y la respuesta del
    horario del laboratorio quedó cortada en producción. La solución fue de
    contenido —horario de 24 horas, sin abreviatura—, así que esta prueba fija
    esa forma en vez de tocar el separador de oraciones, que es compartido con
    el resto del modelo determinístico.
    """
    for doc in DOCUMENTS:
        for chunk in ingestion.chunk_text(doc.text):
            summary = _summarize(chunk.content)
            assert not re.search(r"\b[a-záéíóú]\.$", summary), (
                f"«{doc.slug}» / «{chunk.section}»: "
                f"la primera oración se corta en una abreviatura -> {summary!r}"
            )


# --------------------------------------------------------------- contra Postgres


async def test_seeding_publishes_every_document(session, seeded):
    reset_for_testing()
    results = await seed_knowledge(session)

    assert len(results) == len(DOCUMENTS)
    assert all(outcome == "publicado" for _, outcome in results)

    published = await session.scalars(
        select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.status == "published")
    )
    assert len(list(published)) == len(DOCUMENTS)

    count = await session.scalar(select(func.count()).select_from(KnowledgeChunk))
    assert count and count > 0
    reset_for_testing()


async def test_seeding_twice_does_not_duplicate_or_fail(session, seeded):
    reset_for_testing()
    await seed_knowledge(session)

    before = await session.scalar(select(func.count()).select_from(KnowledgeChunk))

    second = await seed_knowledge(session)
    after = await session.scalar(select(func.count()).select_from(KnowledgeChunk))

    assert after == before
    assert all(outcome == "vigente" for _, outcome in second)
    reset_for_testing()


async def test_reindex_re_embeds_published_content_without_changing_the_checksum(
    session, seeded
):
    """El motivo de existir de `--reindex`: cambiar de proveedor de embeddings
    no cambia el texto del documento, así que la deduplicación por checksum por
    sí sola dejaría los vectores viejos para siempre. `force=True` lo evita.
    """
    reset_for_testing()
    await seed_knowledge(session)

    before = await session.scalars(
        select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.status == "published")
    )
    before_ids = {v.id for v in before}
    before_chunks = await session.scalars(select(KnowledgeChunk.id))
    before_chunk_ids = set(before_chunks)

    results = await seed_knowledge(session, force=True)

    assert all(outcome == "reindexado" for _, outcome in results)

    after = await session.scalars(
        select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.status == "published")
    )
    after_rows = list(after)
    # Misma versión, no una nueva: `--reindex` reincrusta en el sitio.
    assert {v.id for v in after_rows} == before_ids
    assert len(after_rows) == len(DOCUMENTS)

    after_chunk_ids = set(await session.scalars(select(KnowledgeChunk.id)))
    # `process_version` reemplaza los fragmentos: los IDs de los chunks
    # cambian aunque el contenido embebido sea el mismo texto.
    assert after_chunk_ids != before_chunk_ids
    assert len(after_chunk_ids) == len(before_chunk_ids)
    reset_for_testing()


async def test_seeding_requires_the_care_team_account_first(session):
    """Sin `python -m app.seed` antes, no hay quién firme la publicación."""
    import pytest

    with pytest.raises(RuntimeError):
        await seed_knowledge(session)


async def test_seeded_corpus_is_retrievable_with_the_real_embedding_provider(session, seeded):
    """`seed_knowledge` usa `build_embeddings()`, no un doble de prueba fijo.

    Confirma que el proveedor resuelto por configuración —el mismo que usará el
    despliegue— produce vectores de la dimensión que la columna espera.
    """
    reset_for_testing()
    await seed_knowledge(session)

    from app.modules.assistant.ports import RetrievalFilters
    from app.modules.knowledge.retriever import PostgresKnowledgeRetriever

    embeddings = build_embeddings()
    vector = (await embeddings.embed(["¿qué documentos debo llevar?"]))[0]
    chunks = await PostgresKnowledgeRetriever(session).search(
        "¿qué documentos debo llevar?", vector, RetrievalFilters(), top_k=5
    )
    assert chunks
    reset_for_testing()

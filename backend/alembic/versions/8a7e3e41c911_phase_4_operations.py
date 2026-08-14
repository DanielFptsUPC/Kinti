"""phase 4 operational visibility

Revision ID: 8a7e3e41c911
Revises: 44d4a1febf6a
Create Date: 2026-08-13 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8a7e3e41c911"
down_revision: str | None = "44d4a1febf6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ambulatory_capacity_slots",
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_places", sa.Integer(), nullable=False),
        sa.Column("expected_session_minutes", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service", "starts_at", name="uq_capacity_service_start"),
    )
    op.create_index(
        op.f("ix_ambulatory_capacity_slots_service"),
        "ambulatory_capacity_slots",
        ["service"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ambulatory_capacity_slots_starts_at"),
        "ambulatory_capacity_slots",
        ["starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ambulatory_capacity_slots_starts_at"),
        table_name="ambulatory_capacity_slots",
    )
    op.drop_index(
        op.f("ix_ambulatory_capacity_slots_service"),
        table_name="ambulatory_capacity_slots",
    )
    op.drop_table("ambulatory_capacity_slots")


"""evidencias: texto_extraido y detalle; estado inicial de entregas = borrador

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12 16:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('evidencias', schema=None) as batch_op:
        batch_op.add_column(sa.Column('texto_extraido', sa.Text(), nullable=True))
        # server_default para poder añadir la columna NOT NULL a filas existentes.
        batch_op.add_column(
            sa.Column('detalle', sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
    # El default de `entregas.estado` vive solo en el modelo (default de Python):
    # no hay server_default que cambiar. Las filas antiguas "pendiente" pasan a "borrador".
    op.execute("UPDATE entregas SET estado = 'borrador' WHERE estado = 'pendiente'")


def downgrade() -> None:
    op.execute("UPDATE entregas SET estado = 'pendiente' WHERE estado = 'borrador'")
    with op.batch_alter_table('evidencias', schema=None) as batch_op:
        batch_op.drop_column('detalle')
        batch_op.drop_column('texto_extraido')

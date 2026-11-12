"""evaluaciones: trazabilidad de IA y revision docente; tabla ajustes_criterio

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12 18:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('evaluaciones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('error', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('version_prompt', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('modelo_escalamiento', sa.String(length=100), nullable=True))
        # server_default para poder anadir la columna NOT NULL a filas existentes.
        batch_op.add_column(
            sa.Column('requiere_revision', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column('advertencias', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('uso', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column('costo_usd_estimado', sa.Numeric(precision=10, scale=6), nullable=True)
        )
    op.create_table(
        'ajustes_criterio',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('evaluacion_id', sa.Integer(), nullable=False),
        sa.Column('criterio_id', sa.String(length=100), nullable=False),
        sa.Column('nivel_anterior', sa.String(length=200), nullable=False),
        sa.Column('nivel_nuevo', sa.String(length=200), nullable=False),
        sa.Column('justificacion', sa.Text(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['evaluacion_id'], ['evaluaciones.id'], name=op.f('fk_ajustes_criterio_evaluacion_id_evaluaciones')),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_ajustes_criterio_usuario_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ajustes_criterio')),
    )


def downgrade() -> None:
    op.drop_table('ajustes_criterio')
    with op.batch_alter_table('evaluaciones', schema=None) as batch_op:
        batch_op.drop_column('costo_usd_estimado')
        batch_op.drop_column('uso')
        batch_op.drop_column('advertencias')
        batch_op.drop_column('requiere_revision')
        batch_op.drop_column('modelo_escalamiento')
        batch_op.drop_column('version_prompt')
        batch_op.drop_column('error')

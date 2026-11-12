"""esquema inicial v1

Revision ID: 0001
Revises:
Create Date: 2026-11-12 11:06:21.142827
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('laboratorios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cohorte', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=50), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('objetivos', sa.Text(), nullable=False),
    sa.Column('temas', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_laboratorios')),
    sa.UniqueConstraint('codigo', name=op.f('uq_laboratorios_codigo'))
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('correo', sa.String(length=254), nullable=False),
    sa.Column('hash_contrasena', sa.String(length=255), nullable=False),
    sa.Column('rol', sa.String(length=20), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuarios'))
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_correo'), ['correo'], unique=True)

    op.create_table('auditoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('accion', sa.String(length=60), nullable=False),
    sa.Column('entidad', sa.String(length=60), nullable=False),
    sa.Column('entidad_id', sa.Integer(), nullable=True),
    sa.Column('detalle', sa.JSON(), nullable=True),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_auditoria_usuario_id_usuarios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auditoria'))
    )
    op.create_table('rubricas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('laboratorio_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['laboratorio_id'], ['laboratorios.id'], name=op.f('fk_rubricas_laboratorio_id_laboratorios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rubricas')),
    sa.UniqueConstraint('laboratorio_id', name=op.f('uq_rubricas_laboratorio_id'))
    )
    op.create_table('rubrica_versiones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rubrica_id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('contenido', sa.JSON(), nullable=False),
    sa.Column('valida', sa.Boolean(), nullable=False),
    sa.Column('inconsistencias', sa.JSON(), nullable=False),
    sa.Column('creado_por', sa.Integer(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], name=op.f('fk_rubrica_versiones_creado_por_usuarios')),
    sa.ForeignKeyConstraint(['rubrica_id'], ['rubricas.id'], name=op.f('fk_rubrica_versiones_rubrica_id_rubricas')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rubrica_versiones')),
    sa.UniqueConstraint('rubrica_id', 'numero', name=op.f('uq_rubrica_versiones_rubrica_id_numero'))
    )
    op.create_table('entregas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('estudiante_id', sa.Integer(), nullable=False),
    sa.Column('laboratorio_id', sa.Integer(), nullable=False),
    sa.Column('rubrica_version_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['estudiante_id'], ['usuarios.id'], name=op.f('fk_entregas_estudiante_id_usuarios')),
    sa.ForeignKeyConstraint(['laboratorio_id'], ['laboratorios.id'], name=op.f('fk_entregas_laboratorio_id_laboratorios')),
    sa.ForeignKeyConstraint(['rubrica_version_id'], ['rubrica_versiones.id'], name=op.f('fk_entregas_rubrica_version_id_rubrica_versiones')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_entregas')),
    sa.UniqueConstraint('estudiante_id', 'laboratorio_id', name=op.f('uq_entregas_estudiante_id_laboratorio_id'))
    )
    op.create_table('evaluaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entrega_id', sa.Integer(), nullable=False),
    sa.Column('rubrica_version_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('proveedor', sa.String(length=50), nullable=True),
    sa.Column('modelo', sa.String(length=100), nullable=True),
    sa.Column('parametros', sa.JSON(), nullable=True),
    sa.Column('resultado_ia', sa.JSON(), nullable=True),
    sa.Column('verificacion', sa.JSON(), nullable=True),
    sa.Column('nota_preliminar', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('nota_final', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('revisado_por', sa.Integer(), nullable=True),
    sa.Column('aprobado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('publicado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id'], name=op.f('fk_evaluaciones_entrega_id_entregas')),
    sa.ForeignKeyConstraint(['revisado_por'], ['usuarios.id'], name=op.f('fk_evaluaciones_revisado_por_usuarios')),
    sa.ForeignKeyConstraint(['rubrica_version_id'], ['rubrica_versiones.id'], name=op.f('fk_evaluaciones_rubrica_version_id_rubrica_versiones')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evaluaciones'))
    )
    op.create_table('evidencias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entrega_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('ruta_archivo', sa.String(length=500), nullable=True),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('nombre_original', sa.String(length=255), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('tamano_bytes', sa.Integer(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id'], name=op.f('fk_evidencias_entrega_id_entregas')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidencias'))
    )


def downgrade() -> None:
    op.drop_table('evidencias')
    op.drop_table('evaluaciones')
    op.drop_table('entregas')
    op.drop_table('rubrica_versiones')
    op.drop_table('rubricas')
    op.drop_table('auditoria')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_correo'))

    op.drop_table('usuarios')
    op.drop_table('laboratorios')
    # ### end Alembic commands ###
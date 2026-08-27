"""create tenants and rls workspace documents

Revision ID: b501870a5cd9
Revises: ecb939469dd0
Create Date: 2026-08-27 07:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b501870a5cd9'
down_revision: Union[str, None] = 'ecb939469dd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)

    # 2. Add tenant_id foreign key column to users table
    op.add_column('users', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    op.create_foreign_key(
        'fk_users_tenant_id_tenants',
        'users', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )

    # 3. Create workspace_documents table
    op.create_table(
        'workspace_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workspace_documents_id'), 'workspace_documents', ['id'], unique=False)
    op.create_index(op.f('ix_workspace_documents_tenant_id'), 'workspace_documents', ['tenant_id'], unique=False)
    op.create_index('ix_documents_tenant_created', 'workspace_documents', ['tenant_id', 'created_at'], unique=False)

    # 4. Enable PostgreSQL Kernel-Level Row Level Security (RLS)
    op.execute("ALTER TABLE workspace_documents ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workspace_documents FORCE ROW LEVEL SECURITY;")

    # 5. Create Tenant Isolation Policy
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON workspace_documents
        FOR ALL
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        );
    """)


def downgrade() -> None:
    # Drop policy and disable RLS
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON workspace_documents;")
    op.execute("ALTER TABLE workspace_documents DISABLE ROW LEVEL SECURITY;")

    # Drop tables & indexes
    op.drop_index('ix_documents_tenant_created', table_name='workspace_documents')
    op.drop_index(op.f('ix_workspace_documents_tenant_id'), table_name='workspace_documents')
    op.drop_index(op.f('ix_workspace_documents_id'), table_name='workspace_documents')
    op.drop_table('workspace_documents')
    
    op.drop_constraint('fk_users_tenant_id_tenants', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_column('users', 'tenant_id')
    
    op.drop_index(op.f('ix_tenants_slug'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_id'), table_name='tenants')
    op.drop_table('tenants')
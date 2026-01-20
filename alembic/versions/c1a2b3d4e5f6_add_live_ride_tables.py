"""add ride_activities and user_locations tables

Revision ID: c1a2b3d4e5f6
Revises: 36f7d1999ca3
Create Date: 2026-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = '0f47d9f8bde9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ride_activities table
    op.create_table('ride_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ride_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('message', sa.String(500), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('checkpoint_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata_json', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['checkpoint_id'], ['ride_checkpoints.id'], ),
        sa.ForeignKeyConstraint(['ride_id'], ['rides.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ride_activities_activity_type'), 'ride_activities', ['activity_type'], unique=False)
    op.create_index(op.f('ix_ride_activities_created_at'), 'ride_activities', ['created_at'], unique=False)
    op.create_index(op.f('ix_ride_activities_id'), 'ride_activities', ['id'], unique=False)
    op.create_index(op.f('ix_ride_activities_ride_id'), 'ride_activities', ['ride_id'], unique=False)
    op.create_index(op.f('ix_ride_activities_user_id'), 'ride_activities', ['user_id'], unique=False)

    # Create user_locations table
    op.create_table('user_locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ride_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['ride_id'], ['rides.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ride_id', 'user_id', 'recorded_at', name='unique_ride_user_location_time')
    )
    op.create_index(op.f('ix_user_locations_id'), 'user_locations', ['id'], unique=False)
    op.create_index(op.f('ix_user_locations_recorded_at'), 'user_locations', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_user_locations_ride_id'), 'user_locations', ['ride_id'], unique=False)
    op.create_index(op.f('ix_user_locations_user_id'), 'user_locations', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop user_locations table
    op.drop_index(op.f('ix_user_locations_user_id'), table_name='user_locations')
    op.drop_index(op.f('ix_user_locations_ride_id'), table_name='user_locations')
    op.drop_index(op.f('ix_user_locations_recorded_at'), table_name='user_locations')
    op.drop_index(op.f('ix_user_locations_id'), table_name='user_locations')
    op.drop_table('user_locations')

    # Drop ride_activities table
    op.drop_index(op.f('ix_ride_activities_user_id'), table_name='ride_activities')
    op.drop_index(op.f('ix_ride_activities_ride_id'), table_name='ride_activities')
    op.drop_index(op.f('ix_ride_activities_id'), table_name='ride_activities')
    op.drop_index(op.f('ix_ride_activities_created_at'), table_name='ride_activities')
    op.drop_index(op.f('ix_ride_activities_activity_type'), table_name='ride_activities')
    op.drop_table('ride_activities')

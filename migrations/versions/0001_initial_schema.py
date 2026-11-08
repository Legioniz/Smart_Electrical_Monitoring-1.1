"""Initial MySQL schema for Smart Meter Explorer V2.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-01
"""
from alembic import op
from sme.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

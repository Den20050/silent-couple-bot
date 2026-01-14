"""Add bot_messages table

Revision ID: add_bot_messages
Revises: remove_common_chat_id_from_pairs
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_bot_messages'
down_revision: Union[str, None] = 'add_last_surprise_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bot_messages table."""
    op.create_table(
        'bot_messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_bot_messages_sent_at', 'bot_messages', ['sent_at'], unique=False)
    op.create_index('idx_bot_messages_chat_message', 'bot_messages', ['chat_id', 'message_id'], unique=False)
    op.create_index(op.f('ix_bot_messages_chat_id'), 'bot_messages', ['chat_id'], unique=False)


def downgrade() -> None:
    """Drop bot_messages table."""
    op.drop_index(op.f('ix_bot_messages_chat_id'), table_name='bot_messages')
    op.drop_index('idx_bot_messages_chat_message', table_name='bot_messages')
    op.drop_index('idx_bot_messages_sent_at', table_name='bot_messages')
    op.drop_table('bot_messages')

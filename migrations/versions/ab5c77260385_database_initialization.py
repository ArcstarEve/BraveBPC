"""Database Initialization

Revision ID: ab5c77260385
Revises: 
Create Date: 2020-05-12 16:43:56.384043

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab5c77260385'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=128), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('refresh_token', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('request',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request', sa.String(length=4096), nullable=True),
    sa.Column('create_time', sa.DateTime(), nullable=True),
    sa.Column('char_id', sa.Integer(), nullable=True),
    sa.Column('complete_time', sa.DateTime(), nullable=True),
    sa.Column('completed_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['char_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_request_create_time'), 'request', ['create_time'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_request_create_time'), table_name='request')
    op.drop_table('request')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')
    # ### end Alembic commands ###

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"], unique=True)

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.UniqueConstraint("asset_id", "ts", name="uq_price_history_asset_ts"),
    )
    op.create_index("ix_price_history_asset_id", "price_history", ["asset_id"]) 
    op.create_index("ix_price_history_ts", "price_history", ["ts"]) 

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("change_pct", sa.Numeric(9, 4), nullable=False),
    )
    op.create_index("ix_alerts_asset_id", "alerts", ["asset_id"]) 
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"]) 


def downgrade() -> None:
    op.drop_index("ix_alerts_triggered_at", table_name="alerts")
    op.drop_index("ix_alerts_asset_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_price_history_ts", table_name="price_history")
    op.drop_index("ix_price_history_asset_id", table_name="price_history")
    op.drop_table("price_history")

    op.drop_index("ix_assets_symbol", table_name="assets")
    op.drop_table("assets")


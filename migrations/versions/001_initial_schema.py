"""Initial schema: jobs, tasks, workers, queue_metrics

Revision ID: 001
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable UUID generation ────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("input_data", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="jobs_status_check",
        ),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_submitted_at", "jobs", [sa.text("submitted_at DESC")])

    # ── workers ───────────────────────────────────────────────────────────────
    # Created before tasks so tasks.worker_id FK works
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("hostname", sa.String(256), nullable=False, unique=True),
        sa.Column("worker_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="IDLE"),
        sa.Column("current_task_id", postgresql.UUID(), nullable=True),
        sa.Column("last_heartbeat", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("registered_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("tasks_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("status IN ('IDLE','BUSY','DEAD')", name="workers_status_check"),
    )
    op.create_index("idx_workers_last_heartbeat", "workers", ["last_heartbeat"])
    op.create_index("idx_workers_type", "workers", ["worker_type"])

    # ── tasks ─────────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("job_id", postgresql.UUID(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("depends_on", postgresql.ARRAY(postgresql.UUID()), nullable=False, server_default="'{}'"),
        sa.Column("enqueued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("worker_id", postgresql.UUID(), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("stream_message_id", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','ENQUEUED','RUNNING','COMPLETED','FAILED','SKIPPED')",
            name="tasks_status_check",
        ),
    )
    op.create_index("idx_tasks_job_id", "tasks", ["job_id"])
    op.create_index("idx_tasks_stage_name", "tasks", ["stage_name"])
    # Partial index — only indexes PENDING rows, dramatically speeds up scheduler query
    op.create_index(
        "idx_tasks_pending",
        "tasks",
        ["status"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # ── queue_metrics ─────────────────────────────────────────────────────────
    op.create_table(
        "queue_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("captured_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("stream_name", sa.String(128), nullable=False),
        sa.Column("pending_count", sa.Integer(), nullable=False),
        sa.Column("consumer_group", sa.String(128), nullable=False),
        sa.Column("active_consumers", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_queue_metrics_captured_at", "queue_metrics", [sa.text("captured_at DESC")])
    op.create_index("idx_queue_metrics_stream", "queue_metrics", ["stream_name", sa.text("captured_at DESC")])


def downgrade() -> None:
    op.drop_table("queue_metrics")
    op.drop_table("tasks")
    op.drop_table("workers")
    op.drop_table("jobs")

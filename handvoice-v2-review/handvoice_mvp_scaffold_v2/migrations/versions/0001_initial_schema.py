"""Initial HandVoice schema baseline.

Revision ID: 0001
Revises:
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = {
    "operators",
    "participants",
    "assessment_sessions",
    "task_instances",
    "recordings",
    "features",
    "events",
    "audit_events",
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names()) - {"alembic_version"}
    if existing:
        if TABLES.issubset(existing):
            return
        raise RuntimeError(
            "Refusing to baseline a partial schema; back up the database and reconcile it first"
        )

    op.create_table(
        "operators",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("study_id", sa.String(length=100), nullable=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_operators_study_id", "operators", ["study_id"])
    op.create_index("ix_operators_key_hash", "operators", ["key_hash"], unique=True)

    op.create_table(
        "participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.String(length=100), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_reference"),
    )
    op.create_index("ix_participants_study_id", "participants", ["study_id"])

    op.create_table(
        "assessment_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version", sa.String(length=50), nullable=False),
        sa.Column("sequence_id", sa.String(length=10), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_id",
            "session_number",
            name="uq_participant_session_number",
        ),
    )
    op.create_index(
        "ix_assessment_sessions_participant_id",
        "assessment_sessions",
        ["participant_id"],
    )

    op.create_table(
        "task_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("task_code", sa.String(length=10), nullable=False),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("hand", sa.String(length=10), nullable=True),
        sa.Column("speech_task", sa.String(length=50), nullable=True),
        sa.Column("repetition", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "task_code",
            "repetition",
            name="uq_session_task_repetition",
        ),
    )
    op.create_index("ix_task_instances_session_id", "task_instances", ["session_id"])
    op.create_index("ix_task_instances_task_code", "task_instances", ["task_code"])

    op.create_table(
        "recordings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_instance_id", sa.Uuid(), nullable=False),
        sa.Column("object_uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("video_fps", sa.Float(), nullable=True),
        sa.Column("audio_sample_rate", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_instance_id", name="uq_recording_task_instance"),
    )
    op.create_index("ix_recordings_sha256", "recordings", ["sha256"])

    op.create_table(
        "features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_instance_id", sa.Uuid(), nullable=False),
        sa.Column("modality", sa.String(length=30), nullable=False),
        sa.Column("feature_name", sa.String(length=150), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("window_start_ms", sa.Integer(), nullable=True),
        sa.Column("window_end_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("algorithm_version", sa.String(length=100), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_features_task_instance_id", "features", ["task_instance_id"])
    op.create_index("ix_features_modality", "features", ["modality"])
    op.create_index("ix_features_feature_name", "features", ["feature_name"])

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_instance_id", sa.Uuid(), nullable=False),
        sa.Column("modality", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_task_instance_id", "events", ["task_instance_id"])
    op.create_index("ix_events_modality", "events", ["modality"])
    op.create_index("ix_events_event_type", "events", ["event_type"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_modality", table_name="events")
    op.drop_index("ix_events_task_instance_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_features_feature_name", table_name="features")
    op.drop_index("ix_features_modality", table_name="features")
    op.drop_index("ix_features_task_instance_id", table_name="features")
    op.drop_table("features")
    op.drop_index("ix_recordings_sha256", table_name="recordings")
    op.drop_table("recordings")
    op.drop_index("ix_task_instances_task_code", table_name="task_instances")
    op.drop_index("ix_task_instances_session_id", table_name="task_instances")
    op.drop_table("task_instances")
    op.drop_index(
        "ix_assessment_sessions_participant_id",
        table_name="assessment_sessions",
    )
    op.drop_table("assessment_sessions")
    op.drop_index("ix_participants_study_id", table_name="participants")
    op.drop_table("participants")
    op.drop_index("ix_operators_key_hash", table_name="operators")
    op.drop_index("ix_operators_study_id", table_name="operators")
    op.drop_table("operators")

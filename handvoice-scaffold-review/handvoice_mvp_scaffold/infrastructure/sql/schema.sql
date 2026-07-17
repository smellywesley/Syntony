-- Human-readable PostgreSQL schema reference.
-- SQLAlchemy models remain the source of truth for this scaffold.

CREATE TABLE participants (
    id UUID PRIMARY KEY,
    study_id VARCHAR(100) NOT NULL,
    external_reference VARCHAR(255) UNIQUE,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE assessment_sessions (
    id UUID PRIMARY KEY,
    participant_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    protocol_version VARCHAR(50) NOT NULL,
    sequence_id VARCHAR(10) NOT NULL,
    session_number INTEGER NOT NULL,
    context_json JSONB NOT NULL,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

CREATE TABLE task_instances (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    task_code VARCHAR(10) NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    condition VARCHAR(20) NOT NULL,
    hand VARCHAR(10),
    speech_task VARCHAR(50),
    repetition INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    manifest_json JSONB NOT NULL
);

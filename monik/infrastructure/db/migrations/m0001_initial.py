"""Начальная схема Monik.

Хранится только состояние, необходимое для recovery, дедупликации,
уведомлений, диагностики и аудита (``30_DATABASE_SCHEMA.md`` §2).
Полный поток quotes не сохраняется (``30_DATABASE_SCHEMA.md`` §44).

Наименование сущностей соответствует решению D-1: результат Level 1 —
``opportunities`` (``#V``), единица подтверждения — ``level2_jobs`` (``#K``).
Промежуточный ``Candidate`` не персистится.

Все денежные значения и raw amounts хранятся как ``TEXT`` (см.
``monik.infrastructure.db.types``), timestamps — ISO-8601 UTC.
Секреты в схеме отсутствуют (``30_DATABASE_SCHEMA.md`` §58).
"""

from __future__ import annotations

from monik.infrastructure.db.migrations.base import Migration

__all__ = ["MIGRATION"]

_STATEMENTS: tuple[str, ...] = (
    # --- метаданные и последовательности --------------------------------
    """
    CREATE TABLE app_metadata (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE id_sequences (
        name       TEXT PRIMARY KEY,
        next_value INTEGER NOT NULL
    )
    """,
    # --- Level 1 циклы ---------------------------------------------------
    """
    CREATE TABLE scans (
        scan_id         TEXT PRIMARY KEY,
        status          TEXT NOT NULL,
        scope_json      TEXT NOT NULL,
        statistics_json TEXT NOT NULL,
        started_at      TEXT NOT NULL,
        finished_at     TEXT
    )
    """,
    "CREATE INDEX idx_scans_started_at ON scans (started_at)",
    "CREATE INDEX idx_scans_status ON scans (status)",
    # --- Opportunity (сущность Level 1) ----------------------------------
    """
    CREATE TABLE opportunities (
        opportunity_id         TEXT PRIMARY KEY,
        v_id                   TEXT NOT NULL UNIQUE,
        scan_id                TEXT REFERENCES scans (scan_id) ON DELETE SET NULL,
        status                 TEXT NOT NULL,
        fingerprint            TEXT NOT NULL,
        network_id             TEXT NOT NULL,
        input_token            TEXT NOT NULL,
        intermediate_token     TEXT NOT NULL,
        output_token           TEXT NOT NULL,
        buy_provider_id        TEXT NOT NULL,
        sell_provider_id       TEXT NOT NULL,
        buy_route_json         TEXT NOT NULL,
        sell_route_json        TEXT NOT NULL,
        buy_route_fingerprint  TEXT NOT NULL,
        sell_route_fingerprint TEXT NOT NULL,
        detected_at            TEXT NOT NULL,
        expires_at             TEXT NOT NULL,
        updated_at             TEXT,
        confirmed_at           TEXT,
        formula_version        INTEGER
    )
    """,
    "CREATE INDEX idx_opportunities_fingerprint ON opportunities (fingerprint, detected_at)",
    "CREATE INDEX idx_opportunities_status ON opportunities (status)",
    "CREATE INDEX idx_opportunities_detected_at ON opportunities (detected_at)",
    "CREATE INDEX idx_opportunities_expires_at ON opportunities (expires_at)",
    """
    CREATE TABLE opportunity_amounts (
        opportunity_id            TEXT NOT NULL
                                  REFERENCES opportunities (opportunity_id) ON DELETE CASCADE,
        raw_input_amount          TEXT NOT NULL,
        input_decimals            INTEGER NOT NULL,
        preliminary_buy_output    TEXT NOT NULL,
        preliminary_sell_output   TEXT NOT NULL,
        preliminary_net_profit    TEXT,
        preliminary_net_roi       TEXT,
        preliminary_status        TEXT NOT NULL,
        confirmation_status       TEXT,
        PRIMARY KEY (opportunity_id, raw_input_amount)
    )
    """,
    # --- Level 2 ----------------------------------------------------------
    """
    CREATE TABLE level2_jobs (
        k_id            TEXT PRIMARY KEY,
        opportunity_id  TEXT NOT NULL UNIQUE
                        REFERENCES opportunities (opportunity_id) ON DELETE RESTRICT,
        status          TEXT NOT NULL,
        priority        TEXT NOT NULL,
        attempt_count   INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        expires_at      TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_level2_jobs_status ON level2_jobs (status, priority, created_at)",
    "CREATE INDEX idx_level2_jobs_expires_at ON level2_jobs (expires_at)",
    """
    CREATE TABLE level2_attempts (
        attempt_id  TEXT PRIMARY KEY,
        k_id        TEXT NOT NULL REFERENCES level2_jobs (k_id) ON DELETE CASCADE,
        revision    INTEGER NOT NULL,
        status      TEXT NOT NULL,
        started_at  TEXT NOT NULL,
        finished_at TEXT,
        error_code  TEXT,
        UNIQUE (k_id, revision)
    )
    """,
    "CREATE INDEX idx_level2_attempts_job ON level2_attempts (k_id, revision)",
    """
    CREATE TABLE level2_amount_results (
        result_id            TEXT PRIMARY KEY,
        attempt_id           TEXT NOT NULL
                             REFERENCES level2_attempts (attempt_id) ON DELETE CASCADE,
        raw_input_amount     TEXT NOT NULL,
        input_decimals       INTEGER NOT NULL,
        status               TEXT NOT NULL,
        confirmation_status  TEXT NOT NULL,
        current_buy_output   TEXT,
        current_sell_output  TEXT,
        gross_profit         TEXT,
        gross_roi            TEXT,
        total_fees           TEXT,
        gas_cost             TEXT,
        other_costs          TEXT,
        rebates              TEXT,
        net_profit           TEXT,
        net_roi              TEXT,
        threshold            TEXT,
        threshold_passed     INTEGER,
        calculation_status   TEXT,
        formula_version      INTEGER,
        fee_snapshot_json    TEXT,
        gas_snapshot_json    TEXT,
        calculation_json     TEXT,
        rejection_reason     TEXT,
        created_at           TEXT NOT NULL,
        UNIQUE (attempt_id, raw_input_amount)
    )
    """,
    # --- уведомления ------------------------------------------------------
    """
    CREATE TABLE notifications (
        notification_id  TEXT PRIMARY KEY,
        opportunity_id   TEXT NOT NULL
                         REFERENCES opportunities (opportunity_id) ON DELETE RESTRICT,
        destination_id   TEXT NOT NULL,
        destination_kind TEXT NOT NULL,
        mode             TEXT NOT NULL,
        status           TEXT NOT NULL,
        sequence         INTEGER NOT NULL,
        attempt_count    INTEGER NOT NULL DEFAULT 0,
        fingerprint      TEXT NOT NULL,
        message_text     TEXT,
        details_text     TEXT,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        next_attempt_at  TEXT,
        UNIQUE (opportunity_id, destination_id)
    )
    """,
    "CREATE INDEX idx_notifications_order ON notifications (created_at, sequence)",
    "CREATE INDEX idx_notifications_status ON notifications (status, next_attempt_at)",
    "CREATE INDEX idx_notifications_opportunity ON notifications (opportunity_id)",
    """
    CREATE TABLE notification_attempts (
        attempt_id          TEXT PRIMARY KEY,
        notification_id     TEXT NOT NULL
                            REFERENCES notifications (notification_id) ON DELETE CASCADE,
        attempt_number      INTEGER NOT NULL,
        status              TEXT NOT NULL,
        started_at          TEXT NOT NULL,
        finished_at         TEXT,
        error_code          TEXT,
        external_message_id TEXT,
        UNIQUE (notification_id, attempt_number)
    )
    """,
    # --- комиссии, gas, capability ---------------------------------------
    """
    CREATE TABLE fee_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        provider_id TEXT NOT NULL,
        network_id  TEXT NOT NULL,
        operation   TEXT NOT NULL,
        version     INTEGER NOT NULL,
        created_at  TEXT NOT NULL,
        expires_at  TEXT
    )
    """,
    "CREATE INDEX idx_fee_snapshots_lookup ON fee_snapshots "
    "(provider_id, network_id, operation, created_at)",
    """
    CREATE TABLE fee_records (
        record_id   TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES fee_snapshots (snapshot_id) ON DELETE CASCADE,
        fee_type    TEXT NOT NULL,
        status      TEXT NOT NULL,
        amount      TEXT,
        currency    TEXT,
        inclusion   TEXT NOT NULL,
        source      TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        expires_at  TEXT,
        description TEXT
    )
    """,
    "CREATE INDEX idx_fee_records_snapshot ON fee_records (snapshot_id)",
    """
    CREATE TABLE gas_snapshots (
        snapshot_id      TEXT PRIMARY KEY,
        network_id       TEXT NOT NULL,
        status           TEXT NOT NULL,
        gas_units        INTEGER,
        wei_per_gas      TEXT,
        base_fee_wei     TEXT,
        priority_fee_wei TEXT,
        native_token     TEXT,
        cost_native      TEXT,
        source           TEXT NOT NULL,
        observed_at      TEXT NOT NULL,
        expires_at       TEXT
    )
    """,
    "CREATE INDEX idx_gas_snapshots_network ON gas_snapshots (network_id, observed_at)",
    """
    CREATE TABLE capabilities (
        capability_key       TEXT PRIMARY KEY,
        provider_id          TEXT NOT NULL,
        network_id           TEXT NOT NULL,
        operation            TEXT NOT NULL,
        token                TEXT,
        status               TEXT NOT NULL,
        checked_at           TEXT NOT NULL,
        expires_at           TEXT,
        source               TEXT NOT NULL,
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        detail               TEXT
    )
    """,
    "CREATE INDEX idx_capabilities_lookup ON capabilities (provider_id, network_id, operation)",
    "CREATE INDEX idx_capabilities_status ON capabilities (status, expires_at)",
    # --- планировщик ------------------------------------------------------
    """
    CREATE TABLE scheduler_tasks (
        task_id       TEXT PRIMARY KEY,
        mode          TEXT NOT NULL,
        enabled       INTEGER NOT NULL DEFAULT 1,
        schedule_json TEXT NOT NULL,
        last_run_at   TEXT,
        next_run_at   TEXT,
        updated_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_scheduler_tasks_next_run ON scheduler_tasks (enabled, next_run_at)",
    """
    CREATE TABLE scheduler_executions (
        execution_id  TEXT PRIMARY KEY,
        task_id       TEXT NOT NULL REFERENCES scheduler_tasks (task_id) ON DELETE CASCADE,
        status        TEXT NOT NULL,
        scheduled_for TEXT NOT NULL,
        started_at    TEXT,
        finished_at   TEXT,
        error_code    TEXT
    )
    """,
    "CREATE INDEX idx_scheduler_executions_task ON scheduler_executions (task_id, scheduled_for)",
    # --- аудит переходов состояний ---------------------------------------
    """
    CREATE TABLE state_transitions (
        transition_id  TEXT PRIMARY KEY,
        entity_type    TEXT NOT NULL,
        entity_id      TEXT NOT NULL,
        from_state     TEXT,
        to_state       TEXT NOT NULL,
        reason         TEXT NOT NULL,
        correlation_id TEXT,
        occurred_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_state_transitions_entity ON state_transitions "
    "(entity_type, entity_id, occurred_at)",
)

MIGRATION = Migration(version=1, name="initial_schema", statements=_STATEMENTS)

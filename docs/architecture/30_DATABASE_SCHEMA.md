# MONIK — DATABASE SCHEMA

## 1. Назначение

Этот документ определяет обязательные требования к структуре и использованию SQLite database в Monik.

Database используется для хранения persistent state, необходимого для:

- восстановления после restart;
- Level 2 Jobs;
- confirmed opportunities;
- notifications;
- scans;
- scheduler state;
- fee snapshots;
- diagnostics;
- operational history.

Database не является источником live market data.

---

## 2. Главный принцип

SQLite должна хранить только тот state, который действительно необходим для persistence, recovery, diagnostics и audit.

Не сохранять каждый промежуточный quote только ради истории.

---

## 3. Database Technology

На текущем этапе используется:

**SQLite.**

Database должна поддерживать:

- transactions;
- foreign keys;
- indexes;
- migrations;
- integrity checks.

---

## 4. Database Boundary

Business logic не должна выполнять raw SQL напрямую.

Взаимодействие происходит через Repository layer.

---

## 5. Repository Pattern

Repository отвечает за:

- SQL;
- mapping database records → domain models;
- mapping domain models → database records;
- transactions;
- persistence-specific errors.

---

## 6. Domain Independence

Domain models не должны зависеть от SQLite-specific types.

---

## 7. Database Models

Database models могут отличаться от domain models.

Repository выполняет mapping между ними.

---

## 8. Primary Keys

Каждая persistent entity должна иметь deterministic primary key.

Для operational entities рекомендуется использовать UUID/string ID или другой explicit identifier.

---

## 9. IDs

Минимально persistent entities должны иметь идентификаторы:

- scan_id;
- candidate_id;
- job_id;
- opportunity_id;
- notification_id;
- execution_id, если persistence необходима.

---

## 10. Timestamps

Все persistent timestamps должны быть timezone-aware по semantic meaning.

Предпочтительно хранить UTC.

---

## 11. Timestamp Fields

Для lifecycle entities могут использоваться:

- created_at;
- updated_at;
- started_at;
- finished_at;
- expires_at.

Использовать только необходимые поля.

---

## 12. No Local Time Storage

Database не должна зависеть от локального timezone VPS.

---

## 13. Schema Version

Database должна иметь versioned migration state.

---

## 14. Migration Table

Необходимо иметь отдельный механизм определения применённых migrations.

Например:

`schema_migrations`

или equivalent.

---

## 15. Migration Identity

Каждая migration должна иметь уникальный version/identifier.

---

## 16. Migration Order

Migrations применяются последовательно.

Нельзя пропускать обязательную migration.

---

## 17. Migration Atomicity

Migration должна быть atomic насколько это позволяет SQLite и используемый migration mechanism.

---

## 18. Migration Failure

Если migration failed:

application не должен продолжать запуск с предположительно несовместимой schema.

---

## 19. Migration Testing

Каждая migration должна тестироваться отдельно.

---

## 20. Rollback

Destructive migrations не должны предполагать automatic rollback без explicit tested strategy.

---

## 21. Foreign Keys

SQLite foreign keys должны быть включены.

---

## 22. Referential Integrity

Relations между persistent entities должны использовать foreign key constraints там, где это необходимо.

---

## 23. Cascade Deletes

CASCADE DELETE использовать только если удаление child entity действительно безопасно.

---

## 24. No Accidental Cascades

Нельзя использовать cascade deletion для критических financial/audit records без explicit policy.

---

## 25. Opportunities

Confirmed opportunities должны сохраняться persistent state.

Минимально:

- opportunity_id;
- job_id;
- network;
- route/fingerprint;
- input amount;
- output amount;
- total costs;
- net profit;
- profit percentage;
- status;
- created_at;
- confirmed_at;
- calculation version.

---

## 26. Opportunity Immutability

После CONFIRMED critical financial values не должны изменяться произвольно.

Если необходим correction:

использовать explicit correction/audit mechanism.

---

## 27. Opportunity Status

Минимально:

- CONFIRMED;
- NOTIFIED;
- NOTIFIED_PARTIAL;
- NOTIFIED_FAILED;
- EXPIRED.

---

## 28. Candidate Persistence

Candidate persistence допускается для:

- deduplication;
- Level 2 recovery;
- diagnostics;
- operational history.

Не хранить candidate бесконечно.

---

## 29. Candidate Fields

Минимально:

- candidate_id;
- fingerprint;
- network;
- route;
- amount;
- provider pair;
- created_at;
- expires_at;
- status.

---

## 30. Candidate Retention

Candidate retention должна иметь explicit policy.

Expired/rejected candidates могут удаляться после retention period.

---

## 31. Level 2 Jobs

Level 2 Jobs должны сохраняться для recovery после restart.

Минимально:

- job_id;
- candidate_id;
- status;
- priority;
- route;
- amount;
- provider pair;
- created_at;
- updated_at;
- expires_at;
- attempt_count.

---

## 32. Job Recovery

После restart Jobs со статусом RUNNING должны быть обработаны согласно recovery policy.

Нельзя считать RUNNING job автоматически CONFIRMED.

---

## 33. Job State

State transitions должны проходить через explicit application logic.

---

## 34. Job History

При необходимости можно хранить state transition history.

---

## 35. Job Attempts

Retry attempts могут храниться:

- как counter;
- или отдельной execution table.

Выбор зависит от diagnostics requirements.

---

## 36. Execution Records

Для critical operations может использоваться отдельная таблица executions.

Она может содержать:

- execution_id;
- job_id;
- provider;
- operation;
- started_at;
- finished_at;
- status;
- error_code;
- latency.

---

## 37. Notification Persistence

Notifications должны сохраняться для:

- retry;
- deduplication;
- recovery;
- delivery tracking.

---

## 38. Notification Fields

Минимально:

- notification_id;
- opportunity_id;
- destination_id;
- status;
- created_at;
- updated_at;
- attempt_count.

---

## 39. Notification Attempts

При необходимости отдельная таблица может хранить:

- attempt_id;
- notification_id;
- started_at;
- finished_at;
- status;
- error_code;
- external_message_id.

---

## 40. Notification Idempotency

Database должна позволять определить, была ли конкретная opportunity уже отправлена конкретному destination.

---

## 41. Unique Notification Constraint

Для соответствующей notification policy рекомендуется использовать unique constraint на logical notification identity.

Например:

opportunity + destination.

---

## 42. Scan Persistence

Level 1 scans могут сохраняться для diagnostics.

Минимально:

- scan_id;
- started_at;
- finished_at;
- status;
- scope;
- statistics.

---

## 43. Scan Statistics

Statistics могут содержать:

- providers checked;
- networks checked;
- quotes requested;
- quotes successful;
- quotes failed;
- candidates created.

---

## 44. No Raw Quote History

Не сохранять каждый raw quote в database без explicit requirement.

---

## 45. Quote Persistence

Quote persistence допускается только если она нужна для:

- audit;
- debugging;
- testing;
- recovery.

И должна иметь retention policy.

---

## 46. Raw Provider Data

Raw provider responses не должны храниться постоянно без explicit reason.

---

## 47. Fee Snapshots

Fee snapshots могут сохраняться persistent.

Минимально:

- snapshot_id;
- provider;
- network;
- timestamp;
- version;
- validity.

---

## 48. Fee Records

Fee snapshot может иметь связанные fee records.

Минимально:

- fee type;
- amount;
- currency/token;
- included_in_quote;
- source.

---

## 49. Fee Retention

История fee snapshots должна иметь retention policy.

---

## 50. Capability Persistence

Capability state может сохраняться для:

- startup recovery;
- diagnostics;
- change detection.

---

## 51. Capability Freshness

Persisted capability не должна автоматически считаться актуальной после длительного периода.

Dynamic capability должна пройти freshness policy.

---

## 52. Health Persistence

Health state не обязан сохраняться полностью.

Persistent health history допускается только если она нужна для diagnostics/audit.

---

## 53. Scheduler Persistence

Scheduler state может сохраняться для:

- last execution;
- next execution;
- task state;
- recovery.

---

## 54. Scheduler Jobs

Persistent scheduler tasks должны иметь deterministic identity.

---

## 55. Configuration Persistence

Validated production secrets не должны храниться в SQLite.

---

## 56. Runtime Configuration

Если runtime configuration сохраняется:

она должна быть безопасной и не содержать secrets.

---

## 57. Database Metadata

Database может содержать metadata:

- application version;
- schema version;
- environment;
- migration state.

---

## 58. Secrets Prohibition

Database никогда не должна хранить:

- API keys;
- Telegram bot tokens;
- passwords;
- private keys;
- authentication headers.

---

## 59. Sensitive Data

Sensitive runtime data должна храниться только при explicit requirement и с соответствующей protection.

---

## 60. Indexes

Критические query paths должны иметь необходимые indexes.

---

## 61. Opportunity Indexes

Рекомендуемые indexes:

- status;
- created_at;
- confirmed_at;
- fingerprint.

---

## 62. Job Indexes

Рекомендуемые indexes:

- status;
- priority;
- expires_at;
- candidate_id.

---

## 63. Notification Indexes

Рекомендуемые indexes:

- status;
- opportunity_id;
- destination_id;
- created_at.

---

## 64. Scan Indexes

Рекомендуемые indexes:

- started_at;
- status.

---

## 65. Fingerprint Index

Candidate fingerprint должен иметь index.

Если policy требует уникальности:

использовать UNIQUE constraint.

---

## 66. Query Performance

Repositories должны избегать:

- full-table scans на больших operational tables;
- N+1 queries;
- unnecessary repeated queries.

---

## 67. Pagination

Для больших history queries использовать pagination/limited queries.

---

## 68. Retention

Каждая историческая table должна иметь retention policy.

---

## 69. No Infinite Growth

Database не должна бесконтрольно расти из-за:

- logs;
- failed jobs;
- candidates;
- notifications;
- fee snapshots;
- scan history.

---

## 70. Cleanup

Cleanup должен выполняться controlled Scheduler task.

---

## 71. Cleanup Safety

Cleanup не должен удалять:

- active Jobs;
- confirmed Opportunities;
- pending Notifications;

если это нарушает recovery policy.

---

## 72. Cleanup Transactions

Cleanup операций должны использовать transactions.

---

## 73. Database Transactions

Критические multi-step writes должны использовать transactions.

---

## 74. Atomic Confirmation

Создание CONFIRMED Opportunity и связанного critical state должно быть atomic насколько это необходимо для consistency.

---

## 75. Notification Separation

Notification delivery не должна происходить внутри database transaction.

---

## 76. Transaction Scope

Transactions должны быть короткими.

Не удерживать database transaction во время external HTTP request.

---

## 77. External Requests

Никогда не держать SQLite transaction открытой во время:

- provider API request;
- Telegram API request;
- long-running external operation.

---

## 78. Concurrency

SQLite usage должен учитывать concurrency limitations.

---

## 79. WAL

Для production SQLite рекомендуется рассмотреть WAL mode, если он соответствует deployment workload.

---

## 80. Busy Timeout

Database access должен иметь controlled busy/lock timeout.

---

## 81. Database Lock

Transient database lock может retry ограниченное количество раз.

---

## 82. Integrity Check

Production startup может выполнять database integrity check согласно deployment policy.

---

## 83. Corruption

Если database corruption обнаружена:

application должен перейти в safe failure state и не продолжать запись вслепую.

---

## 84. Backup

Database должна регулярно backup-иться.

---

## 85. Backup Consistency

Backup должен быть создан способом, обеспечивающим consistent SQLite state.

---

## 86. Restore

Должен существовать tested restore procedure.

---

## 87. Restore Testing

Backup restore необходимо периодически тестировать.

---

## 88. Database Permissions

Database file должен иметь минимально необходимые filesystem permissions.

---

## 89. Backup Permissions

Backup files должны иметь такие же или более строгие permissions.

---

## 90. Database Path

Database path должен быть configuration-driven.

Не hard-code production filesystem path внутри business logic.

---

## 91. Test Database

Tests используют отдельную database.

---

## 92. No Production Database in Tests

Tests никогда не должны подключаться к production database.

---

## 93. Test Isolation

Каждый integration test suite должен иметь возможность очистить/пересоздать test database.

---

## 94. Migration Tests

CI должен проверять:

- создание database с нуля;
- применение всех migrations;
- корректную schema;
- constraints;
- indexes.

---

## 95. Repository Tests

Каждый repository должен иметь tests для:

- create;
- read;
- update;
- delete, если разрешено;
- filtering;
- pagination;
- transactions;
- constraints;
- errors.

---

## 96. State Transition Tests

Database repositories должны корректно защищать critical state transitions.

---

## 97. Duplicate Protection

Database должна использовать constraints там, где duplicate entity может привести к financial/notification error.

---

## 98. No Duplicate Confirmation

Одна logical opportunity не должна создавать uncontrolled duplicate CONFIRMED records.

---

## 99. No Duplicate Notification

Одна logical notification не должна бесконтрольно отправляться несколько раз одному destination.

---

## 100. Critical Invariants

Database Schema никогда не должна позволять:

1. хранить production secrets;

2. использовать raw SQL из business logic;

3. подтверждать opportunity через database write без application validation;

4. хранить бесконечную историю без retention;

5. удалять active Jobs cleanup task;

6. удалять confirmed Opportunities обычным cleanup;

7. держать transactions открытыми во время external requests;

8. использовать production database в tests;

9. считать stale persisted capability актуальной без freshness policy;

10. терять critical state при обычном application restart;

11. создавать uncontrolled duplicate Opportunities;

12. создавать uncontrolled duplicate Notifications;

13. выполнять destructive migration без tested recovery strategy;

14. обходить repository boundary;

15. считать backup автоматически надёжным без restore verification.

---

## 101. Главный принцип

Database должна обеспечить:

**надёжное и минимально необходимое persistent storage для recovery, consistency, deduplication, notifications, Jobs, opportunities и diagnostics без превращения SQLite в источник live market data или место хранения secrets.**

Database хранит:

**состояние, которое необходимо сохранить.**

Provider APIs предоставляют:

**актуальные внешние данные.**

Domain logic определяет:

**как эти данные интерпретировать.**

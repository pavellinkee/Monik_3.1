# MONIK — DATABASE

## 1. Назначение

Database subsystem отвечает за локальное persistent storage состояния Monik.

На текущем этапе используется:

SQLite.

Database должна обеспечивать:

- persistence;
- recovery;
- deduplication;
- audit;
- diagnostics;
- хранение подтверждённых opportunities;
- хранение необходимого runtime state.

Database не должна использоваться как источник live market data.

---

## 2. Главный принцип

SQLite хранит состояние и историю, необходимую приложению.

Она не заменяет:

- Aggregator APIs;
- Fee System;
- Resource Manager;
- Token Registry;
- Capability Registry;
- свежие quotes.

---

## 3. SQLite

Основная database engine:

SQLite.

Database должна работать локально внутри приложения.

---

## 4. Database File

Путь к database должен задаваться configuration.

Не hard-code путь внутри business logic.

---

## 5. Initialization

При startup Database subsystem должна:

1. открыть database;
2. проверить доступность;
3. выполнить schema validation;
4. выполнить необходимые migrations;
5. проверить integrity;
6. предоставить database другим subsystems.

---

## 6. Migrations

Изменения schema должны выполняться через versioned migrations.

Нельзя изменять schema вручную без migration mechanism.

---

## 7. Migration Version

Database должна хранить текущую schema version.

После успешной migration version должна обновляться atomically.

---

## 8. Migration Safety

Если migration завершилась ошибкой:

приложение не должно считать database полностью готовой.

Нельзя продолжать работу так, будто migration успешно завершилась.

---

## 9. Transactions

Изменения нескольких связанных records должны выполняться в transaction.

Partial writes должны быть предотвращены.

---

## 10. Atomicity

Критические state changes должны быть atomic.

Например:

создание confirmed opportunity и изменение соответствующего state не должны приводить к частично сохранённому состоянию.

---

## 11. Connection Management

Database access должен использовать централизованный Database layer.

Subsystems не должны создавать произвольные SQLite connections по всему проекту.

---

## 12. Repository Boundary

Business logic не должна напрямую писать SQL во всех модулях.

Необходимо использовать repository/data-access layer.

---

## 13. SQL Boundary

SQL queries должны быть локализованы в Database/Repository layer.

Scanner и другие business modules работают с domain models.

---

## 14. Schema

Schema должна быть нормализована настолько, насколько это необходимо для:

- consistency;
- deduplication;
- querying;
- recovery;
- diagnostics.

Не создавать чрезмерно сложную schema без необходимости.

---

## 15. Core Entities

Database должна иметь возможность хранить как минимум:

- scheduler state;
- scan metadata;
- Level 2 Jobs;
- confirmed opportunities;
- notification state;
- fee snapshots;
- diagnostics;
- schema metadata.

---

## 16. Opportunities

Confirmed opportunities должны иметь persistent record.

Минимально:

- opportunity ID;
- Job ID;
- timestamp;
- network;
- token pair;
- amount;
- route;
- entry provider;
- exit provider;
- profit;
- profit percentage;
- status.

---

## 17. Opportunity Status

Минимально поддерживать:

- CONFIRMED;
- NOTIFIED;
- NOTIFIED_PARTIAL;
- NOTIFIED_FAILED;
- EXPIRED.

Фактическая state machine должна быть согласована с Notification System.

---

## 18. Level 2 Jobs

Database должна хранить необходимое состояние Level 2 Jobs для recovery и diagnostics.

Минимально:

- job ID;
- candidate fingerprint;
- created_at;
- status;
- priority;
- expiration;
- confirmation result.

---

## 19. Level 1 Scan Records

Необходимо хранить metadata Level 1 scans.

Минимально:

- scan ID;
- started_at;
- finished_at;
- network;
- status;
- combinations checked;
- candidates created;
- errors.

---

## 20. Raw Quotes

Database не обязана хранить каждый raw quote.

Raw quote history не должна бесконтрольно расти.

---

## 21. Quote Retention

Если raw quotes сохраняются для diagnostics:

они должны иметь explicit retention policy.

---

## 22. Fee Snapshots

Fee System может сохранять normalized fee snapshots.

Snapshot должен иметь:

- snapshot ID;
- provider;
- network;
- fee type;
- value;
- timestamp;
- validity/expiration.

---

## 23. Fee History

Fee history должна храниться только в объёме, необходимом для:

- current state;
- diagnostics;
- audit;
- approved statistics.

---

## 24. Scheduler State

Database может хранить необходимое scheduler runtime state.

Например:

- schedule ID;
- last execution;
- next execution;
- status;
- execution ID.

---

## 25. Notification State

Database должна хранить notification state для:

- deduplication;
- retry;
- recovery;
- diagnostics.

---

## 26. Notification Attempts

Delivery attempts могут храниться отдельно от основного notification record.

Минимально:

- attempt ID;
- notification ID;
- started_at;
- finished_at;
- status;
- error code.

---

## 27. Deduplication

Database должна поддерживать deterministic deduplication.

Для этого могут использоваться:

- unique constraints;
- fingerprints;
- indexes;
- time windows.

---

## 28. Unique Constraints

Критические identity fields должны иметь соответствующие unique constraints.

Например:

- opportunity ID;
- Job ID;
- notification ID;
- scan ID;
- candidate fingerprint при соответствующей policy.

---

## 29. Indexes

Необходимо создавать indexes для часто используемых запросов.

Минимально для:

- status;
- created_at;
- opportunity ID;
- Job ID;
- fingerprint;
- provider;
- network.

---

## 30. No Excessive Indexing

Не создавать indexes для каждого поля.

Каждый index должен иметь практическую query/recovery/deduplication цель.

---

## 31. Foreign Keys

Если используются relational references:

SQLite foreign keys должны быть явно включены.

---

## 32. Referential Integrity

Связанные records не должны оставаться в неконсистентном состоянии.

Например:

notification не должна ссылаться на несуществующую opportunity.

---

## 33. Deletion Policy

Удаление records должно выполняться согласно retention policy.

Не удалять подтверждённые opportunities случайно.

---

## 34. Retention

Retention period должен быть configurable.

Он может различаться для:

- scans;
- jobs;
- notifications;
- fee snapshots;
- diagnostics;
- confirmed opportunities.

---

## 35. Cleanup

Cleanup должен выполняться отдельной scheduled maintenance task.

Не выполнять массовый cleanup во время каждого scanner cycle.

---

## 36. Cleanup Safety

Перед удалением старых данных необходимо учитывать dependencies.

Нельзя удалить record, который всё ещё нужен для:

- recovery;
- notification retry;
- audit;
- deduplication.

---

## 37. WAL

SQLite может использовать WAL mode для улучшения concurrency, если это соответствует deployment policy.

---

## 38. Busy Handling

Database layer должен корректно обрабатывать временные SQLite locking/busy conditions.

---

## 39. Database Timeout

SQLite connection должен иметь configurable timeout для временного database lock.

---

## 40. No Infinite DB Retry

Database lock не должен приводить к бесконечному retry loop.

---

## 41. Integrity Check

Database subsystem должна иметь возможность выполнить integrity check.

---

## 42. Corruption

Если database integrity check обнаруживает corruption:

приложение не должно продолжать silently.

Ошибка должна быть явно зафиксирована.

---

## 43. Backup

Архитектура должна позволять выполнять database backup.

Backup policy должна быть configuration-driven.

---

## 44. Backup Safety

Backup не должен блокировать основную работу Monik дольше необходимого.

---

## 45. Recovery

Database recovery должна позволять восстановить:

- confirmed opportunities;
- notification state;
- necessary job state;
- required scheduler state.

---

## 46. Idempotency

Operations, которые могут быть повторены после restart, должны быть idempotent.

---

## 47. Crash Safety

После неожиданного завершения приложения database не должна содержать частично записанные critical transactions.

---

## 48. Timestamp

Все важные records должны иметь timestamps.

Минимально:

- created_at;
- updated_at.

Для execution records также:

- started_at;
- finished_at.

---

## 49. Time Storage

Внутреннее хранение timestamp должно быть единообразным.

Timezone conversion выполняется на application boundary.

---

## 50. IDs

Entity IDs должны генерироваться централизованно согласно project ID policy.

Не использовать случайные несогласованные ID formats в разных subsystems.

---

## 51. Database Models

Database models должны быть отделены от external API response models.

---

## 52. Domain Models

Business logic должна работать с domain models.

Repository layer отвечает за преобразование:

database record ↔ domain model.

---

## 53. Validation

Database layer должен проверять обязательные поля и типы.

Business-level validation остаётся responsibility соответствующей subsystem.

---

## 54. Nullability

Nullable fields должны быть явно определены.

Не использовать NULL как скрытый способ обозначить неизвестное состояние без policy.

---

## 55. Unknown Values

UNKNOWN и NULL не должны автоматически трактоваться как zero.

Особенно это относится к:

- fees;
- gas;
- profit components.

---

## 56. Financial Storage

Финансовые значения должны храниться без binary floating point precision loss.

Предпочтительно использовать:

- integer base units;
- или exact decimal representation.

---

## 57. Amount Storage

Token amounts должны храниться с учётом token decimals.

Нельзя терять precision при сохранении.

---

## 58. Profit Storage

Profit должен сохраняться в exact representation.

Display rounding выполняется только на notification/UI layer.

---

## 59. Schema Compatibility

Изменение финансовых типов требует migration и backward compatibility analysis.

---

## 60. Configuration State

Database не должна становиться единственным источником пользовательской configuration.

Configuration subsystem остаётся authoritative source для user settings.

---

## 61. Runtime State

Database может хранить runtime state, необходимый для recovery.

Но ephemeral state не обязан сохраняться.

---

## 62. Cache Boundary

SQLite не является cache layer для live quotes.

Если данные должны быть cached, это должно быть отдельной explicit subsystem/policy.

---

## 63. Query Performance

Queries для критических runtime operations должны иметь predictable performance.

Особенно:

- deduplication;
- job lookup;
- notification lookup;
- opportunity lookup;
- scheduler state.

---

## 64. Pagination

Исторические queries должны поддерживать ограничение объёма результатов.

Не загружать бесконечную историю в memory.

---

## 65. Diagnostics Queries

Database layer должен позволять получать:

- последние scans;
- последние Level 2 Jobs;
- последние confirmed opportunities;
- notification failures;
- provider failures;
- scheduler executions.

---

## 66. Health

Database health check должен проверять:

- connection;
- basic query;
- schema version;
- integrity state.

---

## 67. Startup Failure

Если обязательная Database initialization не удалась:

application startup должен следовать explicit failure policy.

Нельзя запускать критические subsystems с неизвестным database state.

---

## 68. Graceful Shutdown

При shutdown:

- новые DB operations не должны приниматься;
- активные transactions должны завершиться или быть корректно отменены;
- connections должны быть закрыты.

---

## 69. Thread/Async Safety

Database access должен соответствовать выбранной concurrency model приложения.

Нельзя использовать одну SQLite connection небезопасным образом из произвольных concurrent tasks.

---

## 70. Testing

Обязательно тестировать:

- schema creation;
- migrations;
- rollback;
- transactions;
- unique constraints;
- foreign keys;
- indexes;
- retention;
- cleanup;
- deduplication;
- recovery;
- crash safety;
- locking;
- concurrency;
- integrity check;
- backup;
- restore.

---

## 71. Migration Testing

Каждая migration должна иметь тест:

old schema
→ migration
→ expected new schema.

---

## 72. Repository Testing

Repository layer должен тестироваться отдельно от business logic.

---

## 73. Integration Testing

Необходимо тестировать:

Scheduler → Database

Level 1 → Database

Level 2 → Database

Notification → Database

Fee System → Database

---

## 74. No Direct SQL in Business Logic

Business modules не должны содержать произвольные SQL queries.

---

## 75. No Cross-Subsystem Tables Manipulation

Одна subsystem не должна напрямую изменять database records другой subsystem в обход repository/API boundary.

Например:

Level 1 не должен напрямую менять notification status.

---

## 76. Auditability

Критические state transitions должны быть диагностируемыми.

Минимально можно определить:

- кто/какая subsystem изменила state;
- когда;
- из какого состояния;
- в какое состояние.

---

## 77. State Transition

State transition должен выполняться через соответствующий service/repository method.

Не разрешать произвольное изменение status field из любого модуля.

---

## 78. Database Exceptions

Database exceptions должны быть нормализованы в понятные application-level errors.

---

## 79. Logging

Database layer должен логировать:

- migration;
- transaction failures;
- lock errors;
- integrity errors;
- backup failures;
- recovery failures.

Не логировать secrets.

---

## 80. Metrics

Database metrics должны включать:

- query latency;
- transaction latency;
- errors;
- lock/busy events;
- database size;
- cleanup duration;
- migration duration.

---

## 81. Critical Invariants

Database subsystem никогда не должна:

1. использовать SQLite как источник live quotes;

2. хранить финансовые значения через binary float;

3. позволять business modules произвольно выполнять SQL;

4. обходить migration mechanism;

5. выполнять бесконечные retry при database lock;

6. удалять данные без retention policy;

7. удалять records, необходимые для recovery;

8. silently продолжать работу после обнаружения corruption;

9. становиться единственным источником user configuration;

10. смешивать database models с external API models;

11. допускать неконсистентные foreign key relationships;

12. терять precision token amounts;

13. считать NULL или UNKNOWN равным zero;

14. создавать неконтролируемое количество concurrent database connections;

15. изменять state другой subsystem в обход установленной boundary.

---

## 82. Главный принцип

Database должна обеспечить:

**надёжное, атомарное и восстанавливаемое хранение необходимого состояния Monik, не превращаясь в источник устаревших market data и не нарушая границы между подсистемами.**

Database отвечает за:

**сохранить состояние.**

Остальные subsystems отвечают за:

**создать и изменить это состояние через утверждённые interfaces.**

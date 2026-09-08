# MONIK — DATA RETENTION

## 1. Назначение

Этот документ определяет правила хранения, очистки и удаления persistent и operational data Monik.

Цель:

- не допускать бесконтрольного роста database;
- сохранять данные, необходимые для recovery;
- сохранять необходимые diagnostics;
- не удалять critical financial state;
- ограничивать объём historical data;
- обеспечить предсказуемое поведение cleanup.

---

## 2. Главный принцип

Monik должен хранить данные только столько, сколько они нужны для:

- работы системы;
- recovery;
- deduplication;
- diagnostics;
- audit;
- operational analysis.

После окончания необходимости данные должны удаляться согласно retention policy.

---

## 3. Retention Categories

Данные делятся на:

- CRITICAL;
- OPERATIONAL;
- HISTORICAL;
- TEMPORARY;
- DIAGNOSTIC.

---

## 4. CRITICAL Data

CRITICAL data необходима для финансовой или operational integrity.

К ней относятся:

- confirmed opportunities;
- необходимые state transitions;
- pending notifications;
- active Level 2 Jobs;
- migration metadata.

CRITICAL data нельзя удалять обычным cleanup.

---

## 5. OPERATIONAL Data

OPERATIONAL data используется для текущей работы и recovery.

Например:

- active Jobs;
- recent scans;
- scheduler state;
- recent capability state;
- recent fee snapshots.

---

## 6. HISTORICAL Data

HISTORICAL data сохраняется ограниченное время для:

- diagnostics;
- statistics;
- analysis;
- debugging.

---

## 7. TEMPORARY Data

TEMPORARY data должна удаляться после завершения операции или по короткому retention period.

---

## 8. DIAGNOSTIC Data

Diagnostic data может сохраняться дольше temporary data, но также должна иметь retention policy.

---

## 9. Confirmed Opportunities

Confirmed Opportunities являются critical historical records.

Они не должны удаляться обычным automated cleanup.

---

## 10. Opportunity Retention

Если в будущем будет необходимость ограничить хранение Opportunities:

это должно быть отдельной explicit policy.

Удаление не должно выполняться silently.

---

## 11. Opportunity Audit

Если Opportunity удаляется по approved retention policy:

необходимо учитывать требования audit/recovery.

---

## 12. Level 2 Jobs

Active Jobs должны сохраняться до:

- confirmation;
- rejection;
- expiration;
- failure;
- cancellation.

---

## 13. Completed Jobs

Completed/terminal Jobs могут храниться ограниченное время для diagnostics.

---

## 14. Job Retention

Retention для terminal Jobs должен быть configuration-driven.

---

## 15. Active Job Protection

Cleanup никогда не должен удалять:

- QUEUED;
- RUNNING

Jobs, если они ещё необходимы для recovery.

---

## 16. Expired Jobs

Expired Jobs могут быть удалены после установленного retention period.

---

## 17. Failed Jobs

Failed Jobs могут храниться дольше обычных expired Jobs для diagnostics.

---

## 18. Candidate Retention

Candidates используются преимущественно для:

- Level 2 workflow;
- deduplication;
- diagnostics.

После expiration и окончания deduplication window они могут удаляться.

---

## 19. Candidate Cleanup

Candidate cleanup должен учитывать:

- candidate status;
- expiration;
- related Job;
- deduplication policy.

---

## 20. Candidate Dependency

Нельзя удалить Candidate, если active Job всё ещё ссылается на него.

---

## 21. Scan History

Scan history не является critical financial state.

Она может иметь ограниченный retention.

---

## 22. Scan Retention

Completed scans могут удаляться после configured retention period.

---

## 23. Failed Scans

Failed/partial scans могут иметь более длинный retention для diagnostics.

---

## 24. Raw Quotes

Raw quotes не должны храниться постоянно без explicit requirement.

---

## 25. Quote Retention

Если quote persistence включена:

она должна иметь короткий retention period.

---

## 26. No Infinite Quote History

Не создавать database, которая бесконтрольно растёт из-за каждого scanner quote.

---

## 27. Fee Snapshots

Fee snapshots могут сохраняться для:

- recovery;
- diagnostics;
- historical analysis.

---

## 28. Fee Retention

Старые Fee Snapshots должны удаляться согласно retention policy.

---

## 29. Current Fee Snapshot

Последний valid Fee Snapshot должен сохраняться до тех пор, пока он необходим для startup/recovery.

---

## 30. Stale Fee Snapshot

Stale snapshots могут сохраняться ограниченное время для diagnostics.

---

## 31. Capability History

Capability changes могут сохраняться для diagnostics.

---

## 32. Capability Retention

Capability history должна иметь ограниченный retention.

---

## 33. Current Capability State

Current capability state может сохраняться как operational state.

---

## 34. Health History

Health state history может иметь короткий retention.

---

## 35. Health Events

Significant incidents и recovery events могут храниться дольше обычных health samples.

---

## 36. Notification Data

Notifications должны храниться до завершения delivery/retry lifecycle.

---

## 37. Sent Notifications

Successfully sent notifications могут сохраняться для deduplication и audit.

---

## 38. Failed Notifications

Failed notifications должны храниться достаточно долго для diagnostics/recovery.

---

## 39. Notification Attempts

Notification attempts могут иметь более короткий retention, чем сама Notification.

---

## 40. Duplicate Protection

Нельзя удалять notification state до окончания периода, в котором duplicate delivery может возникнуть из-за retry/restart.

---

## 41. Scheduler History

Scheduler execution history может иметь ограниченный retention.

---

## 42. Scheduler State

Current scheduler state должен сохраняться, пока он нужен для recovery.

---

## 43. Execution Records

Execution records могут использоваться для diagnostics.

Они должны иметь retention policy.

---

## 44. Error History

Normalized errors могут сохраняться для diagnostics.

---

## 45. Error Retention

Ошибки должны иметь retention, соответствующий их operational importance.

---

## 46. Critical Errors

Critical errors могут сохраняться дольше transient errors.

---

## 47. Logs

Logs имеют отдельную retention policy.

Они не должны храниться внутри основной database без explicit reason.

---

## 48. Log Retention

Production logs должны иметь:

- rotation;
- maximum size;
- retention period.

---

## 49. Diagnostic Snapshots

Diagnostic snapshots должны иметь ограниченный retention.

---

## 50. Temporary Files

Temporary files должны удаляться после использования.

---

## 51. Crash Artifacts

Crash artifacts могут сохраняться ограниченное время для diagnostics.

---

## 52. Backup Retention

Database backups должны иметь отдельную retention policy.

---

## 53. Backup Classes

Можно использовать:

- short-term backups;
- medium-term backups;
- long-term backups.

Фактические periods определяются deployment policy.

---

## 54. Backup Safety

Retention cleanup не должен удалить все доступные backups одновременно.

---

## 55. Minimum Recovery Set

Всегда должен сохраняться минимум один usable recent backup, если production backup system активен.

---

## 56. Backup Verification

Не считать backup пригодным только потому, что файл существует.

Restore verification является частью backup policy.

---

## 57. Data Classification

Каждая новая persistent entity должна иметь:

- retention class;
- retention period;
- cleanup owner;
- deletion policy.

---

## 58. No Unclassified Data

Новые persistent tables не должны появляться без определения retention policy.

---

## 59. Configuration

Retention periods должны быть configuration-driven, если это безопасно.

---

## 60. Safe Defaults

Если retention configuration отсутствует:

использовать conservative default, предотвращающий случайное удаление critical data.

---

## 61. No Zero Retention for Critical Data

Critical data не должна иметь retention period = 0 без explicit approved policy.

---

## 62. Cleanup Scheduler

Cleanup должен выполняться через Scheduler.

Не создавать отдельный uncontrolled background cleanup loop.

---

## 63. Cleanup Frequency

Cleanup frequency должна быть configuration-driven.

---

## 64. Cleanup Batching

Large cleanup operations должны выполняться batches, чтобы не создавать долгие database locks.

---

## 65. Cleanup Transactions

Каждый batch cleanup должен использовать controlled transaction.

---

## 66. Cleanup During Scanner

Cleanup не должен блокировать Level 1/Level 2 дольше допустимого.

---

## 67. Cleanup Priority

Если database pressure высокий:

cleanup может получить повышенный operational priority.

---

## 68. Database Size Monitoring

Health/Observability должны отслеживать:

- database size;
- table growth;
- cleanup success;
- cleanup failures.

---

## 69. Retention Metrics

Минимально полезно иметь:

- records deleted;
- cleanup duration;
- cleanup failures;
- database size;
- oldest retained record.

---

## 70. Cleanup Logging

Каждый cleanup run должен иметь structured log:

- started_at;
- finished_at;
- entity types;
- records deleted;
- errors;
- database size before/after.

---

## 71. No Sensitive Logging

Cleanup logs не должны содержать secrets.

---

## 72. Cleanup Failure

Если cleanup failed:

application не должен автоматически удалять больше данных в попытке «исправить» проблему.

---

## 73. Partial Cleanup

Partial cleanup допустим.

Следующий scheduled cleanup может продолжить работу.

---

## 74. Idempotent Cleanup

Повторный cleanup должен быть безопасным.

---

## 75. Crash During Cleanup

Если process crash произошёл во время cleanup:

database должна остаться consistent благодаря transaction semantics.

---

## 76. Retention Boundary

Record должен удаляться только после полного истечения retention period.

---

## 77. Time Calculation

Retention должен рассчитываться относительно UTC timestamps.

---

## 78. Clock

Cleanup logic должна использовать controlled clock abstraction для тестирования.

---

## 79. Future Timestamps

Record с timestamp из будущего не должен автоматически удаляться.

---

## 80. Invalid Timestamps

Invalid timestamp должен приводить к conservative behavior.

Не удалять record автоматически только потому, что timestamp не удалось корректно прочитать.

---

## 81. Related Records

Перед удалением parent record необходимо проверить связанные child records.

---

## 82. Foreign Keys

Foreign key constraints должны предотвращать accidental orphan relationships.

---

## 83. Deletion Order

Если cascade deletion не используется:

сначала удаляются безопасные dependent records, затем parent records.

---

## 84. Confirmed Opportunity Protection

Cleanup не должен удалять Opportunity только потому, что:

- она старая;
- notification уже отправлена;
- Job завершён.

Для удаления требуется отдельная retention policy.

---

## 85. Notification Protection

Pending/retryable notifications нельзя удалять.

---

## 86. Job Protection

Active Jobs нельзя удалять.

---

## 87. Migration Protection

Migration metadata никогда не должна удаляться retention cleanup.

---

## 88. Schema Protection

Cleanup не должен изменять database schema.

Schema changes выполняются только migrations.

---

## 89. No Dynamic Schema Changes

Retention system не должен создавать/удалять tables автоматически.

---

## 90. Dry Run

Для destructive cleanup желательно иметь dry-run capability.

Она позволяет определить:

- какие records будут удалены;
- сколько records;
- предполагаемый размер освобождения.

---

## 91. Production Cleanup

В production destructive cleanup должен быть предсказуемым и observable.

---

## 92. Manual Cleanup

Manual cleanup допускается только через approved operational command/interface.

---

## 93. Manual Cleanup Protection

Manual destructive cleanup должен требовать explicit confirmation.

---

## 94. No Arbitrary SQL Cleanup

Оператор не должен выполнять произвольный SQL для удаления production data как обычную maintenance procedure.

---

## 95. Recovery Before Cleanup

Перед крупным destructive cleanup должна быть возможность восстановить database из backup.

---

## 96. Retention Changes

Изменение retention period не должно автоматически удалять существующие данные без явного понимания последствий.

---

## 97. Shortening Retention

Сокращение retention является потенциально destructive operation.

Оно должно проходить отдельную review/approval.

---

## 98. Increasing Retention

Увеличение retention обычно безопаснее, но должно учитывать disk capacity.

---

## 99. Disk Pressure

Если disk pressure критически высок:

cleanup может удалять только data, которую policy разрешает удалить.

Нельзя удалять critical financial state только ради освобождения места.

---

## 100. Critical Invariants

Data Retention никогда не должна:

1. удалять active Level 2 Jobs;

2. удалять pending Notifications;

3. удалять confirmed Opportunities обычным cleanup;

4. удалять migration metadata;

5. удалять database schema;

6. удалять records с invalid timestamps автоматически;

7. выполнять uncontrolled mass deletion;

8. удалять все backups;

9. обходить Repository layer;

10. выполнять raw SQL из business logic;

11. блокировать database на неопределённое время;

12. хранить бесконечные logs;

13. создавать бесконечный рост historical data;

14. изменять domain state только ради cleanup;

15. считать backup valid без возможности restore;

16. удалять critical data только из-за disk pressure.

---

## 101. Главный принцип

Data Retention должна обеспечить:

**контролируемое хранение и своевременное удаление ненужных данных без риска потери critical state, нарушения recovery, duplicate protection или financial integrity.**

Каждая persistent data должна иметь понятный lifecycle:

**create → active → historical/terminal → retention period → safe cleanup.**

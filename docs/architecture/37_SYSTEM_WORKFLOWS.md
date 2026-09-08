# MONIK — SYSTEM WORKFLOWS

## 1. Назначение

Этот документ определяет обязательные end-to-end workflows Monik.

Он описывает, как данные и управление проходят через основные subsystem:

- Scheduler;
- Level 1 Scanner;
- Resource Manager;
- Aggregator Adapters;
- Fee System;
- Capability Registry;
- Profit Calculator;
- Level 2 Scanner;
- Database;
- Notification System;
- Health Monitoring.

---

## 2. Главный принцип

Каждый critical workflow должен иметь:

- определённую точку входа;
- определённый порядок выполнения;
- определённые boundaries;
- условия успеха;
- условия отказа;
- retry policy;
- expiration policy;
- recovery behavior.

Нельзя создавать альтернативные скрытые workflows, обходящие architecture boundaries.

---

## 3. Основной Workflow

Основной arbitrage workflow:

Scheduler
→ Level 1
→ Candidate
→ Level 2 Job
→ Level 2
→ fresh data
→ Profit Calculator
→ Opportunity
→ Notification.

---

## 4. Level 1 Workflow

Level 1 workflow:

1. получить active configuration;
2. определить enabled networks;
3. определить enabled tokens;
4. определить enabled providers;
5. проверить capabilities;
6. получить quotes;
7. normalize quotes;
8. выполнить preliminary comparison;
9. создать Candidate при выполнении условий;
10. передать Candidate в Level 2 workflow.

---

## 5. Level 1 не подтверждает Opportunity

Level 1 только обнаруживает потенциальную opportunity.

Он не создаёт CONFIRMED Opportunity.

---

## 6. Level 1 Scope

Каждый scan должен использовать explicit scope:

- networks;
- tokens;
- providers;
- amounts.

---

## 7. Level 1 Provider Selection

Перед quote request Level 1 должен убедиться, что provider:

- enabled;
- доступен;
- поддерживает network;
- поддерживает необходимую operation.

---

## 8. Level 1 Resource Manager

Все external provider requests должны проходить через Resource Manager.

Level 1 не должен напрямую управлять:

- rate limits;
- concurrency;
- retry;
- backoff.

---

## 9. Level 1 Quote Collection

Для каждого valid scan combination Level 1 получает необходимые quotes.

Каждый quote должен быть normalized.

---

## 10. Level 1 Quote Failure

Если один provider request failed:

это не должно автоматически останавливать весь scan.

Если достаточно данных для продолжения:

scan продолжает работу.

---

## 11. Level 1 Insufficient Data

Если необходимых данных недостаточно для безопасного Candidate:

Candidate не создаётся.

---

## 12. Level 1 Preliminary Profit

Preliminary profitability может использоваться для filtering.

Она не является окончательным profit result.

---

## 13. Candidate Creation

Candidate создаётся только если:

- quote valid;
- route valid;
- required provider pair valid;
- amount valid;
- preliminary conditions выполнены;
- Candidate не является duplicate.

---

## 14. Candidate Fingerprint

Перед созданием Candidate необходимо выполнить deduplication по canonical fingerprint.

---

## 15. Candidate Persistence

Candidate должен быть сохранён согласно Database и Retention policies.

---

## 16. Candidate → Level 2

После создания Candidate передаётся в Level 2 workflow.

---

## 17. Level 2 Job Creation

Для Candidate создаётся Level 2 Job.

Job должен содержать ссылку на исходный Candidate.

---

## 18. Level 2 Job Queue

Job помещается в controlled queue.

Queue должна иметь bounded capacity.

---

## 19. Level 2 Job Expiration

Перед execution worker должен проверить:

- Candidate expiration;
- Job expiration;
- required freshness.

Expired Job не должен выполняться.

---

## 20. Level 2 Route Rule

Level 2 обязан проверять **именно ту комбинацию и route parameters, которые были обнаружены Level 1**.

---

## 21. Запрет смены маршрута

Level 2 не должен автоматически заменять обнаруженный Level 1 route другим route только потому, что другой route в момент confirmation оказался более выгодным.

---

## 22. Level 2 Fresh Quotes

Level 2 должен запросить актуальные данные для confirmation.

Level 1 quote не должен считаться автоматически достаточно свежим.

---

## 23. Level 2 Provider Requests

Fresh requests выполняются через:

Level 2
→ Resource Manager
→ Aggregator Adapter
→ Provider API.

---

## 24. Level 2 Fees

Level 2 должен получить актуальные необходимые fees через Fee System.

---

## 25. Level 2 Gas

Level 2 должен получить актуальные необходимые gas data через соответствующий Fee/Gas subsystem согласно architecture.

---

## 26. Level 2 Profit Calculation

После получения fresh financial inputs:

Level 2
→ Profit Calculator.

---

## 27. Profit Calculator Input

Profit Calculator получает:

- input amount;
- output amount;
- fees;
- gas;
- conversion data;
- calculation context.

---

## 28. Profit Calculator Output

Profit Calculator возвращает normalized ProfitResult.

---

## 29. Confirmation Decision

Level 2 может подтвердить opportunity только если:

- required quotes valid;
- quotes fresh;
- route соответствует Candidate;
- fees valid;
- gas valid;
- profit calculation valid;
- required profitability conditions выполнены.

---

## 30. No Confirmation on Unknown

Если critical financial information неизвестна:

Opportunity не подтверждается.

Допустимый результат:

- REJECTED;
- FAILED;
- RETRY;
- EXPIRED.

---

## 31. Profit Recheck

Level 2 должен использовать результат Profit Calculator, а не preliminary profitability Level 1.

---

## 32. Positive Profit Requirement

CONFIRMED Opportunity должна соответствовать configured profitability policy.

---

## 33. Opportunity Creation

После успешной confirmation создаётся immutable Opportunity financial snapshot.

---

## 34. Opportunity Persistence

Opportunity должна быть сохранена в database до начала notification delivery.

---

## 35. Confirmation Atomicity

Создание confirmed Opportunity и соответствующий critical Job state должны быть согласованы через transaction boundary.

---

## 36. Notification Workflow

После сохранения Opportunity:

Opportunity
→ Notification System.

---

## 37. Notification Queue

Каждая Notification должна проходить controlled queue/delivery workflow.

---

## 38. Notification Formatting

Notification System форматирует сообщение на основе Opportunity.

Она не пересчитывает financial values.

---

## 39. Notification Delivery

Notification System:

1. получает Opportunity;
2. определяет configured destinations;
3. создаёт notification records;
4. выполняет delivery;
5. сохраняет результат.

---

## 40. Notification Success

При успешной delivery Notification становится SENT.

Opportunity может перейти в соответствующий notified state согласно policy.

---

## 41. Notification Partial Success

Если destinations несколько и часть delivery успешна:

Opportunity может перейти в NOTIFIED_PARTIAL.

---

## 42. Notification Failure

Если delivery окончательно failed:

Opportunity может перейти в NOTIFIED_FAILED.

Financial snapshot при этом не изменяется.

---

## 43. Notification Retry

Temporary delivery failures должны использовать retry policy.

---

## 44. Notification Idempotency

Перед повторной отправкой необходимо проверить persistent notification state.

---

## 45. Duplicate Notification Prevention

Если logical notification уже SENT:

повторная delivery не выполняется автоматически.

---

## 46. Scheduler Workflow

Scheduler запускает periodic tasks.

Основные задачи могут включать:

- Level 1 scans;
- fee refresh;
- capability refresh;
- cleanup;
- health checks;
- notification retries;
- maintenance.

---

## 47. Scheduler Boundary

Scheduler отвечает только за scheduling.

Business logic выполняется соответствующими services.

---

## 48. Scheduler Task Execution

Task execution:

Scheduler
→ Service
→ subsystem workflow.

---

## 49. Scheduler Failure

Failure одной task не должен останавливать остальные independent tasks.

---

## 50. Scheduler Overlap

Если overlap запрещён:

новая execution не должна запускаться параллельно предыдущей.

---

## 51. Resource Manager Workflow

Каждый external resource request проходит:

Service
→ Resource Manager
→ limits/policy
→ Adapter
→ external provider.

---

## 52. Resource Admission

Resource Manager проверяет:

- provider limit;
- network limit;
- global concurrency;
- queue capacity;
- timeout;
- circuit state.

---

## 53. Resource Rejection

Если resource request не может быть безопасно выполнен:

он должен быть rejected/queued согласно policy.

---

## 54. Retry Workflow

Retry применяется только к retryable errors.

---

## 55. Retry Sequence

Рекомендуемый workflow:

operation
→ failure
→ classify error
→ check retryable
→ check retry budget
→ calculate backoff
→ wait
→ retry.

---

## 56. No Retry for Permanent Errors

Permanent errors не должны повторяться бесконечно.

---

## 57. Retry Budget

Каждая retryable operation должна иметь bounded retry budget.

---

## 58. Backoff

Retry должен использовать controlled backoff.

---

## 59. Jitter

При concurrent retry рекомендуется использовать jitter.

---

## 60. Rate Limit Workflow

При provider rate limit:

1. определить rate-limit error;
2. получить Retry-After, если доступен;
3. применить Resource Manager policy;
4. отложить request;
5. выполнить retry только если operation ещё valid.

---

## 61. Expired Retry

Если Candidate/Job expired во время ожидания retry:

retry не выполняется.

---

## 62. Circuit Breaker Workflow

При repeated provider failures:

Resource Manager может перевести provider circuit:

CLOSED
→ OPEN
→ HALF_OPEN
→ CLOSED/OPEN.

---

## 63. Open Circuit

При OPEN новые requests к соответствующему resource не должны выполняться, кроме разрешённых recovery probes.

---

## 64. Recovery Probe

HALF_OPEN используется для controlled recovery check.

---

## 65. Provider Recovery

После успешного recovery provider возвращается в normal operation согласно threshold policy.

---

## 66. Provider Outage

Если provider недоступен:

Level 1 может продолжить работу с другими compatible providers.

---

## 67. Level 2 Provider Outage

Если необходимый provider pair недоступен:

Level 2 не должен искать произвольную замену route.

Job должен завершиться согласно failure/rejection/retry policy.

---

## 68. Capability Workflow

Capability Registry используется перед выполнением provider/network operation.

---

## 69. Capability Refresh

Capability может периодически проверяться Scheduler.

---

## 70. Unknown Capability

UNKNOWN capability не должна разрешать operation.

---

## 71. Fee Refresh Workflow

Fee System получает/обновляет required fee data.

Workflow:

Scheduler
→ Fee System
→ Provider/Network source
→ validation
→ normalized fee snapshot
→ persistence.

---

## 72. Fee Failure

Если fee source недоступен:

не заменять fee на zero.

---

## 73. Stale Fee

Stale fee может использоваться только если explicit policy это разрешает.

Для critical Level 2 confirmation stale fee должен приводить к rejection/retry согласно policy.

---

## 74. Gas Workflow

Gas workflow аналогичен Fee workflow:

source
→ validation
→ normalized gas data
→ freshness
→ persistence.

---

## 75. Configuration Workflow

Startup:

configuration sources
→ parse
→ validate
→ normalize
→ resolve secrets
→ final configuration
→ subsystem initialization.

---

## 76. Configuration Failure

Если critical configuration invalid:

application не должен запускать соответствующий critical workflow.

---

## 77. Runtime Reload

Если configuration reload разрешён:

new configuration
→ parse
→ validate
→ normalize
→ atomic apply.

При failure текущая valid configuration сохраняется.

---

## 78. Database Workflow

Persistent workflow:

service
→ repository
→ transaction
→ database.

---

## 79. No Direct SQL

Business logic не должна обращаться к database напрямую.

---

## 80. Transaction Boundary

Transaction должна включать только необходимые database operations.

External HTTP/Telegram requests не выполняются внутри transaction.

---

## 81. Recovery Workflow

После application restart:

1. load configuration;
2. initialize database;
3. validate migrations;
4. restore persistent operational state;
5. recover active Jobs;
6. recover pending Notifications;
7. initialize Scheduler;
8. run health checks;
9. start normal operation.

---

## 82. RUNNING Job Recovery

RUNNING Job после crash должен пройти recovery policy.

Он не считается автоматически successful.

---

## 83. Pending Notification Recovery

Pending/retryable notifications должны быть восстановлены после restart.

---

## 84. Duplicate Protection During Recovery

Recovery не должна создавать duplicate:

- Jobs;
- Opportunities;
- Notifications.

---

## 85. Graceful Shutdown

Shutdown workflow:

1. stop accepting new scheduled work;
2. stop creating new Level 1 scans;
3. prevent new Level 2 admissions;
4. allow safe operations to finish within timeout;
5. persist required state;
6. stop notification processing according to policy;
7. close database;
8. terminate process.

---

## 86. Forced Shutdown

Если graceful shutdown не завершился за configured timeout:

application должен завершиться безопасно настолько, насколько возможно.

RUNNING state должен быть recoverable после restart.

---

## 87. Health Workflow

Health Monitoring получает состояния subsystem.

Health checks должны определять:

- provider availability;
- database availability;
- scheduler state;
- resource manager state;
- critical subsystem state.

---

## 88. Health and Business Logic

Health Monitoring не должен изменять Opportunity или financial state.

---

## 89. Degraded Mode

Если optional component unavailable:

application может работать DEGRADED, если critical safety conditions сохраняются.

---

## 90. Critical Failure

Если critical subsystem не может безопасно работать:

application должен перейти в соответствующее unavailable/safe state.

---

## 91. Cleanup Workflow

Scheduler запускает retention cleanup.

Cleanup:

1. определяет eligible records;
2. проверяет dependencies;
3. удаляет безопасными batches;
4. фиксирует statistics;
5. сохраняет cleanup result.

---

## 92. Cleanup Protection

Cleanup не должен удалять:

- active Jobs;
- pending Notifications;
- required recovery state;
- migration metadata;
- protected Opportunities.

---

## 93. Backup Workflow

Если backup system включён:

Scheduler/maintenance workflow создаёт consistent database backup.

---

## 94. Backup Verification

Backup должен проходить verification согласно deployment policy.

---

## 95. Error Workflow

При ошибке:

operation
→ error classification
→ normalized error
→ retry/reject/fail
→ logging/metrics
→ state transition.

---

## 96. Error Classification

Ошибка должна быть классифицирована как:

- retryable;
- permanent;
- timeout;
- rate limit;
- validation;
- configuration;
- dependency;
- internal;
- cancellation.

---

## 97. Error Does Not Equal Opportunity

Любая infrastructure error не должна автоматически создавать Opportunity.

---

## 98. Error Does Not Equal Zero

Ошибка получения financial data не должна превращать отсутствующее значение в zero.

---

## 99. Observability Workflow

Critical workflow должен создавать correlation context.

Минимально желательно связывать:

- scan_id;
- candidate_id;
- job_id;
- opportunity_id;
- notification_id.

---

## 100. Critical Invariants

System Workflows никогда не должны:

1. подтверждать Opportunity на основании только Level 1 data;

2. менять Level 2 route/provider pair автоматически;

3. использовать stale critical financial data как fresh;

4. заменять missing fee на zero;

5. заменять missing gas на zero;

6. обходить Resource Manager;

7. обходить Capability Registry;

8. выполнять external request внутри database transaction;

9. отправлять notification до persistence Opportunity;

10. изменять financial snapshot из Notification System;

11. retry expired Job;

12. бесконечно retry permanent errors;

13. создавать duplicate Opportunity при restart;

14. создавать duplicate Notification при retry;

15. считать RUNNING Job успешным после crash;

16. использовать UNKNOWN capability как разрешение operation;

17. позволять одному provider failure остановить всю систему без необходимости;

18. выполнять uncontrolled route substitution;

19. запускать workflow с invalid critical configuration;

20. позволять cleanup удалить active critical state.

---

## 101. Главный принцип

Основной workflow Monik должен оставаться:

**обнаружить → зафиксировать Candidate → перепроверить именно найденную комбинацию → получить свежие данные → пересчитать profit → подтвердить только при выполнении всех условий → сохранить Opportunity → уведомить.**

Ни один subsystem не должен сокращать этот путь за счёт скрытого fallback, stale data, implicit zero, route substitution или обхода установленного architecture boundary.

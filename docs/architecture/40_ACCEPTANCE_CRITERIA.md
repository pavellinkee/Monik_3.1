# MONIK — ACCEPTANCE CRITERIA

## 1. Назначение

Этот документ определяет объективные критерии готовности Monik.

Проект не считается готовым только потому, что application запускается или отдельные tests проходят.

Готовность должна подтверждаться выполнением всех обязательных criteria этого документа.

---

## 2. Главный принцип

Каждый critical requirement должен иметь проверяемый результат.

Формулировки вида:

- «работает хорошо»;
- «достаточно быстро»;
- «должно быть надёжно»

не являются acceptance criteria без измеримого или проверяемого условия.

---

## 3. Architecture Compliance

Перед acceptance необходимо подтвердить:

- architecture documents согласованы;
- interfaces реализованы;
- dependency direction соблюдается;
- infrastructure boundaries соблюдаются;
- state machines реализованы;
- database contracts соблюдаются;
- testing requirements выполнены.

---

## 4. Requirements Compliance

Все обязательные requirements из:

`docs/architecture/01_PROJECT_REQUIREMENTS.md`

должны быть реализованы или иметь explicit approved exception.

---

## 5. No Unapproved Features

В production implementation не должно быть функциональности, которая:

- противоречит requirements;
- изменяет approved architecture;
- добавляет unapproved trading execution;
- добавляет unrelated functionality.

---

## 6. Project Startup

Application должен:

- запускаться из documented command;
- корректно загружать configuration;
- валидировать configuration;
- инициализировать database;
- инициализировать required subsystems.

---

## 7. Invalid Configuration

При invalid critical configuration application должен завершаться безопасно или переходить в соответствующий unavailable state.

Он не должен запускаться как будто configuration valid.

---

## 8. Secret Safety

Acceptance не пройден, если:

- secrets находятся в Git;
- secrets выводятся в logs;
- secrets попадают в errors;
- secrets попадают в notifications;
- production credentials используются в tests.

---

## 9. Database Initialization

Application должен корректно:

- создать/открыть database;
- проверить schema;
- применить необходимые migrations;
- проверить critical constraints.

---

## 10. Database Safety

Database должен иметь protection от:

- test/production confusion;
- invalid schema;
- unsupported migration;
- unsafe concurrent writes.

---

## 11. Repository Boundary

Business logic не должна напрямую обращаться к SQLite или SQL implementation.

---

## 12. Token Registry

Token Registry должен:

- предоставлять canonical token identity;
- возвращать correct decimals;
- различать tokens разных networks;
- поддерживать enabled/disabled state;
- отклонять invalid tokens.

---

## 13. Network Registry

Network information должна иметь stable canonical identity.

Unsupported network не должен использоваться для scanning или confirmation.

---

## 14. Provider Registry

Каждый configured provider должен иметь:

- stable identity;
- enabled state;
- configuration;
- supported operations/networks через capability system.

---

## 15. Capability Registry

Перед provider/network operation application должен проверять соответствующую capability.

UNKNOWN не должен считаться SUPPORTED.

---

## 16. Resource Manager

Все external provider requests должны проходить через Resource Manager.

Acceptance не пройден, если хотя бы один critical provider path обходит Resource Manager.

---

## 17. Resource Limits

Resource Manager должен обеспечивать bounded:

- concurrency;
- queue size;
- retries;
- request timeout.

---

## 18. Rate Limiting

Provider rate limits должны соблюдаться.

Rate limit response не должен приводить к uncontrolled request loop.

---

## 19. Retry

Retry должен:

- выполняться только для retryable errors;
- иметь maximum attempts;
- использовать backoff;
- учитывать expiration;
- не повторять permanent errors бесконечно.

---

## 20. Circuit Breaker

При configured repeated provider failures circuit breaker должен:

- открываться;
- блокировать normal requests;
- выполнять controlled recovery probes;
- возвращаться в normal state после recovery.

---

## 21. Aggregator Adapters

Каждый aggregator adapter должен:

- реализовывать common interface;
- возвращать normalized Quote;
- переводить provider errors;
- валидировать response;
- использовать Resource Manager.

---

## 22. Provider Independence

Failure одного provider не должен автоматически ломать независимые provider paths.

---

## 23. Malformed Provider Response

Malformed response не должен превращаться в valid Quote.

---

## 24. Missing Provider Fields

Missing required provider response fields должны приводить к validation failure.

---

## 25. Quote Freshness

Quote должен содержать достаточную information для определения freshness.

Stale Quote не должен использоваться как fresh.

---

## 26. Route Integrity

Normalized Route должен сохранять существенные параметры исходного provider route.

---

## 27. Level 1 Scanner

Level 1 должен:

1. получить configured scan scope;
2. проверить capabilities;
3. получить quotes;
4. normalize quotes;
5. сравнить valid results;
6. применить preliminary filtering;
7. создать Candidate при выполнении условий.

---

## 28. Level 1 Scope

Level 1 должен использовать configured:

- networks;
- tokens;
- providers;
- amounts.

Не должен самостоятельно расширять scan scope.

---

## 29. Level 1 Candidate

Candidate должен содержать достаточно information для повторной проверки в Level 2.

---

## 30. Candidate Deduplication

Повторный обнаруженный Candidate с тем же canonical fingerprint не должен создавать uncontrolled duplicate.

---

## 31. Candidate Expiration

Expired Candidate не должен переходить в normal confirmation workflow.

---

## 32. Level 1 Does Not Confirm

Level 1 не должен создавать CONFIRMED Opportunity.

---

## 33. Level 2 Job

Для valid Candidate должен создаваться controlled Level 2 Job.

Job должен иметь:

- stable ID;
- Candidate reference;
- state;
- expiration;
- retry metadata.

---

## 34. Level 2 Queue

Queue должна быть bounded.

Queue overflow должен иметь explicit behavior.

---

## 35. Level 2 Exact Combination

Level 2 должен подтверждать именно ту комбинацию, которая была обнаружена Level 1:

- network;
- token pair;
- amount;
- provider pair;
- route.

---

## 36. No Implicit Route Replacement

Level 2 не должен автоматически заменить исходный route на другой route.

---

## 37. Fresh Level 2 Data

Level 2 должен получить fresh required market data перед confirmation.

---

## 38. Fresh Fees

Level 2 должен использовать valid/fresh fee data согласно configured policy.

---

## 39. Fresh Gas

Level 2 должен использовать valid/fresh gas data согласно configured policy.

---

## 40. Profit Calculator

Profit Calculator должен:

- быть deterministic;
- использовать exact financial representation;
- учитывать required costs;
- возвращать normalized ProfitResult.

---

## 41. Missing Financial Data

Missing required:

- quote;
- fee;
- gas;
- conversion data

не должен превращаться в zero.

---

## 42. No False Positive

Если critical financial data неизвестна:

Opportunity не должна быть CONFIRMED.

---

## 43. Profit Correctness

Profit Calculator должен корректно обрабатывать:

- positive profit;
- zero profit;
- negative profit;
- fees;
- gas;
- precision;
- rounding;
- configured thresholds.

---

## 44. Threshold Boundary

Тесты должны подтверждать поведение:

- threshold - smallest valid unit;
- threshold;
- threshold + smallest valid unit.

---

## 45. Financial Snapshot

После confirmation Opportunity должна содержать immutable financial snapshot.

---

## 46. Opportunity Creation

Opportunity может быть создана только после успешного Level 2 confirmation.

---

## 47. Opportunity Uniqueness

Один logical confirmed Job не должен создавать uncontrolled duplicate Opportunity.

---

## 48. Opportunity Persistence

Opportunity должна быть persisted до начала notification delivery.

---

## 49. Opportunity Financial Immutability

Обычный workflow не должен изменять:

- input amount;
- output amount;
- fees;
- gas;
- total costs;
- net profit;
- profit percentage;
- route;
- calculation version.

---

## 50. Notification System

Notification System должен:

- получить confirmed Opportunity;
- определить configured destinations;
- создать Notification;
- выполнить delivery;
- сохранить delivery state.

---

## 51. Notification Does Not Recalculate

Notification System не должен пересчитывать profitability.

---

## 52. Notification Idempotency

Повторная обработка одной logical notification не должна создавать uncontrolled duplicate delivery.

---

## 53. Notification Retry

Temporary delivery failure должен использовать bounded retry.

---

## 54. Notification Permanent Failure

Permanent failure не должен приводить к бесконечному retry.

---

## 55. Notification Partial Success

При нескольких destinations система должна корректно различать:

- all delivered;
- partial delivery;
- all failed.

---

## 56. Scheduler

Scheduler должен:

- запускать configured tasks;
- соблюдать intervals;
- соблюдать overlap policy;
- поддерживать cancellation;
- изолировать failures отдельных tasks.

---

## 57. Scheduler Business Logic

Scheduler не должен содержать business logic Level 1, Level 2 или Profit Calculator.

---

## 58. Scan Frequency

Level 1 scan frequency должна соответствовать approved configuration.

Не должно существовать скрытых дополнительных scan loops.

---

## 59. Database Transactions

Critical state changes должны быть atomic.

---

## 60. External Requests and Transactions

HTTP/provider/Telegram requests не должны удерживаться внутри database transactions.

---

## 61. State Machines

Все critical lifecycle transitions должны соответствовать:

`docs/architecture/35_STATE_MACHINES.md`

---

## 62. Invalid State Transition

Каждый forbidden transition должен быть rejected.

---

## 63. Terminal States

Terminal states не должны изменяться обычным background workflow.

---

## 64. Concurrent State Changes

Два concurrent workers не должны оба успешно изменить один incompatible critical state.

---

## 65. Restart Recovery

После restart система должна корректно восстановить:

- Jobs;
- pending Notifications;
- required operational state.

---

## 66. RUNNING Job Recovery

RUNNING Job после crash не должен автоматически считаться successful.

---

## 67. Duplicate Prevention After Restart

Restart не должен создавать duplicate:

- Opportunities;
- Notifications;
- Jobs.

---

## 68. Graceful Shutdown

Application должен иметь controlled shutdown.

Он должен прекращать новые operations и сохранять необходимое state.

---

## 69. Forced Shutdown Recovery

После forced shutdown система должна иметь возможность восстановить persisted operational state.

---

## 70. Error Handling

Все critical errors должны проходить normalized error handling.

---

## 71. Error Classification

Ошибки должны различать:

- retryable;
- permanent;
- timeout;
- rate limit;
- validation;
- configuration;
- cancellation;
- dependency;
- internal.

---

## 72. Observability

Critical workflows должны иметь:

- structured logs;
- relevant metrics;
- correlation IDs;
- state transition diagnostics.

---

## 73. Secret Redaction

Ни один secret не должен появляться в observability output.

---

## 74. Health Monitoring

Health Monitoring должен корректно отражать:

- startup;
- healthy;
- degraded;
- unavailable;
- stopping.

---

## 75. Degraded Mode

Optional component failure может приводить к DEGRADED, если critical safety requirements продолжают выполняться.

---

## 76. Critical Failure

Critical subsystem failure должен предотвращать unsafe operation.

---

## 77. Configuration Reload

Если runtime reload поддерживается:

invalid configuration не должна заменять текущую valid configuration.

---

## 78. Architecture Boundaries

Acceptance не пройден, если:

- Scanner импортирует SQLite;
- Scanner импортирует Telegram;
- Scanner использует raw HTTP;
- Profit Calculator использует external APIs;
- business logic читает environment variables;
- provider SDK проникает в domain models.

---

## 79. Testing Requirements

Должны существовать и проходить:

- unit tests;
- contract tests;
- integration tests;
- security tests;
- recovery tests;
- E2E tests.

---

## 80. Financial Regression Tests

Любое изменение financial logic должно проходить regression tests для:

- fees;
- gas;
- precision;
- rounding;
- thresholds;
- positive/negative profit.

---

## 81. Provider Contract Tests

Каждый provider adapter должен проходить contract tests.

---

## 82. Architecture Tests

CI должен проверять critical dependency boundaries.

---

## 83. Security Tests

Минимально должны быть проверены:

- SSRF;
- SQL injection;
- path traversal;
- secret exposure;
- environment isolation;
- unsafe URLs.

---

## 84. Performance

Система должна сохранять bounded resource usage при configured workload.

---

## 85. No Unbounded Growth

Не допускается uncontrolled growth:

- queues;
- retries;
- memory;
- database temporary data;
- logs.

---

## 86. Documentation

Перед acceptance должны быть согласованы:

- CLAUDE.md;
- README.md;
- architecture documents;
- API Contracts;
- Interfaces;
- State Machines;
- Data Models;
- Implementation Plan.

---

## 87. Documentation Consistency

Не должно существовать двух conflicting authoritative definitions одного critical behavior.

---

## 88. Code Quality

Перед acceptance:

- formatter проходит;
- linter проходит;
- type checker проходит;
- tests проходят;
- no unexplained critical warnings.

---

## 89. Dependency Security

Dependencies должны быть проверены на известные critical vulnerabilities согласно используемому security tooling.

---

## 90. Production Configuration

Production configuration должна быть:

- validated;
- isolated;
- secret-safe;
- documented.

---

## 91. Backup

Если backup предусмотрен architecture:

должен существовать проверенный backup/restore workflow.

---

## 92. Recovery Drill

Перед production readiness необходимо выполнить хотя бы один controlled recovery test.

---

## 93. End-to-End Acceptance

Минимальный успешный сценарий:

Level 1
→ Candidate
→ Level 2 Job
→ fresh quote/fees/gas
→ Profit Calculator
→ confirmed Opportunity
→ persisted Opportunity
→ Notification.

---

## 94. End-to-End Rejection

Минимальный negative scenario:

Level 1
→ Candidate
→ Level 2
→ fresh data
→ profitability condition not met
→ no Opportunity.

---

## 95. End-to-End Stale Data

Scenario:

Candidate
→ Level 2
→ stale critical data
→ no confirmation.

---

## 96. End-to-End Provider Failure

Scenario:

Candidate
→ Level 2
→ provider failure
→ no false confirmation.

---

## 97. End-to-End Notification Failure

Scenario:

confirmed Opportunity
→ notification failure
→ Opportunity financial snapshot remains intact.

---

## 98. End-to-End Restart

Scenario:

active Job/Notification
→ application restart
→ state recovery
→ no duplicate financial result.

---

## 99. Final Production Gate

Monik может считаться production-ready только если:

- all mandatory acceptance criteria выполнены;
- critical tests passed;
- security checks passed;
- recovery verified;
- architecture boundaries verified;
- documentation synchronized;
- no unresolved critical issues.

---

## 100. Acceptance Sign-off

Перед production deployment должен быть зафиксирован итог:

- PASS;
- PASS WITH APPROVED EXCEPTIONS;
- NOT READY.

Любое exception должно иметь explicit description и approval.

---

## 101. Critical Invariants

Acceptance никогда не может считаться успешным, если:

1. существует false-positive confirmation;

2. stale critical data может привести к CONFIRMED;

3. missing fee/gas может превратиться в zero;

4. Level 2 меняет обнаруженную комбинацию без explicit rule;

5. external requests обходят Resource Manager;

6. business logic напрямую использует infrastructure;

7. financial snapshot изменяется после confirmation;

8. duplicate Opportunity может создаваться из-за retry/restart;

9. duplicate Notification может бесконтрольно отправляться;

10. production secrets присутствуют в Git;

11. production database может использоваться тестами;

12. critical state transitions не защищены от concurrency;

13. RUNNING state после crash считается successful;

14. required tests отсутствуют;

15. architecture documents противоречат implementation;

16. Claude Code может самостоятельно изменить critical architecture без approval.

---

## 102. Главный принцип

Monik считается готовым не тогда, когда **«код работает»**, а тогда, когда:

**требования выполнены → архитектура соблюдена → financial logic проверена → external failures обработаны → state recovery проверен → security проверена → полный workflow протестирован → документация соответствует implementation.**

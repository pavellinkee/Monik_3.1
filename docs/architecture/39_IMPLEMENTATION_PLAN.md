# MONIK — IMPLEMENTATION PLAN

## 1. Назначение

Этот документ определяет обязательный порядок реализации Monik.

Цель:

- реализовывать систему последовательно;
- соблюдать архитектурные зависимости;
- не создавать код до определения необходимых contracts;
- минимизировать rework;
- обеспечить возможность тестирования каждого этапа;
- не допускать преждевременной реализации Level 1/Level 2 до готовности foundation.

---

## 2. Главный принцип

Реализация выполняется снизу вверх по dependency graph.

Нельзя начинать с Level 1 или Level 2 только потому, что это основные функции системы.

Сначала должны быть готовы необходимые:

- models;
- contracts;
- configuration;
- database;
- infrastructure boundaries;
- registries;
- resource controls.

---

## 3. Implementation Order

Рекомендуемый порядок:

1. project foundation;
2. configuration;
3. domain models;
4. database;
5. repositories;
6. registries;
7. error handling;
8. resource manager;
9. aggregator adapters;
10. fee/gas system;
11. profit calculator;
12. Level 1;
13. Level 2;
14. scheduler;
15. notification system;
16. health/observability;
17. integration;
18. final testing;
19. deployment preparation.

---

## 4. Phase 0 — Project Foundation

Сначала необходимо проверить:

- repository structure;
- Python version;
- dependency management;
- test framework;
- linting;
- formatting;
- type checking;
- Git workflow;
- CLAUDE.md;
- architecture documentation.

---

## 5. Foundation Completion Criteria

Phase 0 считается завершённой, когда:

- project запускается;
- test runner запускается;
- linting работает;
- formatting работает;
- type checking настроен;
- базовая структура проекта соответствует Project Structure document.

---

## 6. Phase 1 — Configuration

Реализовать:

- configuration loader;
- environment overrides;
- validation;
- normalization;
- defaults;
- secret references;
- environment isolation.

---

## 7. Configuration Tests

До перехода дальше должны проходить:

- valid configuration;
- invalid configuration;
- missing required values;
- environment override;
- production safety;
- secret redaction tests.

---

## 8. Phase 2 — Domain Models

Реализовать canonical models:

- Network;
- Token;
- Token Amount;
- Provider;
- Route;
- Quote;
- Fee;
- Gas;
- ProfitResult;
- Candidate;
- Level 2 Job;
- Opportunity;
- Notification;
- Capability;
- Health;
- normalized Error.

---

## 9. Domain Model Rule

На этом этапе нельзя добавлять provider-specific business logic в domain models.

---

## 10. Domain Tests

До перехода дальше должны проходить:

- validation;
- serialization;
- exact numeric behavior;
- identity;
- equality/fingerprint;
- state-related validation.

---

## 11. Phase 3 — Database

Реализовать:

- database initialization;
- schema;
- migrations;
- indexes;
- constraints;
- transaction support;
- backup/restore mechanism, если включён.

---

## 12. Database Safety

Database implementation должна иметь защиту от:

- production/test confusion;
- invalid migrations;
- missing constraints;
- unsafe concurrent writes.

---

## 13. Phase 4 — Repositories

Реализовать Repository interfaces и concrete implementations для необходимых сущностей.

Минимально:

- Token;
- Candidate;
- Job;
- Opportunity;
- Notification;
- Fee;
- Capability.

---

## 14. Repository Rule

Repositories не принимают business decisions.

Они отвечают за persistence и retrieval.

---

## 15. Repository Tests

Обязательно протестировать:

- create;
- read;
- update;
- filtering;
- deduplication;
- state persistence;
- transactions;
- rollback;
- constraints.

---

## 16. Phase 5 — Registries

Реализовать:

- Token Registry;
- Network Registry, если выделен;
- Capability Registry;
- Provider Registry, если предусмотрен architecture.

---

## 17. Registry Rule

Registry должен быть authoritative source для соответствующего типа данных.

Не создавать параллельные источники canonical token/provider/network information.

---

## 18. Phase 6 — Error Handling

Реализовать:

- normalized errors;
- error codes;
- categories;
- retryability;
- severity;
- infrastructure error translation.

---

## 19. Error Handling Tests

Проверить:

- provider errors;
- HTTP errors;
- timeout;
- rate limit;
- validation;
- database errors;
- cancellation;
- internal errors.

---

## 20. Phase 7 — Resource Manager

Реализовать central Resource Manager.

Минимально:

- concurrency limits;
- queue limits;
- provider limits;
- network limits;
- timeout;
- retry;
- backoff;
- jitter;
- circuit breaker;
- cancellation.

---

## 21. Resource Manager Rule

После завершения этой phase ни один external provider request не должен выполняться в обход Resource Manager.

---

## 22. Resource Manager Tests

Проверить:

- concurrency;
- queue overflow;
- timeout;
- retry;
- backoff;
- rate limit;
- circuit breaker;
- cancellation;
- recovery.

---

## 23. Phase 8 — HTTP Infrastructure

Реализовать controlled HTTP client abstraction.

Он должен обеспечивать:

- timeout;
- TLS verification;
- response limits;
- redirect policy;
- normalized transport errors.

---

## 24. HTTP Rule

Business services не должны получать raw HTTP implementation.

---

## 25. Phase 9 — Aggregator Adapters

Реализовать adapters для утверждённых providers.

Каждый adapter должен:

- реализовать common interface;
- использовать Resource Manager;
- преобразовывать provider response в normalized Quote;
- переводить provider errors;
- поддерживать соответствующие networks.

---

## 26. Adapter Order

Каждый provider реализуется независимо.

Ошибка одного adapter не должна требовать изменения остальных adapters.

---

## 27. Adapter Contract Tests

Каждый adapter должен пройти:

- valid response;
- malformed response;
- missing fields;
- invalid amounts;
- timeout;
- rate limit;
- authentication error;
- provider error;
- normalization tests.

---

## 28. Phase 10 — Fee System

Реализовать:

- Fee Provider interfaces;
- Fee normalization;
- Fee freshness;
- persistence;
- refresh;
- error handling.

---

## 29. Phase 11 — Gas System

Если Gas реализован отдельно:

реализовать:

- Gas Provider;
- normalization;
- freshness;
- persistence;
- refresh;
- conversion.

---

## 30. Financial Data Rule

До перехода к Level 1/Level 2 должны существовать безопасные способы получения:

- quotes;
- fees;
- gas;
- required conversion data.

---

## 31. Phase 12 — Profit Calculator

Реализовать Profit Calculator как deterministic domain/application component.

---

## 32. Profit Calculator Restrictions

Profit Calculator не должен:

- делать HTTP requests;
- читать provider APIs;
- читать Telegram;
- обращаться к database за hidden data;
- самостоятельно искать routes.

---

## 33. Profit Calculator Tests

Обязательно протестировать:

- profitable;
- unprofitable;
- zero profit;
- negative profit;
- fees;
- gas;
- precision;
- rounding;
- token decimals;
- missing data;
- stale data;
- threshold boundaries.

---

## 34. Phase 13 — Level 1 Scanner

После готовности infrastructure реализовать Level 1.

---

## 35. Level 1 Dependencies

Level 1 должен использовать:

- Configuration;
- Token Registry;
- Capability Registry;
- Resource Manager;
- Aggregator Adapters;
- Profit/financial helpers, если предусмотрено;
- Candidate Repository;
- Clock.

---

## 36. Level 1 Responsibilities

Level 1 должен:

1. определить scan scope;
2. проверить capabilities;
3. получить quotes;
4. normalize quotes;
5. сравнить valid results;
6. применить preliminary filtering;
7. создать Candidate;
8. сохранить Candidate;
9. передать Candidate в Level 2.

---

## 37. Level 1 Restrictions

Level 1 не должен:

- подтверждать Opportunity;
- отправлять Telegram;
- обходить Resource Manager;
- напрямую работать с SQLite;
- самостоятельно реализовывать provider-specific parsing.

---

## 38. Phase 14 — Level 2 Scanner

Level 2 реализуется только после готовности:

- Candidate model;
- Job state machine;
- Resource Manager;
- Aggregator Adapters;
- Fee System;
- Gas System;
- Profit Calculator;
- repositories.

---

## 39. Level 2 Responsibilities

Level 2 должен:

1. получить Candidate;
2. создать/обработать Job;
3. проверить expiration;
4. проверить capabilities;
5. проверить именно исходную route;
6. получить fresh quote;
7. получить fresh fees;
8. получить fresh gas;
9. вызвать Profit Calculator;
10. принять confirmation/rejection decision;
11. создать Opportunity при success.

---

## 40. Level 2 Route Rule

Level 2 не должен автоматически заменять route/provider pair, обнаруженные Level 1.

Любое изменение route является отдельной архитектурной функцией и не является implicit fallback.

---

## 41. Level 2 Confirmation Rule

CONFIRMED допускается только при наличии всех required valid и fresh financial inputs.

---

## 42. Phase 15 — Opportunity Service

Реализовать:

- immutable financial snapshot;
- persistence;
- idempotency;
- state transition;
- duplicate protection.

---

## 43. Opportunity Rule

Opportunity должна быть сохранена до начала notification delivery.

---

## 44. Phase 16 — Notification System

Реализовать:

- Notification Service;
- destination management;
- Telegram adapter;
- formatting;
- persistence;
- retry;
- deduplication;
- delivery states.

---

## 45. Notification Restrictions

Notification System не должна:

- пересчитывать profit;
- менять financial snapshot;
- выбирать другой route;
- выполнять arbitrage logic.

---

## 46. Phase 17 — Scheduler

Scheduler реализуется после готовности основных services.

Scheduler должен запускать:

- Level 1 scans;
- fee refresh;
- capability refresh;
- cleanup;
- health checks;
- notification retries;
- maintenance tasks.

---

## 47. Scheduler Rule

Scheduler координирует timing, но не содержит business logic.

---

## 48. Phase 18 — Health Monitoring

Реализовать:

- health states;
- subsystem health;
- provider health;
- database health;
- recovery detection;
- degraded state.

---

## 49. Health Rule

Health Monitoring не должен изменять business state.

---

## 50. Phase 19 — Observability

Реализовать:

- structured logging;
- metrics;
- correlation IDs;
- state transition events;
- important workflow diagnostics.

---

## 51. Observability Security

Не допускать попадания в observability data:

- API keys;
- passwords;
- private keys;
- tokens/secrets;
- sensitive credentials.

---

## 52. Phase 20 — Integration

После завершения отдельных subsystem соединить:

Level 1
→ Candidate
→ Level 2
→ Profit Calculator
→ Opportunity
→ Notification.

---

## 53. Integration Rule

Integration должна использовать реальные production-like interfaces, но controlled test infrastructure.

---

## 54. Integration Tests

Проверить полный workflow:

- successful opportunity;
- unprofitable candidate;
- stale quote;
- missing fee;
- missing gas;
- provider timeout;
- provider rate limit;
- retry;
- expiration;
- cancellation.

---

## 55. Phase 21 — Recovery

Проверить restart в critical points:

- после Candidate creation;
- после Job creation;
- во время Job execution;
- после Opportunity persistence;
- во время notification;
- во время retry.

---

## 56. Recovery Rule

Restart не должен создавать duplicate:

- Candidate;
- Job;
- Opportunity;
- Notification.

---

## 57. Phase 22 — Security Validation

Перед production preparation выполнить:

- input validation;
- SSRF tests;
- path traversal tests;
- SQL injection tests;
- secret redaction;
- configuration isolation;
- dependency security checks.

---

## 58. Phase 23 — Performance Validation

Проверить:

- Level 1 throughput;
- Level 2 queue behavior;
- Resource Manager limits;
- database performance;
- notification throughput;
- memory usage.

---

## 59. Performance Rule

Performance optimization не должна нарушать financial correctness или architecture boundaries.

---

## 60. Phase 24 — Full Test Suite

Запустить полный test suite:

1. unit;
2. contract;
3. integration;
4. security;
5. recovery;
6. E2E;
7. performance checks.

---

## 61. CI Requirements

CI должен проверять минимум:

- formatting;
- linting;
- type checking;
- unit tests;
- contract tests;
- integration tests;
- security checks.

---

## 62. Phase 25 — Documentation Validation

Перед deployment проверить соответствие:

- CLAUDE.md;
- README.md;
- architecture documents;
- API contracts;
- interfaces;
- state machines;
- database schema;
- implementation.

---

## 63. Documentation Rule

Если implementation противоречит architecture document:

нельзя автоматически считать implementation правильной.

Сначала необходимо определить, что является authoritative source и устранить противоречие.

---

## 64. Phase 26 — Deployment Preparation

Подготовить:

- production configuration;
- secret references;
- database location;
- backup;
- logging;
- monitoring;
- health checks;
- startup;
- shutdown;
- recovery.

---

## 65. Deployment Safety

Production deployment не должен использовать:

- test credentials;
- development defaults;
- test database;
- uncontrolled debug settings.

---

## 66. Phase 27 — Production Readiness

Перед первым production запуском подтвердить:

- configuration valid;
- database initialized;
- migrations applied;
- providers configured;
- capabilities valid;
- Resource Manager limits configured;
- Level 1 tested;
- Level 2 tested;
- notifications tested;
- recovery tested;
- security tests passed;
- observability enabled.

---

## 67. Implementation Dependency Graph

Критические зависимости:

`Configuration`
→ `Domain Models`
→ `Database`
→ `Repositories`

`Registries`
→ `Provider Adapters`

`Resource Manager`
→ `Provider Adapters`

`Fee/Gas`
→ `Profit Calculator`

`Provider Adapters + Registries + Resource Manager`
→ `Level 1`

`Level 1 + Fee/Gas + Profit Calculator`
→ `Level 2`

`Level 2`
→ `Opportunity`

`Opportunity`
→ `Notification`

`All operational services`
→ `Scheduler`

`All critical services`
→ `Health + Observability`

---

## 68. No Premature Implementation

Нельзя реализовывать subsystem до готовности его critical dependencies, если это приводит к temporary architecture bypass.

Temporary bypass не должен попадать в production code.

---

## 69. Temporary Mocks

Для разработки допускаются mocks/fakes.

Но они должны быть заменены или формально закреплены как test implementations до production.

---

## 70. Incremental Integration

После завершения каждой major phase необходимо:

1. написать tests;
2. запустить tests;
3. проверить architecture boundaries;
4. только после этого переходить к следующей phase.

---

## 71. Regression Rule

Изменение одного subsystem требует запуска связанных contract/integration tests.

---

## 72. Breaking Change Rule

Если изменение ломает existing contract:

необходимо сначала обновить:

- interface;
- consumers;
- tests;
- documentation.

---

## 73. Database Migration Rule

Изменение persistent models должно сопровождаться database migration.

---

## 74. State Machine Rule

Изменение lifecycle state требует синхронного изменения:

- state machine;
- database constraints;
- services;
- tests;
- documentation.

---

## 75. Financial Rule

Любое изменение, способное повлиять на:

- amount;
- fee;
- gas;
- profit;
- route;

требует дополнительных financial regression tests.

---

## 76. Provider Rule

Добавление provider должно требовать:

- adapter;
- capability configuration;
- contract tests;
- error mapping;
- documentation;
- integration tests.

---

## 77. Network Rule

Добавление network должно требовать проверки:

- Token Registry;
- Capability Registry;
- provider support;
- gas;
- configuration;
- tests.

---

## 78. Notification Destination Rule

Добавление destination не должно требовать изменения Opportunity financial logic.

---

## 79. Feature Flag Rule

Feature flags могут использоваться для безопасного rollout.

Но feature flag не должен обходить required validation или security controls.

---

## 80. Code Review Rule

Перед merge необходимо проверить:

- architecture;
- correctness;
- security;
- tests;
- observability;
- documentation.

---

## 81. Claude Code Rule

Claude Code должен реализовывать систему в соответствии с:

1. `CLAUDE.md`;
2. `docs/architecture/01_PROJECT_REQUIREMENTS.md`;
3. соответствующими architecture documents;
4. API Contracts;
5. Interfaces;
6. State Machines;
7. Testing requirements.

При конфликте документов Claude Code не должен самостоятельно выбирать произвольный вариант.

Он должен остановиться и запросить решение.

---

## 82. No Architecture Invention

Claude Code не должен самостоятельно:

- менять архитектуру;
- добавлять новый provider;
- менять route policy;
- менять financial formula;
- менять state machine;
- добавлять новый persistence mechanism;

без explicit approval.

---

## 83. No Scope Expansion

Implementation должна соответствовать утверждённым requirements.

Не добавлять:

- trading execution;
- automatic swaps;
- portfolio management;
- unrelated UI;
- unrelated APIs;

если они не входят в approved scope.

---

## 84. Implementation Completion

Implementation считается завершённой только после:

- implementation;
- unit tests;
- integration tests;
- contract tests;
- security validation;
- recovery validation;
- documentation update.

---

## 85. Final Verification

Перед передачей проекта в production/Claude Code необходимо проверить:

- все required files существуют;
- architecture documents согласованы;
- interfaces согласованы;
- models согласованы;
- workflows согласованы;
- state machines согласованы;
- tests согласованы;
- no duplicate authoritative documents;
- no unresolved contradictions.

---

## 86. Critical Invariants

Implementation Plan никогда не должен позволять:

1. начинать Level 1 до готовности его critical dependencies;

2. начинать Level 2 до готовности financial infrastructure;

3. обходить Resource Manager;

4. обходить Repository layer;

5. обходить Capability Registry;

6. использовать temporary architecture bypass в production;

7. менять financial logic без regression tests;

8. менять state machine без migration/tests;

9. добавлять provider без contract tests;

10. добавлять network без capability validation;

11. передавать production secrets в development;

12. использовать test database в production;

13. считать passing unit tests достаточными для production readiness;

14. изменять architecture без explicit approval;

15. позволять Claude Code самостоятельно расширять scope.

---

## 87. Главный принцип

Monik должен реализовываться последовательно:

**foundation → contracts → infrastructure → financial core → Level 1 → Level 2 → notifications → scheduling → observability → integration → recovery → security → deployment.**

Каждый следующий этап должен опираться на уже проверенный предыдущий этап, а не создавать временные обходы архитектуры.

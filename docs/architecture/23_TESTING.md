# MONIK — TESTING

## 1. Назначение

Testing определяет единую стратегию автоматического тестирования Monik.

Цель:

- предотвращать регрессии;
- проверять архитектурные boundaries;
- подтверждать корректность финансовых расчётов;
- проверять отказоустойчивость;
- проверять взаимодействие subsystems;
- обеспечивать безопасное изменение production code.

---

## 2. Главный принцип

Каждая критическая subsystem должна быть тестируема независимо.

Тесты не должны требовать запуска всей системы, если проверяется отдельная функция или subsystem.

---

## 3. Test Layers

Monik должен использовать несколько уровней тестирования:

- unit tests;
- component tests;
- contract tests;
- integration tests;
- failure tests;
- recovery tests;
- architecture tests;
- end-to-end tests.

---

## 4. Unit Tests

Unit tests проверяют отдельные функции, классы и небольшие components.

Они должны быть:

- быстрыми;
- deterministic;
- изолированными;
- независимыми от Internet.

---

## 5. Component Tests

Component tests проверяют отдельную subsystem целиком с controlled dependencies.

Например:

- Level 1 Scanner;
- Level 2 Scanner;
- Resource Manager;
- Fee System;
- Notification System.

---

## 6. Contract Tests

Contract tests проверяют соответствие Adapter и domain API contracts.

Они особенно важны для:

- 1inch;
- 0x;
- Velora;
- Uniswap;
- Telegram Adapter.

---

## 7. Integration Tests

Integration tests проверяют взаимодействие нескольких реальных subsystems.

Минимально:

Level 1
→ Level 2
→ Profit Calculator
→ Notification System.

---

## 8. End-to-End Tests

E2E tests проверяют полный production-like workflow:

configuration
→ startup
→ scheduler
→ Level 1
→ Level 2
→ calculation
→ confirmation
→ notification.

---

## 9. No Real Trading

Никакой тест не должен выполнять реальный swap или отправлять real trading transaction.

На текущем этапе trading execution вообще отсутствует.

---

## 10. No Production Credentials

Automated tests никогда не должны использовать production credentials.

---

## 11. No Real Telegram by Default

Tests Notification System должны использовать mock Telegram Adapter.

Реальный Telegram integration test допускается только как explicit opt-in test.

---

## 12. No Uncontrolled External APIs

Unit/component tests не должны выполнять реальные external API requests.

Для них используются:

- mocks;
- fixtures;
- fake adapters;
- recorded responses.

---

## 13. External Integration Tests

Реальные provider API tests могут существовать отдельно.

Они должны быть:

- explicit;
- ограниченными;
- configuration-controlled;
- защищёнными от excessive requests.

---

## 14. Test Environment

Production configuration не должна использоваться для tests.

Test environment должен иметь собственные:

- database;
- configuration;
- credentials;
- fixtures;
- logs.

---

## 15. Test Database

Integration tests должны использовать отдельную SQLite database.

Production database никогда не используется тестами.

---

## 16. Database Isolation

Каждый test suite должен иметь возможность:

- создать test database;
- очистить state;
- применить migrations;
- проверить результаты.

---

## 17. Deterministic Tests

Тесты не должны зависеть от:

- текущей цены токена;
- текущего gas;
- случайного provider response;
- текущего времени без controlled clock;
- внешнего network state.

---

## 18. Time Control

Scheduler, expiration и freshness tests должны иметь возможность использовать controlled/fake clock.

---

## 19. Randomness

Если используется randomness:

test должен иметь возможность задать deterministic seed.

---

## 20. Decimal Tests

Все financial calculations должны иметь tests на:

- Decimal precision;
- rounding;
- very small values;
- large values;
- zero;
- negative;
- exact equality.

---

## 21. Floating Point Protection

Architecture tests должны предотвращать использование binary Float в financial domain models.

---

## 22. Token Registry Tests

Обязательно тестировать:

- valid token;
- invalid address;
- duplicate token;
- decimals;
- network;
- disabled token;
- unknown token;
- token identity.

---

## 23. Capability Registry Tests

Обязательно тестировать:

- supported;
- unsupported;
- unknown;
- degraded;
- unavailable;
- expiration;
- refresh;
- recovery;
- configuration restrictions.

---

## 24. Aggregator Adapter Tests

Для каждого provider adapter тестировать:

- valid quote;
- invalid quote;
- missing fields;
- malformed response;
- unsupported pair;
- timeout;
- rate limit;
- authentication failure;
- provider error;
- response normalization.

---

## 25. Quote Normalization Tests

Один и тот же normalized quote contract должен корректно формироваться из каждого provider response.

---

## 26. Quote Freshness Tests

Тестировать:

- fresh quote;
- stale quote;
- expired quote;
- missing timestamp;
- invalid timestamp.

---

## 27. Resource Manager Tests

Обязательно тестировать:

- concurrency;
- rate limits;
- priority;
- retry;
- timeout;
- backoff;
- jitter;
- cancellation;
- queue capacity;
- request deduplication;
- circuit breaker.

---

## 28. Priority Tests

Проверить, что Level 2 requests получают priority над обычными Level 1 requests при ограниченной capacity.

---

## 29. Retry Tests

Проверить:

- retryable error;
- non-retryable error;
- max attempts;
- backoff;
- Retry-After;
- retry exhaustion.

---

## 30. No Retry Storm

Test должен гарантировать отсутствие uncontrolled nested retries.

---

## 31. Fee System Tests

Обязательно тестировать:

- fee loading;
- normalization;
- freshness;
- expiration;
- unknown fee;
- included-in-quote;
- duplicate fee prevention;
- scheduled refresh;
- startup refresh.

---

## 32. Gas Tests

Тестировать:

- valid gas;
- stale gas;
- missing gas;
- conversion;
- invalid gas;
- network-specific gas.

---

## 33. Profit Calculator Tests

Profit Calculator должен иметь наиболее строгий набор tests.

Обязательно:

- zero profit;
- positive profit;
- negative profit;
- fees;
- gas;
- rebates;
- multiple costs;
- included fees;
- double-count protection;
- Decimal precision;
- threshold;
- invalid inputs;
- unknown costs.

---

## 34. Profit Formula Tests

Каждая financial formula должна иметь explicit expected-value tests.

---

## 35. Golden Test Cases

Необходимо иметь набор фиксированных golden cases:

input
→ costs
→ output
→ expected profit.

Изменение результата golden case должно требовать осознанного изменения теста.

---

## 36. Level 1 Tests

Обязательно тестировать:

- token filtering;
- network filtering;
- provider filtering;
- capability filtering;
- amount combinations;
- quote requests;
- quote normalization;
- preliminary profitability;
- candidate creation;
- candidate fingerprint;
- deduplication;
- ranking;
- expiration;
- queue limits;
- partial scan;
- provider failures;
- scan overlap.

---

## 37. Level 1 No-Notification Test

Level 1 test должен гарантировать:

Level 1 не отправляет Telegram notification напрямую.

---

## 38. Level 1 No-Bypass Test

Architecture/component test должен гарантировать:

Level 1 не обходит Resource Manager.

---

## 39. Level 2 Tests

Обязательно тестировать:

- Job validation;
- fresh quotes;
- route consistency;
- provider consistency;
- token consistency;
- network consistency;
- fee freshness;
- gas;
- profitability;
- threshold;
- confirmation snapshot;
- expiration;
- retry;
- duplicate Jobs;
- cancellation.

---

## 40. Level 2 Fresh Data Test

Тест должен гарантировать:

Level 2 не использует Level 1 quote вместо required fresh quote.

---

## 41. Level 2 No-False-Positive Test

Если critical data отсутствует:

Level 2 не может вернуть CONFIRMED.

---

## 42. Notification Tests

Обязательно тестировать:

- confirmed opportunity;
- formatting;
- precision;
- language;
- destination;
- duplicate detection;
- queue;
- retry;
- rate limit;
- permanent error;
- temporary error;
- recovery;
- multiple destinations.

---

## 43. Notification No-Recalculation Test

Тест должен гарантировать:

Notification System не изменяет final profit.

---

## 44. Database Tests

Обязательно тестировать:

- initialization;
- migrations;
- rollback;
- transactions;
- unique constraints;
- foreign keys;
- indexes;
- retention;
- cleanup;
- recovery;
- locking;
- integrity;
- backup/restore.

---

## 45. Migration Tests

Для каждой migration должен существовать тест:

old schema
→ migration
→ expected schema.

---

## 46. Configuration Tests

Обязательно тестировать:

- valid configuration;
- missing fields;
- invalid types;
- invalid ranges;
- invalid enums;
- invalid timezone;
- invalid amounts;
- cross-field validation;
- environment overrides;
- secret references;
- reload;
- rollback.

---

## 47. Security Tests

Обязательно тестировать:

- secret redaction;
- SQL injection;
- path traversal;
- malformed input;
- oversized responses;
- unsafe URLs;
- credential failures;
- sensitive data leakage.

---

## 48. Scheduler Tests

Обязательно тестировать:

- startup tasks;
- daily tasks;
- interval tasks;
- manual tasks;
- timezone;
- overlap;
- skip policy;
- retry;
- failure;
- cancellation;
- shutdown;
- recovery.

---

## 49. Scheduler Time Tests

Scheduler tests должны использовать controlled clock.

Не использовать реальные ожидания в минутах для обычных automated tests.

---

## 50. Health Monitoring Tests

Обязательно тестировать:

- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STARTING;
- STOPPING;
- provider failure;
- provider recovery;
- stale health;
- queue saturation;
- database failure.

---

## 51. Error Handling Tests

Обязательно тестировать:

- error classification;
- severity;
- retryability;
- propagation;
- normalization;
- recovery;
- circuit breaker;
- cancellation;
- critical failure.

---

## 52. API Contract Tests

Для каждого normalized contract тестировать:

- required fields;
- types;
- enums;
- Decimal representation;
- timestamps;
- serialization;
- validation;
- backward compatibility.

---

## 53. Architecture Tests

Architecture tests должны проверять утверждённые boundaries.

Минимально запрещать:

- Scanner → direct HTTP;
- Scanner → Telegram;
- Notification → Aggregator API;
- Profit Calculator → provider API;
- business logic → arbitrary SQL;
- provider-specific models → domain layer.

---

## 54. Dependency Direction

Architecture tests должны контролировать направление dependencies.

Высокоуровневые business modules не должны зависеть от конкретных infrastructure implementations без abstraction boundary.

---

## 55. Adapter Isolation Test

Provider-specific implementation должна быть изолирована Adapter layer.

Добавление нового provider не должно требовать изменения Profit Calculator.

---

## 56. Provider Independence Test

Отключение одного provider не должно ломать остальные provider adapters.

---

## 57. Network Independence Test

Отключение одной network не должно ломать остальные enabled networks.

---

## 58. Failure Injection

Тестовая архитектура должна позволять искусственно создавать:

- timeout;
- provider error;
- rate limit;
- database lock;
- stale quote;
- missing fee;
- Telegram failure.

---

## 59. Recovery Tests

После simulated restart необходимо проверять:

- database state;
- Level 2 jobs;
- confirmed opportunities;
- notification state;
- scheduler state.

---

## 60. Crash Tests

Критические workflow должны тестироваться с simulated crash:

- до transaction;
- во время transaction;
- после confirmation;
- перед notification;
- во время notification.

---

## 61. Idempotency Tests

Повторное выполнение одной operation должно приводить к корректному результату.

Особенно:

- candidate creation;
- Level 2 confirmation;
- notification delivery;
- database writes.

---

## 62. Deduplication Tests

Одинаковые:

- candidates;
- Jobs;
- opportunities;
- notifications

не должны создавать uncontrolled duplicates.

---

## 63. Concurrency Tests

Необходимо тестировать concurrent operations:

- multiple Level 1 tasks;
- multiple Level 2 jobs;
- multiple notifications;
- simultaneous database access.

---

## 64. Race Condition Tests

Особое внимание:

- Job state transitions;
- notification state transitions;
- deduplication;
- scheduler overlap;
- database writes.

---

## 65. Load Tests

Load testing должно оценивать:

- scanner throughput;
- Resource Manager capacity;
- Level 2 backlog;
- notification queue;
- database performance.

---

## 66. Load Test Safety

Load tests не должны использовать production providers или production credentials без explicit isolated environment.

---

## 67. Stress Tests

Stress tests должны проверять поведение при:

- provider outage;
- high request volume;
- full queues;
- database contention;
- repeated errors.

---

## 68. Performance Baselines

Для критических components должны существовать baseline metrics.

Минимально:

- Level 1 scan duration;
- Level 2 confirmation latency;
- quote normalization latency;
- database query latency;
- notification delivery latency.

---

## 69. Regression Tests

Каждая найденная production bug должна по возможности получать regression test.

---

## 70. Test Naming

Test names должны описывать:

condition → expected result.

Например:

provider_timeout_does_not_create_candidate

---

## 71. Test Independence

Тесты не должны зависеть от порядка выполнения других тестов.

---

## 72. Test Cleanup

Каждый test должен очищать созданные resources.

---

## 73. No Test Pollution

Test database, files, environment variables и mocks не должны влиять на другие tests.

---

## 74. CI

Automated tests должны запускаться в CI при изменениях codebase.

---

## 75. CI Levels

CI рекомендуется разделить на:

- fast tests;
- full tests;
- integration tests;
- optional external tests.

---

## 76. Fast CI

Fast CI должен включать:

- unit tests;
- validation;
- lint;
- type checking;
- architecture tests.

---

## 77. Full CI

Full CI дополнительно включает:

- component tests;
- contract tests;
- database tests;
- failure tests;
- recovery tests.

---

## 78. External Integration CI

External provider tests должны запускаться отдельно, чтобы нестабильность внешнего API не ломала основной fast CI pipeline.

---

## 79. Coverage

Coverage является вспомогательной метрикой.

Высокий coverage не заменяет quality of tests.

---

## 80. Critical Code Coverage

Особенно высокий уровень test coverage требуется для:

- Profit Calculator;
- Resource Manager;
- Fee System;
- Level 2;
- Database state transitions;
- Security boundaries.

---

## 81. Test Artifacts

CI должен сохранять необходимые:

- test reports;
- failure logs;
- coverage reports;
- diagnostics.

Не сохранять secrets.

---

## 82. Flaky Tests

Flaky tests должны считаться defect.

Не скрывать flaky test бесконечными retries.

---

## 83. Test Retry

CI может иметь ограниченный retry только для инфраструктурных transient failures.

Он не должен скрывать реальные test failures.

---

## 84. Release Gate

Production release не должен проходить, если critical automated tests failed.

---

## 85. Critical Test Failures

Особенно блокирующими являются:

- Profit Calculator failures;
- architecture boundary failures;
- security test failures;
- database migration failures;
- Level 2 false-positive failures.

---

## 86. Test Configuration

Test configuration должна быть отдельной от production configuration.

---

## 87. Fixtures

Fixtures должны быть:

- deterministic;
- versioned;
- understandable;
- minimal.

---

## 88. Provider Fixtures

Provider fixtures должны содержать representative responses:

- profitable;
- unprofitable;
- malformed;
- stale;
- failed.

---

## 89. Financial Fixtures

Financial fixtures должны покрывать:

- tiny amounts;
- normal amounts;
- large amounts;
- exact break-even;
- negative profit;
- positive profit;
- high fees;
- high gas.

---

## 90. Boundary Values

Обязательно тестировать boundary values:

- zero;
- minimum;
- maximum;
- just below threshold;
- exactly threshold;
- just above threshold.

---

## 91. Time Boundaries

Тестировать:

- quote exactly at freshness limit;
- quote just beyond freshness;
- job exactly at expiration;
- job just beyond expiration;
- scheduler exactly at execution time.

---

## 92. Data Integrity

Tests должны гарантировать:

- no partial critical transactions;
- no duplicate identities;
- no invalid state transitions;
- no precision loss.

---

## 93. State Machine Tests

State machines для:

- Level 2 Job;
- Notification;
- Opportunity;
- Scheduler Task

должны иметь explicit transition tests.

---

## 94. Invalid State Transitions

Каждый запрещённый state transition должен иметь test.

Например:

FAILED → CONFIRMED

не должен происходить без explicit recovery workflow.

---

## 95. Observability Tests

Проверять, что critical failures создают необходимые:

- logs;
- metrics;
- health state changes.

---

## 96. Security Regression

Security fixes должны получать regression tests, предотвращающие повторное появление vulnerability.

---

## 97. Test Documentation

Для сложных tests необходимо кратко документировать:

- что проверяется;
- почему это важно;
- какие assumptions используются.

---

## 98. Test Execution Order

Если test suite имеет dependencies, они должны быть explicit.

По возможности tests должны оставаться независимыми.

---

## 99. Local Testing

Developer должен иметь возможность запускать основной test suite локально без production credentials.

---

## 100. Final Testing Principle

Перед production deployment необходимо подтвердить:

- tests pass;
- architecture boundaries intact;
- security checks pass;
- database migrations pass;
- critical calculations pass;
- Level 2 cannot generate false confirmations under tested failure conditions;
- notifications use only confirmed data.

---

## 101. Critical Invariants

Testing никогда не должен:

1. использовать production credentials без explicit isolated environment;

2. выполнять реальные swaps;

3. отправлять реальные trading transactions;

4. использовать production database;

5. считать высокий coverage доказательством отсутствия defects;

6. скрывать реальные failures бесконечными retries;

7. зависеть от внешнего API для обычных unit tests;

8. использовать текущие market prices как deterministic test input;

9. допускать отсутствие tests для critical financial logic;

10. игнорировать architecture boundary violations;

11. считать flaky tests нормальным состоянием;

12. сохранять secrets в test artifacts;

13. использовать binary Float для проверки financial calculations;

14. пропускать critical test failures перед production release.

---

## 102. Главный принцип

Testing должен обеспечить:

**доказуемую корректность, устойчивость и архитектурную целостность Monik через независимые, deterministic и многоуровневые автоматические тесты.**

Unit tests проверяют:

**отдельные элементы.**

Integration tests проверяют:

**взаимодействие.**

Failure/recovery tests проверяют:

**поведение при сбоях.**

Architecture tests проверяют:

**сохранение утверждённых границ системы.**

E2E tests проверяют:

**полный workflow.**

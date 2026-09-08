# MONIK — DEVELOPMENT RULES

## 1. Назначение

Этот документ определяет обязательные правила разработки Monik.

Он предназначен прежде всего для Claude Code и любого другого разработчика, который изменяет repository.

Цель:

- сохранить утверждённую архитектуру;
- предотвратить самовольное изменение требований;
- обеспечить безопасное внесение изменений;
- не допускать скрытого technical debt;
- сохранять тестируемость;
- сохранять финансовую корректность;
- обеспечить предсказуемый workflow разработки.

---

## 2. Приоритет документов

При работе над проектом необходимо учитывать:

1. `CLAUDE.md`;
2. `docs/architecture/01_PROJECT_REQUIREMENTS.md`;
3. соответствующие документы `docs/architecture/`;
4. API Contracts;
5. Interfaces;
6. State Machines;
7. Data Models;
8. Testing requirements.

Если документы противоречат друг другу:

Claude Code не должен самостоятельно выбирать вариант.

Необходимо остановиться и запросить решение.

---

## 3. No Architecture Invention

Claude Code не должен самостоятельно придумывать новую архитектуру, если требуемая архитектура уже определена документацией.

---

## 4. No Silent Architecture Changes

Изменение архитектуры нельзя выполнять silently.

Даже если новая архитектура кажется технически лучше, изменение должно быть явно согласовано.

---

## 5. No Scope Expansion

Не добавлять функциональность, которой нет в approved requirements.

Особенно без explicit approval запрещены:

- trading execution;
- automatic swaps;
- portfolio management;
- arbitrary UI;
- новые networks;
- новые providers;
- новые notification channels;
- дополнительные external services.

---

## 6. Minimal Change Principle

При изменении существующего кода необходимо делать минимально необходимое изменение.

Не переписывать unrelated components без необходимости.

---

## 7. No Unrelated Refactoring

Если задача касается конкретного subsystem:

не выполнять одновременно большой refactoring других subsystem, если он не необходим для задачи.

---

## 8. Existing Code First

Перед написанием нового кода необходимо изучить существующую implementation.

Нельзя создавать duplicate implementation только потому, что нужная functionality кажется отсутствующей.

---

## 9. Search Before Create

Перед созданием:

- class;
- function;
- service;
- interface;
- repository;
- utility;

необходимо проверить, не существует ли уже соответствующий компонент.

---

## 10. Reuse Existing Contracts

Если существует соответствующий interface/contract:

использовать его вместо создания второго аналогичного interface.

---

## 11. No Duplicate Sources of Truth

Для каждого critical data type должен существовать один authoritative source.

Нельзя создавать параллельные:

- token registries;
- provider registries;
- configuration sources;
- state definitions;
- financial formulas.

---

## 12. Canonical Models

Использовать canonical domain models, определённые в:

`docs/architecture/36_DATA_MODELS.md`

Provider-specific models не должны распространяться в domain layer.

---

## 13. Provider Isolation

Provider-specific implementation должна находиться внутри соответствующего adapter.

---

## 14. No Provider Leakage

Provider SDK types, JSON structures и exceptions не должны проникать в business logic.

---

## 15. Resource Manager Rule

Все external provider requests должны проходить через Resource Manager.

Нельзя создавать альтернативный HTTP path, который обходит:

- rate limiting;
- concurrency;
- timeout;
- retry;
- circuit breaker.

---

## 16. No Direct HTTP in Business Logic

Business services не должны выполнять raw HTTP requests.

---

## 17. No Direct Database in Business Logic

Business services не должны:

- выполнять SQL;
- открывать SQLite connection;
- использовать database cursor;
- знать database path.

---

## 18. Repository Boundary

Persistence выполняется через Repository interfaces.

---

## 19. No Direct Telegram in Business Logic

Business services не должны напрямую использовать Telegram SDK/API.

---

## 20. Notification Boundary

Все Telegram operations должны проходить через Notification System и соответствующий adapter.

---

## 21. Configuration Boundary

Business logic не должна напрямую читать:

- `os.environ`;
- `.env`;
- YAML;
- JSON configuration files.

Configuration должна поступать через normalized Configuration object.

---

## 22. Secret Handling

Secrets никогда не должны:

- записываться в source code;
- commit'иться в Git;
- попадать в обычные logs;
- попадать в exceptions;
- попадать в test fixtures;
- попадать в notifications.

---

## 23. No Hardcoded Credentials

API keys, tokens, passwords и private credentials запрещены в source code.

---

## 24. Financial Code Rule

Любой код, который работает с:

- token amounts;
- fees;
- gas;
- profit;
- percentages;
- conversion;

должен использовать exact numeric representation.

Binary `float` запрещён для critical financial calculations.

---

## 25. No Implicit Zero

Если financial value отсутствует:

не подставлять zero автоматически.

Это относится как минимум к:

- fee;
- gas;
- quote;
- conversion rate.

---

## 26. Financial Change Review

Любое изменение financial calculation требует проверки:

- precision;
- rounding;
- decimals;
- units;
- fee treatment;
- gas treatment;
- threshold behavior.

---

## 27. Profit Calculator Isolation

Profit Calculator не должен самостоятельно:

- запрашивать provider;
- читать database;
- обращаться к Telegram;
- искать route;
- читать configuration напрямую.

Он получает validated input и возвращает ProfitResult.

---

## 28. Level 1 Rule

Level 1 обнаруживает Candidate.

Level 1 не подтверждает Opportunity.

---

## 29. Level 2 Rule

Level 2 подтверждает Candidate только после fresh validation.

---

## 30. Exact Combination Rule

Level 2 обязан проверять именно комбинацию, обнаруженную Level 1.

Не менять автоматически:

- network;
- token pair;
- amount;
- provider pair;
- route.

---

## 31. No Hidden Route Optimization

Нельзя добавлять implicit route optimization в Level 2.

Если route optimization потребуется:

это отдельное approved requirement.

---

## 32. Freshness Rule

Перед critical confirmation необходимо проверять freshness всех required external data.

---

## 33. No Stale Confirmation

Stale critical data не может использоваться для CONFIRMED Opportunity, если explicit policy не разрешает это.

---

## 34. Candidate Rule

Candidate является preliminary signal.

Он не должен рассматриваться как guaranteed arbitrage opportunity.

---

## 35. Opportunity Rule

Opportunity создаётся только после successful Level 2 confirmation.

---

## 36. Financial Snapshot Rule

После confirmation financial snapshot Opportunity является immutable в рамках обычного workflow.

---

## 37. State Machine Rule

Critical state нельзя изменять напрямую.

Использовать соответствующую State Machine transition.

---

## 38. Invalid Transition

Forbidden state transition должен приводить к explicit error.

Нельзя silently исправлять invalid state.

---

## 39. Terminal State Rule

Terminal state не должен изменяться обычным background workflow.

---

## 40. Concurrency Rule

Critical state transitions должны быть защищены от race conditions.

---

## 41. Idempotency Rule

Operations, которые могут быть повторены после:

- retry;
- timeout;
- restart;
- worker failure;

должны иметь idempotency strategy.

---

## 42. Duplicate Prevention

Особенно необходимо предотвращать duplicate:

- Candidates;
- Jobs;
- Opportunities;
- Notifications.

---

## 43. Retry Rule

Retry разрешён только для errors, классифицированных как retryable.

---

## 44. Retry Budget

Каждый retryable workflow должен иметь bounded retry budget.

---

## 45. No Infinite Loops

Запрещены uncontrolled:

- retry loops;
- polling loops;
- scanner loops;
- queue loops.

---

## 46. Expiration Rule

Если object expired:

не выполнять operation, которая требует valid freshness window.

---

## 47. Retry and Expiration

Expiration имеет приоритет над retry.

---

## 48. Cancellation Rule

После cancellation нельзя создавать новые execution attempts, если это противоречит lifecycle policy.

---

## 49. Scheduler Rule

Scheduler отвечает за timing и coordination.

Он не должен содержать business logic.

---

## 50. No Hidden Schedulers

Не создавать дополнительные background loops вне Scheduler без explicit architecture approval.

---

## 51. Scanner Frequency

Не создавать дополнительные scan loops, которые могут привести к превышению approved scan frequency.

---

## 52. Resource Bounds

Все новые components должны иметь bounded:

- concurrency;
- queue size;
- retries;
- response size;
- memory usage;

если соответствующий resource потенциально может расти.

---

## 53. Database Transactions

Transaction должна быть минимальной и atomic.

---

## 54. No External Requests in Transaction

Нельзя выполнять внутри database transaction:

- provider HTTP requests;
- Telegram requests;
- arbitrary external API calls.

---

## 55. Transaction Ownership

Transaction boundary должна определяться application/service layer, а не случайным repository call chain.

---

## 56. Error Handling

Infrastructure exceptions должны переводиться в normalized errors на boundary.

---

## 57. No Exception Swallowing

Нельзя делать:

- empty `except`;
- silent failure;
- silent retry exhaustion.

Каждый failure должен иметь defined behavior.

---

## 58. Error Classification

Каждый meaningful external failure должен быть классифицирован.

Минимально:

- retryable;
- permanent;
- timeout;
- rate limit;
- validation;
- configuration;
- dependency;
- cancellation;
- internal.

---

## 59. Logging Rule

Logs должны быть:

- structured;
- useful;
- actionable;
- safe.

---

## 60. No Secret Logging

Secrets никогда не логировать.

---

## 61. Correlation IDs

Critical workflows должны использовать correlation context там, где это необходимо для tracing.

---

## 62. Error Messages

Error messages должны помогать диагностировать проблему, но не раскрывать:

- credentials;
- private data;
- internal secrets.

---

## 63. Testing Before Commit

Изменение implementation должно сопровождаться соответствующими tests.

---

## 64. Test Scope

Минимально перед commit необходимо запускать tests, связанные с изменённым subsystem.

---

## 65. Full Tests

Перед завершением major feature необходимо запускать полный relevant test suite.

---

## 66. Financial Tests

При изменении financial code обязательны financial regression tests.

---

## 67. Contract Tests

При изменении interface или adapter обязательны contract tests.

---

## 68. State Tests

При изменении state machine обязательны transition tests.

---

## 69. Database Tests

При изменении schema/repository обязательны database/integration tests.

---

## 70. Security Tests

При изменении security-sensitive code необходимо запускать соответствующие security tests.

---

## 71. No Test Manipulation

Нельзя изменять tests только для того, чтобы скрыть regression.

---

## 72. No Flaky Test Suppression

Flaky test должен быть:

- исправлен;
- изолирован с documented reason;
- или удалён только после понимания причины.

---

## 73. Test Determinism

Tests должны быть deterministic.

Time, randomness и external systems должны быть controlled.

---

## 74. Clock Rule

Time-dependent tests должны использовать Clock abstraction.

---

## 75. External API Tests

Unit tests не должны зависеть от real external provider availability.

---

## 76. Mock Boundary

Mock/fake должен заменять external boundary, а не скрывать business logic.

---

## 77. Architecture Tests

Critical dependency boundaries должны проверяться автоматически, если tooling позволяет.

---

## 78. Forbidden Imports

Не допускать forbidden dependencies между layers.

Например:

- domain → infrastructure;
- Scanner → Telegram;
- Scanner → SQLite;
- Profit Calculator → HTTP.

---

## 79. Dependency Injection

Critical dependencies должны передаваться explicit способом.

Не использовать hidden global mutable state.

---

## 80. No Unnecessary Singleton

Singleton использовать только при доказанной необходимости.

---

## 81. Type Safety

Новый critical code должен соответствовать configured type checking.

Не отключать type checker ради быстрого исправления ошибки.

---

## 82. Formatting

Новый code должен соответствовать project formatter.

---

## 83. Linting

Не добавлять новые lint violations.

---

## 84. Dependency Addition

Новая dependency не должна добавляться без необходимости.

Перед добавлением проверить:

- можно ли использовать существующую dependency;
- security;
- maintenance;
- license;
- size/complexity;
- compatibility.

---

## 85. No Duplicate Libraries

Не добавлять вторую library для той же задачи без explicit reason.

---

## 86. Dependency Lock

Если project использует lock file:

он должен обновляться согласованным способом.

---

## 87. File Organization

Новый file должен находиться в соответствующей directory согласно Project Structure.

---

## 88. Naming

Названия:

- files;
- classes;
- functions;
- modules;

должны соответствовать существующему project convention.

---

## 89. No Generic Dump Modules

Не создавать огромные файлы вроде:

- `utils.py`;
- `helpers.py`;
- `common.py`;

для unrelated functionality без explicit architecture reason.

---

## 90. Single Responsibility

Каждый subsystem/component должен иметь clear responsibility.

---

## 91. No Business Logic in Infrastructure

Infrastructure adapter не должен принимать domain business decisions.

---

## 92. No Infrastructure in Domain

Domain models не должны импортировать infrastructure.

---

## 93. API Contract Rule

Если внешний API меняется:

сначала обновить adapter contract/mapping и tests.

Не распространять provider change по всей системе.

---

## 94. Database Migration Rule

Любое изменение persistent schema должно иметь migration.

---

## 95. Migration Safety

Migration должна быть:

- deterministic;
- testable;
- reversible, если architecture допускает;
- compatible с existing data согласно migration policy.

---

## 96. Data Preservation

Не удалять existing persistent data без explicit migration/retention policy.

---

## 97. Documentation Update

Изменение:

- API contract;
- state machine;
- data model;
- architecture;
- configuration;

требует обновления соответствующего documentation.

---

## 98. Documentation Authority

Не создавать новый документ только потому, что существующий кажется неудобным.

Сначала проверить, не покрывает ли существующий документ требуемую область.

---

## 99. Duplicate Documentation

Нельзя создавать два authoritative documents, определяющих одно и то же critical behavior.

---

## 100. Claude Code Stop Conditions

Claude Code должен остановиться и запросить решение, если:

1. requirements противоречат implementation;

2. два architecture documents противоречат друг другу;

3. задача требует изменения approved architecture;

4. требуется новый provider/network вне approved scope;

5. требуется изменение financial formula;

6. требуется изменение critical state machine;

7. требуется изменение database model без documented migration;

8. невозможно безопасно определить intended behavior;

9. найден security risk, который нельзя устранить без изменения scope;

10. implementation требует обхода architecture boundary.

---

## 101. No Guessing Critical Behavior

Нельзя угадывать:

- financial formulas;
- fee semantics;
- gas semantics;
- route behavior;
- state transitions;
- retry policy;
- security policy;

если они не определены документацией.

---

## 102. Safe Default

Если behavior неизвестен и его невозможно безопасно определить:

предпочтительно fail safely, а не продолжать с guessed behavior.

---

## 103. Change Impact Analysis

Перед изменением critical component необходимо определить:

- consumers;
- interfaces;
- tests;
- database dependencies;
- state transitions;
- documentation affected.

---

## 104. Small Commits

Изменения рекомендуется делать небольшими логически завершёнными шагами.

---

## 105. Commit Scope

Один commit желательно ограничивать одной coherent change.

---

## 106. No Generated Noise

Не добавлять в commit:

- temporary files;
- debug output;
- local databases;
- credentials;
- caches;
- IDE files;

если они не являются частью project.

---

## 107. Debug Code

Перед завершением задачи удалить:

- temporary prints;
- debug endpoints;
- temporary bypasses;
- development-only hacks;

если они не предусмотрены architecture.

---

## 108. Temporary Code

Если temporary implementation необходима:

она должна быть clearly marked и иметь explicit replacement plan.

---

## 109. No Hidden TODO for Critical Logic

Нельзя оставлять critical business logic в виде:

- TODO;
- placeholder;
- `pass`;
- fake success;
- hardcoded result.

---

## 110. No Fake Financial Results

Запрещено использовать hardcoded:

- profit;
- quote;
- fee;
- gas;
- route;

для production implementation.

---

## 111. No Fake Provider Success

Provider adapter не должен возвращать fake success при реальном provider failure.

---

## 112. Safe Failure

Если external data недоступна:

система должна fail/reject/retry согласно policy.

Не создавать synthetic valid financial data.

---

## 113. Production Debugging

Debug mode не должен отключать:

- security;
- validation;
- resource limits;
- financial checks.

---

## 114. Configuration Safety

Нельзя использовать development defaults в production.

---

## 115. Test Safety

Tests не должны иметь возможность случайно воздействовать на production infrastructure.

---

## 116. Review Checklist

Перед завершением изменения проверить:

- requirements;
- architecture;
- interfaces;
- data models;
- state machine;
- tests;
- security;
- performance;
- observability;
- documentation.

---

## 117. Final Verification

Перед объявлением задачи завершённой:

1. проверить changed files;
2. проверить diff;
3. запустить relevant tests;
4. проверить lint/type/format;
5. проверить architecture boundaries;
6. проверить documentation consistency.

---

## 118. No Premature Completion

Не объявлять задачу completed только потому, что code compiles или application starts.

---

## 119. Acceptance Alignment

Implementation должна соответствовать:

`docs/architecture/40_ACCEPTANCE_CRITERIA.md`

---

## 120. Production Readiness

Production-ready означает одновременно:

- requirements satisfied;
- architecture satisfied;
- tests passed;
- security validated;
- recovery validated;
- observability available;
- documentation synchronized.

---

## 121. Critical Invariants

Development Rules никогда не должны позволять:

1. Claude Code самостоятельно менять approved architecture;

2. угадывать critical financial behavior;

3. обходить Resource Manager;

4. обходить Repository boundary;

5. обходить State Machine;

6. использовать stale financial data для confirmation;

7. превращать missing financial data в zero;

8. создавать fake financial results;

9. создавать fake provider success;

10. хранить secrets в source code;

11. логировать secrets;

12. использовать production infrastructure в tests;

13. добавлять uncontrolled retry loops;

14. добавлять hidden schedulers;

15. создавать duplicate authoritative documentation;

16. менять database schema без migration;

17. менять financial logic без regression tests;

18. менять state machine без соответствующих tests;

19. расширять project scope без approval;

20. объявлять implementation готовой без выполнения acceptance criteria.

---

## 122. Главный принцип

Разработка Monik должна следовать правилу:

**сначала понять существующую архитектуру → определить impact изменения → изменить минимально необходимый код → проверить contracts и invariants → запустить tests → проверить security и boundaries → обновить документацию → только после этого считать задачу завершённой.**

Claude Code должен быть исполнителем утверждённой архитектуры, а не самостоятельным архитектором проекта.

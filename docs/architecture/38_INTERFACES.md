# MONIK — INTERFACES

## 1. Назначение

Этот документ определяет обязательные interfaces между subsystem Monik.

Цель:

- зафиксировать архитектурные boundaries;
- определить dependencies между компонентами;
- запретить прямой доступ к infrastructure;
- обеспечить заменяемость implementations;
- упростить testing;
- предотвратить появление скрытых coupling.

---

## 2. Главный принцип

Business logic должна зависеть от interfaces, а не от concrete infrastructure implementations.

Например:

Level 1 должен зависеть от Quote Provider interface, а не от конкретного HTTP client или SDK конкретного aggregator.

---

## 3. Interface vs Implementation

Interface определяет:

- что компонент делает;
- какие данные принимает;
- какие данные возвращает;
- какие ошибки может вернуть.

Implementation определяет:

- как именно это выполняется.

---

## 4. Dependency Direction

Рекомендуемое направление:

Domain
→ Application Interfaces
→ Infrastructure Implementations.

Infrastructure не должна становиться dependency domain layer.

---

## 5. Interface Ownership

Каждый interface должен иметь одного архитектурного owner.

Например:

- Quote interface → Aggregator subsystem;
- Fee interface → Fee System;
- Repository interface → соответствующий domain/application owner;
- Notification interface → Notification System;
- Scheduling interface → Scheduler;
- Resource interface → Resource Manager.

---

## 6. Provider Adapter Interface

Каждый aggregator adapter должен реализовывать единый normalized interface.

Условно:

`AggregatorAdapter`

---

## 7. AggregatorAdapter Responsibilities

AggregatorAdapter отвечает за:

- provider-specific request;
- provider-specific authentication;
- provider-specific response parsing;
- provider-specific error translation;
- conversion в normalized Quote.

---

## 8. AggregatorAdapter Must Not

AggregatorAdapter не должен:

- рассчитывать arbitrage profit;
- создавать Candidate;
- подтверждать Opportunity;
- отправлять Telegram;
- управлять глобальным Scheduler;
- напрямую изменять database domain state.

---

## 9. Quote Interface

Quote interface должен предоставлять операцию получения quote.

Логически:

`get_quote(request) -> Quote`

---

## 10. Quote Request

Quote request должен содержать:

- network;
- input token;
- output token;
- amount;
- provider context;
- route constraints, если применимо.

---

## 11. Quote Result

Quote result должен быть normalized domain model.

---

## 12. Quote Errors

Quote interface может возвращать normalized errors:

- timeout;
- rate limit;
- authentication;
- provider error;
- validation;
- unavailable.

Provider-specific exception classes не должны распространяться в business logic.

---

## 13. Fee Provider Interface

Fee System должен иметь abstraction для получения fees.

Логически:

`FeeProvider`

---

## 14. FeeProvider Responsibilities

FeeProvider отвечает за получение и normalization fee data.

---

## 15. FeeProvider Must Not

FeeProvider не должен:

- рассчитывать final arbitrage profitability;
- создавать Opportunity;
- отправлять notifications;
- управлять Scheduler.

---

## 16. Gas Provider Interface

Если gas является отдельным infrastructure source:

использовать отдельный interface:

`GasProvider`

---

## 17. GasProvider Responsibilities

GasProvider предоставляет normalized gas information.

---

## 18. GasProvider Must Not

GasProvider не должен самостоятельно решать, является ли opportunity profitable.

---

## 19. Profit Calculator Interface

Profit Calculator должен иметь explicit interface.

Логически:

`ProfitCalculator`

с операцией:

`calculate(input) -> ProfitResult`

---

## 20. Profit Calculator Input

Input должен содержать все required financial values.

---

## 21. Profit Calculator Independence

Profit Calculator не должен самостоятельно:

- делать HTTP requests;
- получать quotes;
- читать Telegram;
- читать environment variables;
- обращаться к database для получения hidden financial values.

---

## 22. Profit Calculator Determinism

При одинаковом validated input и одинаковой calculation version результат должен быть deterministic.

---

## 23. Token Registry Interface

Token Registry должен предоставлять canonical token information.

Минимальные операции:

- `get_token`
- `exists`
- `validate`
- `list_enabled`

---

## 24. Token Registry Responsibilities

Token Registry отвечает за:

- canonical Token identity;
- decimals;
- network association;
- enabled state.

---

## 25. Token Registry Must Not

Token Registry не должен:

- получать market quotes;
- рассчитывать profit;
- отправлять notifications.

---

## 26. Network Registry Interface

Если Network Registry выделен отдельно:

он предоставляет:

- network lookup;
- enabled networks;
- native token;
- network validation.

---

## 27. Capability Registry Interface

Capability Registry должен предоставлять:

- capability lookup;
- support validation;
- capability status;
- freshness.

---

## 28. Capability Query

Логически:

`check(provider, network, operation) -> Capability`

---

## 29. Capability Registry Rule

UNKNOWN capability не должна возвращаться как SUPPORTED.

---

## 30. Resource Manager Interface

Resource Manager является обязательной boundary для controlled external requests.

---

## 31. ResourceManager Responsibilities

Resource Manager отвечает за:

- concurrency;
- rate limiting;
- queueing;
- timeout;
- retry;
- backoff;
- jitter;
- circuit breaker;
- cancellation.

---

## 32. Resource Request

Resource request должен содержать:

- provider;
- network;
- operation;
- priority;
- timeout;
- cancellation context.

---

## 33. Resource Manager Execution

Логически:

`execute(request, operation) -> result`

или equivalent abstraction.

---

## 34. Resource Manager Ownership

Caller не должен самостоятельно обходить Resource Manager для provider requests.

---

## 35. HTTP Client Interface

Provider adapters могут использовать общий HTTP abstraction.

Логически:

`HttpClient`

---

## 36. HttpClient Responsibilities

HttpClient отвечает за:

- HTTP method;
- URL;
- headers;
- query;
- body;
- timeout;
- response;
- transport errors.

---

## 37. HttpClient Security

HTTP abstraction должен поддерживать:

- TLS verification;
- response size limit;
- redirect policy;
- timeout.

---

## 38. HttpClient Must Not

HttpClient не должен знать:

- arbitrage logic;
- Candidate;
- Opportunity;
- Telegram;
- Profit Calculator.

---

## 39. Clock Interface

Time-dependent logic должна использовать:

`Clock`

с операцией:

`now()`

---

## 40. Clock Responsibilities

Clock используется для:

- freshness;
- expiration;
- scheduler;
- retention;
- retry;
- tests.

---

## 41. System Time

Domain/application code не должен напрямую использовать system clock там, где deterministic testing требуется.

---

## 42. Scheduler Interface

Scheduler должен предоставлять controlled task scheduling.

Логически:

`Scheduler`

---

## 43. Scheduler Operations

Минимально:

- register task;
- enable task;
- disable task;
- execute task;
- cancel task;
- inspect state.

---

## 44. Scheduler Responsibilities

Scheduler отвечает за:

- timing;
- task lifecycle;
- overlap policy;
- execution coordination.

---

## 45. Scheduler Must Not

Scheduler не должен содержать:

- Level 1 business logic;
- Level 2 business logic;
- Profit calculation;
- provider-specific logic.

---

## 46. Level 1 Scanner Interface

Level 1 должен быть представлен application service/interface.

Логически:

`Level1Scanner`

---

## 47. Level 1 Scanner Operation

Например:

`scan(scope) -> ScanResult`

---

## 48. Level 1 Responsibilities

Level 1 отвечает за:

- scan scope;
- provider selection;
- quote collection;
- preliminary comparison;
- Candidate creation.

---

## 49. Level 1 Dependencies

Level 1 может зависеть от:

- Configuration;
- Token Registry;
- Capability Registry;
- Resource Manager;
- Aggregator Adapters;
- Candidate Repository;
- Clock.

---

## 50. Level 1 Prohibitions

Level 1 не должен напрямую использовать:

- SQLite;
- raw HTTP;
- Telegram;
- provider SDK.

---

## 51. Candidate Service Interface

Candidate lifecycle должен иметь explicit service.

Например:

`CandidateService`

---

## 52. CandidateService Responsibilities

Он отвечает за:

- Candidate validation;
- fingerprint;
- deduplication;
- persistence;
- queue handoff.

---

## 53. Level 2 Scanner Interface

Level 2 должен быть application service/interface.

Логически:

`Level2Scanner`

---

## 54. Level 2 Operation

Например:

`confirm(job) -> ConfirmationResult`

---

## 55. Level 2 Responsibilities

Level 2 отвечает за:

- Candidate validation;
- exact route validation;
- fresh quote retrieval;
- fresh fee/gas retrieval;
- Profit Calculator invocation;
- confirmation decision;
- Opportunity creation.

---

## 56. Level 2 Route Restriction

Level 2 не должен самостоятельно выбирать другой route вместо Candidate route.

---

## 57. Level 2 Dependencies

Level 2 может зависеть от:

- Candidate Repository;
- Job Repository;
- Resource Manager;
- Aggregator Adapters;
- Fee System;
- Gas Provider;
- Profit Calculator;
- Capability Registry;
- Clock;
- Opportunity Repository.

---

## 58. Opportunity Service Interface

Opportunity creation должна выполняться через explicit application/domain service.

Например:

`OpportunityService`

---

## 59. OpportunityService Responsibilities

Он отвечает за:

- confirmation validation;
- immutable financial snapshot;
- persistence;
- idempotency;
- state transition.

---

## 60. OpportunityService Must Not

OpportunityService не должен:

- отправлять Telegram;
- выполнять arbitrary provider requests;
- самостоятельно менять confirmed financial values.

---

## 61. Notification Interface

Notification System должен иметь interface:

`NotificationService`

или equivalent abstraction.

---

## 62. Notification Operation

Логически:

`notify(opportunity, destination) -> NotificationResult`

---

## 63. Notification Responsibilities

Notification Service отвечает за:

- formatting;
- destination selection;
- delivery;
- retry;
- deduplication;
- persistence.

---

## 64. Notification Adapter

Для Telegram должен существовать отдельный adapter.

Например:

`TelegramNotificationAdapter`

---

## 65. Telegram Adapter Responsibilities

Telegram adapter отвечает только за:

- Telegram API interaction;
- Telegram-specific errors;
- Telegram response parsing.

---

## 66. Telegram Adapter Must Not

Telegram adapter не должен:

- рассчитывать profit;
- менять Opportunity;
- выбирать arbitrage route.

---

## 67. Repository Interfaces

Database access должен происходить через repositories.

---

## 68. CandidateRepository

CandidateRepository должен поддерживать необходимые операции:

- create;
- get;
- find by fingerprint;
- update state;
- expiration queries.

---

## 69. JobRepository

JobRepository должен поддерживать:

- create;
- get;
- state transition;
- retry metadata;
- active jobs;
- recovery queries.

---

## 70. OpportunityRepository

OpportunityRepository должен поддерживать:

- create;
- get;
- deduplication lookup;
- notification relation;
- controlled status update.

---

## 71. NotificationRepository

NotificationRepository должен поддерживать:

- create;
- get;
- find logical notification;
- update delivery state;
- retry queries.

---

## 72. ScanRepository

Если Scan persistence используется:

он должен поддерживать:

- create;
- complete;
- fail;
- statistics;
- history queries.

---

## 73. FeeRepository

FeeRepository отвечает за persistence Fee snapshots.

---

## 74. CapabilityRepository

CapabilityRepository отвечает за persistence capability state/history.

---

## 75. Repository Restrictions

Repository не должен содержать business decisions вроде:

- «эта opportunity profitable»;
- «этот route лучше»;
- «отправить Telegram».

---

## 76. Transaction Interface

Critical multi-repository operations должны иметь transaction abstraction.

Например:

`TransactionManager`

---

## 77. Transaction Responsibilities

TransactionManager отвечает за:

- begin;
- commit;
- rollback.

---

## 78. Transaction Restrictions

Transaction не должна удерживаться во время:

- provider API call;
- Telegram API call;
- arbitrary external request.

---

## 79. Configuration Interface

Services должны получать normalized configuration через interface/object.

Например:

`Configuration`

---

## 80. Configuration Restrictions

Business services не должны самостоятельно читать:

- `os.environ`;
- YAML;
- JSON;
- `.env`.

---

## 81. Error Interface

Все subsystem должны использовать normalized error model.

---

## 82. Error Translation Boundary

Infrastructure переводит provider/database/HTTP exceptions в normalized application errors.

---

## 83. Health Interface

Health Monitoring должен иметь interface:

`HealthMonitor`

---

## 84. HealthMonitor Operations

Минимально:

- report healthy;
- report degraded;
- report unavailable;
- report recovery;
- get current state.

---

## 85. Health Restrictions

HealthMonitor не должен изменять business state.

---

## 86. Observability Interface

Logging/metrics/tracing должны предоставляться через controlled abstractions там, где это необходимо для тестируемости.

---

## 87. Logger Interface

Application services могут использовать:

`Logger`

с structured fields.

---

## 88. Metrics Interface

Metrics interface может предоставлять:

- counter;
- gauge;
- histogram;
- timing.

---

## 89. Correlation Interface

Critical workflow operations должны иметь возможность передавать correlation context.

---

## 90. Cancellation Interface

Long-running operations должны поддерживать cancellation context там, где это необходимо.

---

## 91. Retry Interface

Retry orchestration должна находиться в Resource Manager или другом central infrastructure component.

Business services не должны создавать uncontrolled retry loops.

---

## 92. Circuit Breaker Interface

Circuit breaker является internal Resource Manager capability.

Не каждый consumer должен самостоятельно создавать circuit breaker.

---

## 93. Persistence Interface

Persistent state должен проходить через Repository boundary.

---

## 94. External Boundary

External interaction должна проходить через:

- Resource Manager;
- Adapter;
- normalized contract.

---

## 95. Dependency Injection

Dependencies должны передаваться explicit способом.

Предпочтительно использовать constructor injection или equivalent explicit dependency injection.

---

## 96. No Hidden Globals

Critical services не должны использовать hidden global mutable state.

---

## 97. Singleton Policy

Singletons допустимы только если архитектурно необходимы и не создают hidden mutable state.

---

## 98. Testing Implementations

Каждый critical interface должен позволять использовать:

- fake;
- mock;
- stub;
- test implementation.

---

## 99. Interface Tests

Каждая concrete implementation должна проходить соответствующие contract tests.

---

## 100. Critical Invariants

Interfaces никогда не должны позволять:

1. business logic зависеть от provider SDK;

2. Scanner напрямую использовать HTTP;

3. Scanner напрямую использовать SQLite;

4. Scanner напрямую использовать Telegram;

5. Profit Calculator обращаться к external APIs;

6. Notification System пересчитывать profit;

7. Scheduler содержать business logic;

8. Repository принимать business decisions;

9. provider adapter создавать Opportunity;

10. provider adapter обходить Resource Manager;

11. business logic читать environment variables напрямую;

12. infrastructure exceptions распространяться в domain;

13. critical services использовать hidden global mutable state;

14. retry loops реализовываться независимо от central Resource Manager;

15. external DTO становиться canonical domain model;

16. один subsystem напрямую изменять persistent state другого subsystem;

17. transaction удерживаться во время external request;

18. interface contract изменяться без обновления consumers и tests.

---

## 101. Главный принцип

Interfaces Monik должны обеспечить:

**чёткие архитектурные границы, dependency inversion и заменяемость infrastructure implementations, при которых business logic работает только с canonical contracts и не знает, каким конкретно способом получены, сохранены или отправлены данные.**

Основной boundary:

**Service → Interface → Infrastructure Adapter → External System**

а для persistence:

**Service → Repository Interface → Database Implementation.**

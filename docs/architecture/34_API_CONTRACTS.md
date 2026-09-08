# MONIK — API CONTRACTS

## 1. Назначение

Этот документ определяет обязательные API contracts между основными subsystem Monik.

Цель:

- обеспечить стабильные boundaries;
- отделить domain models от infrastructure;
- стандартизировать взаимодействие между subsystem;
- упростить тестирование;
- позволить заменять provider implementations без изменения business logic.

---

## 2. Главный принцип

Каждая subsystem взаимодействует с другой subsystem только через определённый contract.

Internal implementation details не являются частью contract.

---

## 3. Contract Categories

Monik использует следующие категории contracts:

- Domain Contracts;
- Service Contracts;
- Provider Contracts;
- Repository Contracts;
- Notification Contracts;
- Scheduler Contracts;
- Resource Contracts;
- Health Contracts.

---

## 4. Domain Contract

Domain models должны быть независимы от:

- HTTP;
- SQLite;
- Telegram;
- environment variables;
- конкретных provider SDK.

---

## 5. Provider Quote Contract

Aggregator Adapter должен предоставлять normalized quote contract.

Логически:

`quote(request) -> Quote`

---

## 6. Quote Request

Quote request должен содержать только необходимые параметры.

Минимально:

- network;
- input token;
- output token;
- amount;
- provider;
- optional route constraints.

---

## 7. Quote Response

Normalized Quote должен содержать необходимые данные для дальнейшего processing.

Минимально:

- provider;
- network;
- input token;
- output token;
- input amount;
- output amount;
- route;
- timestamp;
- freshness metadata.

---

## 8. Quote Provider Metadata

Provider-specific metadata может сохраняться отдельно.

Она не должна становиться обязательной для domain logic.

---

## 9. Quote Validation

Provider Adapter должен отклонять:

- malformed response;
- missing required fields;
- invalid amounts;
- invalid token;
- invalid network;
- invalid route.

---

## 10. Quote Freshness

Quote contract должен позволять определить:

- created_at;
- age;
- freshness;
- expiration.

---

## 11. No Stale Quote as Fresh

Adapter или consumer не должен скрывать stale state.

---

## 12. Route Contract

Route должен содержать normalized representation маршрута.

Provider-specific route structure должна быть адаптирована внутри Adapter.

---

## 13. Token Contract

Token должен иметь canonical identity.

Минимально:

- network;
- address;
- symbol;
- decimals.

---

## 14. Token Identity

Token identity должна определяться через:

`network + address`

или equivalent canonical identifier.

---

## 15. Token Registry Contract

Token Registry должен предоставлять возможность:

- получить token;
- проверить existence;
- проверить network;
- получить decimals;
- проверить enabled state.

---

## 16. Capability Contract

Capability Registry должен позволять определить:

- provider;
- network;
- operation;
- supported;
- unsupported;
- degraded;
- unavailable;
- freshness.

---

## 17. Capability Semantics

UNKNOWN не должен автоматически считаться SUPPORTED.

---

## 18. Fee Contract

Fee System должен предоставлять normalized fee information.

Минимально:

- fee type;
- amount;
- currency/token;
- source;
- timestamp;
- freshness;
- included_in_quote.

---

## 19. Gas Contract

Gas information должен содержать:

- network;
- gas value;
- unit;
- conversion information;
- timestamp;
- freshness.

---

## 20. Profit Contract

Profit Calculator получает validated financial inputs и возвращает normalized result.

Логически:

`calculate(input) -> ProfitResult`

---

## 21. Profit Input

Profit calculation input должен содержать:

- input amount;
- output amount;
- fees;
- gas;
- required conversion data;
- calculation context.

---

## 22. Profit Result

ProfitResult должен содержать:

- gross result;
- total costs;
- net profit;
- profit percentage;
- calculation timestamp;
- calculation version;
- validity state.

---

## 23. Profit Invalid State

Если required financial input отсутствует или invalid:

ProfitResult не должен становиться valid positive result.

---

## 24. Level 1 Candidate Contract

Level 1 создаёт Candidate.

Candidate должен содержать:

- candidate_id;
- fingerprint;
- network;
- input token;
- output token;
- amount;
- route;
- provider pair;
- preliminary profitability;
- created_at;
- expires_at.

---

## 25. Candidate Purpose

Candidate является сигналом для дальнейшего Level 2 validation.

Candidate не является подтверждённой opportunity.

---

## 26. Candidate Contract Rule

Нельзя интерпретировать Candidate как CONFIRMED opportunity.

---

## 27. Level 2 Job Contract

Level 2 Job должен содержать:

- job_id;
- candidate reference;
- priority;
- created_at;
- expires_at;
- attempt count;
- state.

---

## 28. Level 2 Job States

Минимально:

- QUEUED;
- RUNNING;
- CONFIRMED;
- REJECTED;
- FAILED;
- EXPIRED;
- CANCELLED.

---

## 29. Job State Transition

State transition должен выполняться только через approved state machine.

---

## 30. Invalid Job Transition

Invalid state transition должен приводить к explicit error.

---

## 31. Level 2 Confirmation Contract

Level 2 должен возвращать либо:

- confirmed opportunity;
- rejected result;
- failure result.

---

## 32. Confirmation Requirements

CONFIRMED допускается только если:

- required data fresh;
- route valid;
- fees valid;
- gas valid;
- profit calculation valid;
- all required checks passed.

---

## 33. No Partial Confirmation

Если critical confirmation requirement не выполнен:

Job не может стать CONFIRMED.

---

## 34. Opportunity Contract

Confirmed Opportunity должна содержать immutable financial snapshot.

Минимально:

- opportunity_id;
- job_id;
- network;
- route;
- input amount;
- output amount;
- total costs;
- net profit;
- profit percentage;
- confirmed_at;
- calculation version.

---

## 35. Opportunity Immutability

Notification System не может изменять financial values Opportunity.

---

## 36. Notification Contract

Notification System принимает confirmed Opportunity.

Логически:

`notify(opportunity, destination)`

---

## 37. Notification Input

Notification contract должен содержать только approved notification data.

---

## 38. Notification Result

Notification result должен сообщать:

- success;
- temporary failure;
- permanent failure;
- retry state.

---

## 39. Notification Idempotency

Notification operation должна поддерживать deduplication.

---

## 40. Notification No-Recalculation

Notification System не должна пересчитывать profitability.

---

## 41. Scheduler Contract

Scheduler должен позволять зарегистрировать controlled task.

Task должен иметь:

- task_id;
- schedule;
- handler;
- enabled;
- retry policy;
- overlap policy.

---

## 42. Scheduler Handler

Task handler не должен создавать собственный scheduler loop.

---

## 43. Scheduler Result

Task execution должен иметь explicit result/state:

- SUCCESS;
- FAILED;
- SKIPPED;
- CANCELLED.

---

## 44. Scheduler Isolation

Scheduler не должен содержать business logic конкретной task.

Он вызывает соответствующий service.

---

## 45. Resource Manager Contract

Resource Manager должен принимать controlled resource request.

Минимально:

- resource type;
- provider;
- network;
- operation;
- priority;
- timeout;
- cancellation context.

---

## 46. Resource Result

Resource Manager возвращает:

- success;
- failure;
- timeout;
- rate limit;
- rejected;
- cancelled.

---

## 47. Resource Manager Enforcement

Provider requests не должны обходить Resource Manager.

---

## 48. Repository Contract

Repository должен предоставлять domain/application operations.

Например:

- save;
- get;
- update;
- list;
- delete, если разрешено;
- transaction.

---

## 49. Repository Abstraction

Business service не должен знать:

- SQL syntax;
- SQLite cursor;
- database file path.

---

## 50. Repository Errors

Database-specific exceptions должны переводиться в normalized application errors.

---

## 51. Transaction Contract

Critical multi-record operations должны поддерживать transaction boundary.

---

## 52. No External Calls in Transaction

Repository transaction не должна удерживаться во время external HTTP/Telegram operations.

---

## 53. Health Contract

Health Monitoring должен предоставлять:

- current state;
- subsystem states;
- provider states;
- timestamp;
- diagnostics summary.

---

## 54. Health States

Минимально:

- STARTING;
- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STOPPING.

---

## 55. Health Update

Subsystem должна иметь возможность сообщить Health Monitoring:

- success;
- failure;
- degraded condition;
- recovery.

---

## 56. Health No Business Logic

Health Monitoring не должна изменять business state ради health check.

---

## 57. Error Contract

Normalized error должен иметь:

- code;
- category;
- severity;
- retryable;
- message;
- operation;
- subsystem;
- timestamp.

---

## 58. Error Code

Error code должен быть stable machine-readable identifier.

---

## 59. Error Translation

Infrastructure errors должны переводиться в normalized error на boundary.

---

## 60. Configuration Contract

Services получают validated configuration.

Они не должны читать:

- environment variables;
- raw config files.

---

## 61. Configuration Object

Normalized configuration должен быть strongly typed.

---

## 62. Configuration Immutability

Runtime configuration должна быть immutable после startup, кроме explicitly reloadable values.

---

## 63. Clock Contract

Time-sensitive services должны использовать clock abstraction.

Логически:

`now() -> timestamp`

---

## 64. Clock Purpose

Clock abstraction необходима для:

- tests;
- freshness;
- expiration;
- scheduler;
- retention.

---

## 65. HTTP Contract

HTTP client abstraction должен предоставлять:

- method;
- URL;
- headers;
- query;
- body;
- timeout;
- response.

---

## 66. HTTP Safety

HTTP client должен обеспечивать:

- TLS verification;
- timeout;
- response size limits;
- controlled redirects.

---

## 67. Provider Adapter Contract

Каждый provider adapter должен реализовывать одинаковый normalized interface.

---

## 68. Provider Independence

Добавление нового provider не должно требовать изменения:

- Profit Calculator;
- domain models;
- Notification System.

---

## 69. Provider-Specific Features

Если provider имеет уникальную capability:

она должна быть представлена через explicit capability contract.

---

## 70. Provider Errors

Provider-specific errors не должны распространяться в domain.

---

## 71. Network Contract

Network abstraction должна предоставлять canonical network identity и metadata.

---

## 72. Network Validation

Service должен проверить, что requested network поддерживается соответствующим provider/capability.

---

## 73. Token Amount Contract

Token amount должен хранить:

- token identity;
- exact amount;
- decimals/context.

---

## 74. Decimal Contract

Financial contracts должны использовать exact decimal/base-unit representation.

---

## 75. Serialization

Domain contracts должны иметь deterministic serialization, если они передаются между processes или сохраняются.

---

## 76. No Infrastructure Serialization

Domain contract не должен зависеть от provider-specific JSON format.

---

## 77. Versioning

Critical contracts должны иметь versioning strategy.

---

## 78. Contract Changes

Breaking contract changes требуют:

- обновления consumers;
- обновления tests;
- обновления documentation;
- explicit review.

---

## 79. Backward Compatibility

Если возможно, contract changes должны быть backward-compatible.

---

## 80. Contract Tests

Каждый external adapter должен иметь contract tests.

---

## 81. Provider Contract Fixtures

Provider fixtures должны проверять mapping:

provider response
→ normalized contract.

---

## 82. Invalid Contract Tests

Tests должны проверять:

- missing fields;
- wrong types;
- invalid values;
- unsupported states.

---

## 83. Boundary Tests

Каждый critical contract должен иметь tests на:

- valid input;
- invalid input;
- boundary values;
- missing values;
- stale values.

---

## 84. No Hidden Fields

Critical behavior не должен зависеть от undocumented fields.

---

## 85. Optional Fields

Optional fields должны быть явно определены как optional.

---

## 86. Null Semantics

Null/None должен иметь определённую semantic meaning.

---

## 87. Unknown Semantics

UNKNOWN должен быть explicit state.

---

## 88. Failure Semantics

Failure должен быть distinguishable от:

- empty result;
- zero;
- unknown;
- unavailable.

---

## 89. Empty Result

Empty result не должен автоматически означать failure.

---

## 90. Zero Result

Zero financial result должен быть отличим от missing result.

---

## 91. Cancellation

Cancellation должна быть отдельным state/result.

---

## 92. Idempotency Contract

Operations, которые могут быть retried, должны иметь idempotency strategy.

---

## 93. Correlation Contract

Critical operations должны передавать correlation context.

---

## 94. Observability Contract

Critical services должны генерировать:

- structured logs;
- relevant metrics;
- correlation information.

---

## 95. Security Contract

Contracts не должны передавать secrets между subsystems без explicit requirement.

---

## 96. Access Contract

Subsystem должна получать только необходимые dependencies.

---

## 97. No Direct Infrastructure

Business services не должны получать arbitrary infrastructure objects.

Например, Scanner не должен получать raw HTTP client, если architecture требует Resource Manager.

---

## 98. Contract Ownership

Каждый contract должен иметь определённого owner в architecture.

Например:

- Quote → Provider Adapter;
- ProfitResult → Profit Calculator;
- Job → Level 2;
- Opportunity → domain/application;
- Notification → Notification System.

---

## 99. Contract Documentation

Изменение contract должно сопровождаться обновлением:

- documentation;
- tests;
- implementation.

---

## 100. Critical Invariants

API Contracts никогда не должны позволять:

1. provider-specific data проникать в domain без normalization;

2. Scanner напрямую использовать HTTP;

3. Scanner напрямую использовать Telegram;

4. business logic напрямую использовать SQLite;

5. Notification System пересчитывать profit;

6. Candidate считаться confirmed opportunity;

7. Level 2 подтверждать opportunity без required fresh data;

8. missing fee превращаться в zero;

9. missing gas превращаться в zero;

10. UNKNOWN считаться SUPPORTED;

11. raw provider exceptions распространяться в business logic;

12. financial contracts использовать binary Float;

13. external requests обходить Resource Manager;

14. transactions удерживаться во время external requests;

15. contracts изменяться silently;

16. secrets передаваться между subsystems без необходимости.

---

## 101. Главный принцип

API Contracts должны обеспечить:

**стабильные и проверяемые границы между subsystem Monik, при которых внешние данные нормализуются на boundary, business logic работает с domain contracts, а infrastructure implementations можно заменять без разрушения архитектуры.**

Основной поток:

**external provider → Adapter → normalized contract → business logic → domain result → next subsystem.**

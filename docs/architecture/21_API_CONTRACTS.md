# MONIK — API CONTRACTS

## 1. Назначение

API Contracts определяет единые внутренние контракты взаимодействия между подсистемами Monik и внешними providers.

Контракты должны обеспечивать:

- единый формат данных;
- предсказуемое поведение;
- изоляцию provider-specific implementation;
- type safety;
- validation;
- совместимость между subsystems;
- возможность заменять implementation без изменения business logic.

---

## 2. Главный принцип

Business logic должна работать с normalized domain models.

Она не должна зависеть от:

- конкретного HTTP client;
- JSON structure конкретного provider;
- provider-specific exceptions;
- provider-specific field names.

---

## 3. Contract Layers

Контракты логически разделяются на:

- external provider contracts;
- adapter contracts;
- domain contracts;
- subsystem contracts;
- persistence contracts;
- notification contracts.

---

## 4. External Provider Contract

Каждый provider имеет собственный внешний API contract.

Этот contract используется только внутри соответствующего Adapter.

---

## 5. Adapter Contract

Aggregator Adapter преобразует:

external provider response

в:

normalized domain model.

---

## 6. No Provider Leakage

Provider-specific fields не должны попадать непосредственно в Scanner, Profit Calculator или Notification System.

---

## 7. Quote Contract

Normalized Quote должен содержать минимум:

- provider;
- network;
- input token;
- output token;
- input amount;
- output amount;
- timestamp;
- validity;
- route metadata;
- fee metadata;
- slippage metadata;
- price impact metadata.

---

## 8. Quote Identity

Quote должен иметь unique identifier или deterministic reference.

---

## 9. Quote Amounts

Input и output amounts должны использовать exact financial representation.

Binary floating point запрещён.

---

## 10. Quote Timestamp

Quote должен содержать timestamp получения или формирования normalized response.

---

## 11. Quote Validity

Quote должен иметь явный validity state.

Минимально:

- VALID;
- INVALID;
- STALE;
- EXPIRED.

---

## 12. Invalid Quote

INVALID quote не должен участвовать в profitability calculation.

---

## 13. Stale Quote

STALE quote не должен использоваться для Level 2 final confirmation.

---

## 14. Expired Quote

Если provider предоставляет expiration:

после expiration quote считается EXPIRED.

---

## 15. Fee Contract

Normalized Fee должен содержать минимум:

- fee ID;
- provider;
- network;
- fee type;
- amount/value;
- currency/token;
- source;
- timestamp;
- validity;
- included_in_quote.

---

## 16. Fee Types

Fee type должен быть explicit.

Например:

- AGGREGATOR;
- PROTOCOL;
- INTEGRATOR;
- GAS;
- OTHER;
- REBATE.

---

## 17. Included Fee

Если fee включена в quote:

included_in_quote = true.

Profit Calculator не должен вычитать её повторно.

---

## 18. Unknown Fee

UNKNOWN fee должна иметь explicit state.

Она не должна автоматически преобразовываться в zero.

---

## 19. Gas Contract

Normalized Gas data должна содержать:

- estimate;
- unit;
- native token;
- network;
- timestamp;
- source;
- validity.

---

## 20. Gas Conversion

Если Profit Calculator требует gas в другой currency:

conversion должен выполняться через approved pricing/conversion mechanism.

---

## 21. Token Contract

Normalized Token должен содержать:

- symbol;
- address;
- decimals;
- network;
- enabled;
- metadata status.

---

## 22. Token Identity

Token identity определяется как минимум:

network + address.

Symbol не является уникальным идентификатором token.

---

## 23. Route Contract

Route должен содержать:

- network;
- input token;
- intermediate tokens;
- output token;
- providers;
- operations;
- sequence.

---

## 24. Fixed Route

Route должен быть immutable в рамках конкретного Job.

Level 2 не должен молча заменять route.

---

## 25. Opportunity Contract

Confirmed Opportunity должна содержать:

- opportunity ID;
- Job ID;
- network;
- route;
- amount;
- entry provider;
- exit provider;
- input amount;
- output amount;
- fees;
- gas;
- final profit;
- profit percentage;
- confirmation timestamp;
- calculation version.

---

## 26. Opportunity Status

Минимально:

- CONFIRMED;
- NOTIFIED;
- NOTIFIED_PARTIAL;
- NOTIFIED_FAILED;
- EXPIRED.

---

## 27. Candidate Contract

Level 1 Candidate должен содержать:

- candidate ID;
- fingerprint;
- network;
- route;
- amount;
- provider pair;
- preliminary result;
- creation timestamp;
- expiration timestamp.

---

## 28. Candidate Is Not Confirmation

Candidate не должен иметь статус, который можно интерпретировать как final confirmation.

---

## 29. Level 2 Job Contract

Level 2 Job должен содержать:

- job ID;
- candidate ID;
- fingerprint;
- priority;
- created_at;
- expires_at;
- status;
- route;
- amount;
- provider pair.

---

## 30. Job Status

Минимально:

- QUEUED;
- RUNNING;
- CONFIRMED;
- REJECTED;
- EXPIRED;
- FAILED;
- CANCELLED.

---

## 31. Scan Contract

Level 1 Scan должен иметь:

- scan ID;
- started_at;
- finished_at;
- status;
- scope;
- statistics;
- errors.

---

## 32. Scan Status

Минимально:

- RUNNING;
- COMPLETED;
- PARTIAL;
- FAILED;
- CANCELLED.

---

## 33. Scheduler Contract

Scheduler Task должен содержать:

- task ID;
- task type;
- schedule;
- enabled;
- priority;
- overlap policy;
- last execution;
- next execution.

---

## 34. Notification Contract

Notification должен содержать:

- notification ID;
- opportunity ID;
- destination ID;
- status;
- message;
- created_at;
- attempts.

---

## 35. Notification Status

Минимально:

- PENDING;
- SENDING;
- SENT;
- FAILED;
- CANCELLED;
- DUPLICATE.

---

## 36. Notification Attempt Contract

Attempt должен содержать:

- attempt ID;
- notification ID;
- started_at;
- finished_at;
- status;
- error code;
- external message ID, если доступен.

---

## 37. Error Contract

Normalized Error должен содержать:

- error code;
- category;
- severity;
- message;
- subsystem;
- operation;
- retryable;
- timestamp;
- context.

---

## 38. Error Categories

Минимально:

- CONFIGURATION_ERROR;
- VALIDATION_ERROR;
- NETWORK_ERROR;
- TIMEOUT_ERROR;
- RATE_LIMIT_ERROR;
- AUTH_ERROR;
- PROVIDER_ERROR;
- DATABASE_ERROR;
- RESOURCE_ERROR;
- CALCULATION_ERROR;
- INTERNAL_ERROR;
- CANCELLATION_ERROR.

---

## 39. Error Serialization

Errors, передаваемые между subsystems, должны использовать normalized representation.

Raw provider exceptions не должны передаваться через architecture boundaries.

---

## 40. Resource Request Contract

Resource Manager request должен содержать:

- request ID;
- provider/resource;
- operation;
- priority;
- timeout;
- retry policy;
- idempotency key;
- execution context.

---

## 41. Resource Response Contract

Resource Manager должен возвращать:

- request ID;
- status;
- result;
- latency;
- attempts;
- error, если operation failed.

---

## 42. Request Status

Минимально:

- SUCCESS;
- FAILED;
- TIMEOUT;
- RATE_LIMITED;
- CANCELLED.

---

## 43. Idempotency Key

Для операций, которые могут быть безопасно повторены, должен использоваться idempotency key.

---

## 44. Context Propagation

Контракты должны позволять передавать:

- scan ID;
- Job ID;
- execution ID;
- notification ID.

Это необходимо для tracing и diagnostics.

---

## 45. Configuration Contract

Configuration subsystem должна возвращать validated configuration object.

Остальные subsystems не должны читать configuration file самостоятельно.

---

## 46. Configuration Snapshot

Operation может получить immutable configuration snapshot.

---

## 47. Capability Contract

Capability должна содержать:

- provider;
- network;
- token;
- operation;
- state;
- source;
- timestamp;
- expiration.

---

## 48. Capability State

Минимально:

- SUPPORTED;
- UNSUPPORTED;
- UNKNOWN;
- DEGRADED;
- UNAVAILABLE.

---

## 49. Health Contract

Health status должен содержать:

- subsystem;
- status;
- timestamp;
- reason;
- checks;
- metrics summary.

---

## 50. Health Status

Минимально:

- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STARTING;
- STOPPING.

---

## 51. Fee Snapshot Contract

Fee Snapshot должен содержать:

- snapshot ID;
- provider;
- network;
- timestamp;
- fees;
- validity;
- version.

---

## 52. Profit Calculation Contract

Profit Calculator должен принимать normalized calculation input.

Минимально:

- input amount;
- output amount;
- fees;
- gas;
- rebates;
- other costs;
- calculation context.

---

## 53. Profit Result

Profit Result должен содержать:

- gross output;
- total costs;
- net profit;
- profit percentage;
- calculation version;
- timestamp;
- status.

---

## 54. Calculation Status

Минимально:

- CALCULATED;
- REJECTED;
- INVALID;
- INCOMPLETE.

---

## 55. No Implicit Defaults

API contracts не должны использовать скрытые financial defaults.

Например:

missing fee ≠ zero.

---

## 56. Validation

Каждый contract должен иметь validation rules.

Validation должна выполняться на boundary перед передачей данных дальше.

---

## 57. Required Fields

Отсутствие required field должно приводить к VALIDATION_ERROR.

---

## 58. Unknown Fields

Unknown external provider fields могут игнорироваться на Adapter boundary.

Но required fields должны быть явно проверены.

---

## 59. Versioning

Contracts должны иметь versioning strategy.

Изменение структуры, которое может нарушить consumers, требует version change или backward-compatible migration.

---

## 60. Backward Compatibility

Minor additions должны по возможности оставаться backward compatible.

Удаление или изменение semantic meaning существующего required field требует explicit migration.

---

## 61. Contract Version

Критические domain snapshots могут содержать:

contract_version.

---

## 62. Schema Validation

Для сериализуемых contracts должна существовать machine-readable schema или equivalent validation.

---

## 63. Serialization

Serialization format должен быть deterministic насколько это возможно.

Это важно для:

- hashing;
- fingerprints;
- testing;
- persistence.

---

## 64. Decimal Serialization

Decimal values не должны сериализоваться как binary float.

Предпочтительно:

- decimal string;
- integer base units.

---

## 65. Address Normalization

Token addresses должны проходить normalization согласно network/address policy.

---

## 66. Case Sensitivity

Business identity не должна зависеть от регистра token address.

---

## 67. Enum Stability

Enum values должны иметь стабильные machine-readable identifiers.

Display labels не должны использоваться как internal identifiers.

---

## 68. Timestamp Format

Serialized timestamps должны использовать единый формат.

Предпочтительно UTC ISO 8601.

---

## 69. Timezone

Internal timestamps должны быть timezone-aware.

Display timezone определяется presentation/configuration layer.

---

## 70. Contract Ownership

Каждый contract должен иметь одну authoritative subsystem.

Например:

- Token → Token Registry;
- Quote → Aggregator Adapter/domain layer;
- Profit Result → Profit Calculator;
- Notification → Notification System.

---

## 71. No Duplicate Models

Не создавать несколько несовместимых моделей для одного и того же domain object без необходимости.

---

## 72. Adapter Mapping

Provider Adapter отвечает за:

external response
→ normalized contract.

---

## 73. Domain Mapping

Business subsystem не должна знать, каким JSON provider описывает quote.

---

## 74. Persistence Mapping

Database Repository отвечает за:

domain model
↔ database record.

---

## 75. Notification Mapping

Message Formatter отвечает за:

confirmed opportunity
→ display message.

---

## 76. API Contract Testing

Каждый external adapter должен иметь contract tests.

---

## 77. Provider Contract Tests

Contract tests должны проверять:

- valid response;
- missing fields;
- invalid fields;
- unexpected fields;
- error response;
- timeout;
- rate limit;
- malformed response.

---

## 78. Domain Contract Tests

Необходимо тестировать:

- Quote;
- Fee;
- Gas;
- Token;
- Route;
- Candidate;
- Job;
- Opportunity;
- Profit Result.

---

## 79. Compatibility Tests

При изменении contract необходимо проверять существующих consumers.

---

## 80. Integration Tests

Обязательно тестировать основные contract chains:

Aggregator Adapter
→ Quote
→ Level 1

Level 1
→ Candidate
→ Level 2 Job

Level 2
→ Profit Result
→ Confirmed Opportunity

Confirmed Opportunity
→ Notification

---

## 81. Critical Invariants

API Contracts никогда не должны:

1. позволять provider-specific JSON проникать в business logic;

2. использовать Float для финансовых значений;

3. считать missing value равным zero без policy;

4. позволять Level 1 создавать CONFIRMED Opportunity;

5. позволять Notification System изменять Profit Result;

6. позволять Level 2 выполнять swaps;

7. позволять Scanner напрямую обращаться к provider-specific API models;

8. передавать raw exceptions через subsystem boundaries;

9. изменять semantic meaning поля без version/migration policy;

10. использовать display labels как internal identifiers;

11. смешивать timestamps с разными timezone semantics;

12. создавать duplicate incompatible models без необходимости.

---

## 82. Главный принцип

API Contracts должны обеспечить:

**строго определённый язык взаимодействия между всеми подсистемами Monik, при котором каждая subsystem получает только normalized, validated и однозначные данные, не зависит от внутренних деталей другой subsystem и может быть заменена без разрушения всей архитектуры.**

External providers говорят на своих API.

Adapters переводят их.

Domain contracts обеспечивают единый язык Monik.

Business subsystems работают только с этим единым языком.

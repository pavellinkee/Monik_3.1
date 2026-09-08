# MONIK — DATA MODELS

## 1. Назначение

Этот документ определяет canonical domain data models Monik.

Он является обязательным источником истины для структуры основных сущностей системы.

Цель:

- определить единые модели данных;
- исключить дублирование разных representations;
- определить обязательные и optional fields;
- определить связи между сущностями;
- определить ownership данных;
- исключить provider-specific data из domain models;
- обеспечить совместимость Level 1, Level 2, Profit Calculator, Database и Notification System.

---

## 2. Главный принцип

Каждая основная сущность Monik должна иметь одну canonical domain representation.

Infrastructure-specific representations могут существовать отдельно, но должны преобразовываться в canonical domain model на соответствующей boundary.

---

## 3. Domain Model Independence

Domain models не должны зависеть от:

- SQLite;
- конкретного ORM;
- HTTP;
- provider SDK;
- Telegram SDK;
- environment variables;
- configuration file format.

---

## 4. Exact Numeric Representation

Все financial amounts должны использовать exact representation.

Для Python implementation предпочтительно:

- Decimal;
- integer base units;

в зависимости от конкретного поля.

Binary floating-point `float` запрещён для critical financial calculations.

---

## 5. Timestamp Representation

Все timestamps должны использовать UTC semantics.

Domain model должна явно представлять timezone-aware timestamp или эквивалентную безопасную representation.

---

## 6. Identifier Rules

Каждая persistent entity должна иметь stable identifier.

ID должен быть:

- unique;
- deterministic where required;
- serializable;
- safe for database storage.

---

## 7. Network

Network представляет blockchain network.

Минимальные поля:

- `network_id`
- `name`
- `chain_id`, если применимо
- `native_token`
- `enabled`

---

## 8. Network Identity

Canonical identity Network должна быть stable.

Не использовать display name как единственный identifier.

---

## 9. Token

Token представляет конкретный token внутри конкретной network.

Минимальные поля:

- `network_id`
- `address`
- `symbol`
- `decimals`
- `enabled`

---

## 10. Token Identity

Canonical Token identity:

`network_id + normalized_address`

Symbol не является уникальным identifier.

---

## 11. Native Token

Native token должен быть представлен через canonical Token/Network model или explicit native-token abstraction.

Нельзя использовать symbol как единственный способ идентификации native asset.

---

## 12. Token Amount

Token Amount представляет количество конкретного Token.

Минимально:

- `token`
- `amount`

`amount` должен использовать exact representation.

---

## 13. Base Units

Если amount хранится в base units:

decimals Token должны использоваться только для conversion/display.

---

## 14. Provider

Provider представляет внешний aggregator/API provider.

Минимальные поля:

- `provider_id`
- `name`
- `enabled`

Provider credentials не являются частью domain model.

---

## 15. Provider Capability

Provider capability определяется отдельно через Capability Registry.

Provider model не должен самостоятельно утверждать, что provider поддерживает конкретную operation.

---

## 16. Route

Route представляет normalized swap path.

Минимально может содержать:

- provider;
- network;
- input token;
- output token;
- route steps;
- route identifier/fingerprint.

---

## 17. Route Step

Route Step представляет отдельный этап маршрута.

Минимально:

- input token;
- output token;
- protocol/source;
- optional pool/address metadata.

Provider-specific route format должен быть преобразован в normalized Route Step.

---

## 18. Route Fingerprint

Route fingerprint используется для deterministic comparison/deduplication.

Fingerprint должен зависеть от meaningful route parameters.

Не включать:

- timestamps;
- random IDs;
- secrets.

если они не являются частью route identity.

---

## 19. Quote

Quote представляет актуальную external market quote.

Минимально:

- `quote_id`, если persistence необходима;
- `provider_id`
- `network_id`
- `input_token`
- `output_token`
- `input_amount`
- `output_amount`
- `route`
- `created_at`
- `expires_at` или freshness information.

---

## 20. Quote Semantics

Quote является snapshot external market state.

Quote не является гарантией будущего execution result.

---

## 21. Quote Freshness

Каждый Quote должен позволять определить, является ли он fresh.

Freshness определяется policy, а не только наличием timestamp.

---

## 22. Quote Provider Data

Raw provider response не является canonical Quote.

Adapter обязан преобразовать provider response в normalized Quote.

---

## 23. Quote Validation

Quote считается valid только если:

- network valid;
- tokens valid;
- amounts valid;
- route valid;
- provider valid;
- timestamp valid;
- required fields присутствуют.

---

## 24. Fee

Fee представляет стоимость, связанную с operation.

Минимально:

- `fee_type`
- `amount`
- `currency`
- `source`
- `timestamp`
- `included_in_quote`

---

## 25. Fee Type

Fee type должен быть explicit enum/category.

Например:

- provider fee;
- protocol fee;
- network fee;
- service fee;
- other approved category.

---

## 26. Gas

Gas представляет network execution cost.

Минимально:

- `network_id`
- `gas_units`
- `gas_price`
- `native_token`
- `estimated_cost`
- `timestamp`

---

## 27. Gas Freshness

Gas information должен иметь freshness state.

Stale gas не должен использоваться для critical confirmation без explicit policy.

---

## 28. Profit Calculation Input

ProfitCalculationInput должен содержать все required financial data.

Минимально:

- input amount;
- output amount;
- fees;
- gas;
- conversion context;
- calculation context.

---

## 29. Profit Result

ProfitResult представляет результат financial calculation.

Минимально:

- gross result;
- total costs;
- net profit;
- profit percentage;
- timestamp;
- calculation version;
- validity state.

---

## 30. Profit Validity

ProfitResult должен позволять отличить:

- VALID;
- INVALID;
- INCOMPLETE;
- STALE.

---

## 31. No Implicit Zero

Отсутствующий Fee, Gas или conversion data не должен превращаться в zero автоматически.

---

## 32. Candidate

Candidate представляет preliminary opportunity, обнаруженную Level 1.

Минимально:

- `candidate_id`
- `fingerprint`
- `network_id`
- `input_token`
- `output_token`
- `input_amount`
- `route`
- `buy_provider`
- `sell_provider`
- `preliminary_profit`
- `created_at`
- `expires_at`
- `status`

---

## 33. Candidate Semantics

Candidate является сигналом для Level 2.

Candidate не является confirmed financial opportunity.

---

## 34. Candidate Fingerprint

Fingerprint должен обеспечивать deduplication логически одинаковых candidates.

Он не должен зависеть от случайного Candidate ID.

---

## 35. Candidate Expiration

Candidate должен иметь validity window.

После expiration Candidate нельзя использовать для confirmation.

---

## 36. Level 2 Job

Level 2 Job представляет execution unit для confirmation одного Candidate.

Минимально:

- `job_id`
- `candidate_id`
- `priority`
- `status`
- `created_at`
- `updated_at`
- `expires_at`
- `attempt_count`

---

## 37. Job Ownership

Level 2 является owner lifecycle Job.

Другие subsystems не должны напрямую изменять Job status.

---

## 38. Job State

Job status должен соответствовать State Machine document.

Минимально:

- QUEUED;
- RUNNING;
- CONFIRMED;
- REJECTED;
- FAILED;
- EXPIRED;
- CANCELLED.

---

## 39. Job Retry

Retry metadata должна быть отделена от business result.

`attempt_count` не означает successful execution.

---

## 40. Confirmation Result

Confirmation Result представляет результат одного Level 2 validation attempt.

Он может содержать:

- status;
- fresh quote(s);
- fresh fees;
- fresh gas;
- profit result;
- rejection reason;
- error information.

---

## 41. Confirmation Result vs Opportunity

Confirmation Result не является Opportunity.

Opportunity создаётся только после успешного confirmation.

---

## 42. Opportunity

Opportunity представляет confirmed arbitrage opportunity.

Минимально:

- `opportunity_id`
- `job_id`
- `candidate_id`, если нужен audit relation
- `network_id`
- `route`
- `input_amount`
- `output_amount`
- `total_costs`
- `net_profit`
- `profit_percentage`
- `confirmed_at`
- `calculation_version`
- `status`

---

## 43. Opportunity Financial Snapshot

После confirmation financial values являются snapshot.

Обычный workflow не должен их изменять.

---

## 44. Opportunity Status

Минимально:

- CONFIRMED;
- NOTIFIED;
- NOTIFIED_PARTIAL;
- NOTIFIED_FAILED.

---

## 45. Opportunity Immutability

После создания Opportunity нельзя обычным update менять:

- route;
- input amount;
- output amount;
- fees;
- gas;
- total costs;
- net profit;
- profit percentage;
- calculation version.

---

## 46. Opportunity Correction

Если correction действительно необходим:

использовать explicit correction/audit mechanism.

Не изменять historical snapshot silently.

---

## 47. Notification

Notification представляет попытку доставить Opportunity destination.

Минимально:

- `notification_id`
- `opportunity_id`
- `destination_id`
- `status`
- `created_at`
- `updated_at`
- `attempt_count`

---

## 48. Notification State

Минимально:

- QUEUED;
- SENDING;
- RETRY_WAIT;
- SENT;
- FAILED;
- CANCELLED.

---

## 49. Notification Identity

Logical notification identity должна позволять определить:

`opportunity + destination`

---

## 50. Notification Idempotency

Одна logical notification не должна бесконтрольно отправляться повторно.

---

## 51. Scan

Scan представляет один execution cycle Level 1.

Минимально:

- `scan_id`
- `started_at`
- `finished_at`
- `status`
- `scope`
- statistics.

---

## 52. Scan Scope

Scan scope должен описывать:

- networks;
- providers;
- token universe;
- amounts.

---

## 53. Scan Statistics

Scan statistics могут содержать:

- providers checked;
- networks checked;
- quote requests;
- successful quotes;
- failed quotes;
- candidates created.

---

## 54. Scan Result

Scan Result не должен содержать необязательную огромную историю всех raw quotes.

---

## 55. Resource Request

Resource Request представляет запрос к ограниченному external resource.

Минимально:

- provider;
- network;
- operation;
- priority;
- timeout;
- cancellation context.

---

## 56. Resource Result

Resource Result должен отличать:

- SUCCESS;
- FAILURE;
- TIMEOUT;
- RATE_LIMITED;
- REJECTED;
- CANCELLED.

---

## 57. Scheduler Task

Scheduler Task представляет registered scheduled operation.

Минимально:

- `task_id`
- schedule;
- enabled;
- overlap policy;
- retry policy.

---

## 58. Scheduler Execution

Execution history может содержать:

- execution_id;
- task_id;
- started_at;
- finished_at;
- status;
- error code.

---

## 59. Capability

Capability представляет факт поддержки конкретной operation.

Минимально:

- provider;
- network;
- operation;
- status;
- checked_at;
- expires_at/freshness.

---

## 60. Capability Status

Минимально:

- SUPPORTED;
- UNSUPPORTED;
- UNKNOWN;
- DEGRADED;
- UNAVAILABLE.

---

## 61. Capability Semantics

UNKNOWN не означает SUPPORTED.

---

## 62. Health State

Health state представляет operational состояние subsystem/provider.

Минимально:

- component;
- status;
- timestamp;
- reason;
- diagnostics summary.

---

## 63. Health Status

Минимально:

- STARTING;
- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STOPPING.

---

## 64. Error

Normalized Error представляет controlled application failure.

Минимально:

- code;
- category;
- severity;
- retryable;
- message;
- subsystem;
- operation;
- timestamp;
- correlation ID.

---

## 65. Error Metadata

Provider-specific diagnostic metadata может существовать отдельно.

Она не должна становиться обязательной частью domain error contract.

---

## 66. Correlation Context

Critical workflow objects могут содержать или передавать:

- correlation_id;
- job_id;
- candidate_id;
- opportunity_id.

---

## 67. Configuration Model

Normalized Configuration является отдельным strongly typed model.

Он не должен смешиваться с domain financial entities.

---

## 68. Secrets

Secrets не являются частью domain models.

---

## 69. API Serialization

Domain models могут иметь отдельные DTO для:

- HTTP;
- Telegram;
- database;
- provider APIs.

Domain model не должна быть forced serialization format для всех boundaries.

---

## 70. Database Models

Database models могут отличаться от domain models.

Repository отвечает за mapping.

---

## 71. DTO

DTO может использоваться для передачи данных между infrastructure boundaries.

DTO не должен становиться причиной provider coupling.

---

## 72. Model Validation

Каждая canonical model должна иметь validation rules.

---

## 73. Required Fields

Required fields должны валидироваться при создании model.

---

## 74. Immutable Financial Models

Financial snapshot models должны быть immutable после confirmation.

---

## 75. Mutable Operational Models

Operational models, например Job, могут изменять lifecycle state через State Machine.

---

## 76. Enum Stability

Enums, используемые в persistent state, должны иметь stable values.

---

## 77. Serialization Stability

Persistent models должны иметь deterministic serialization/mapping.

---

## 78. Model Version

Если persistent model меняется таким образом, что нарушается compatibility:

необходима migration strategy.

---

## 79. Relationships

Основные relationships:

`Network → Token`

`Provider → Capability`

`Provider + Network → Capability`

`Candidate → Level 2 Job`

`Level 2 Job → Opportunity`

`Opportunity → Notification`

`Scan → Candidate`

`Scheduler Task → Execution`

---

## 80. Candidate and Job

Один Candidate может иметь максимум controlled number of Level 2 Jobs согласно retry/recovery policy.

Нельзя создавать uncontrolled duplicate Jobs.

---

## 81. Job and Opportunity

Один успешно подтверждённый Job должен создавать максимум одну logical Opportunity.

---

## 82. Opportunity and Notification

Одна Opportunity может иметь несколько Notifications, если configured несколько destinations.

---

## 83. Notification and Destination

Destination является configuration/operational identity.

Он не должен быть произвольным external input.

---

## 84. Scan and Candidate

Candidate должен иметь связь с Scan, если это необходимо для diagnostics/audit.

---

## 85. Financial Snapshot Consistency

Все financial values одной Opportunity должны относиться к одному confirmation context.

Нельзя смешивать quote из одного confirmation с fee/gas snapshot от другого несовместимого context.

---

## 86. Quote Consistency

Input/output amounts, route и provider должны быть взаимно согласованы.

---

## 87. Network Consistency

Все Token и Route objects должны соответствовать указанной Network.

---

## 88. Token Consistency

Token decimals должны соответствовать canonical Token Registry.

---

## 89. Provider Consistency

Provider в Quote/Route должен соответствовать provider registry.

---

## 90. Capability Consistency

Operation может выполняться только если соответствующая capability позволяет её выполнение.

---

## 91. Freshness Consistency

Financial confirmation models должны содержать или иметь доступ к freshness metadata для required external data.

---

## 92. Expiration Consistency

Candidate и Job expiration не должны противоречить друг другу.

---

## 93. Amount Consistency

Input amount Level 2 confirmation должен соответствовать Candidate amount, если architecture не предусматривает explicit amount transformation.

---

## 94. Route Consistency

Level 2 обязан проверять именно route, который относится к Candidate согласно Level 2 requirements.

---

## 95. Provider Pair Consistency

Если Candidate содержит buy/sell provider pair:

Level 2 не должен автоматически заменять provider pair другим маршрутом без explicit architecture rule.

---

## 96. No Hidden Transformation

Любое изменение:

- amount;
- route;
- provider;
- network;
- token pair

должно быть explicit и observable.

---

## 97. Model Ownership

Каждая model должна иметь owner subsystem.

Пример:

- Token → Token Registry;
- Capability → Capability Registry;
- Quote → Provider Adapter;
- Candidate → Level 1;
- Job → Level 2;
- ProfitResult → Profit Calculator;
- Opportunity → confirmation/application layer;
- Notification → Notification System.

---

## 98. Cross-Subsystem Changes

Subsystem не должен изменять чужую model напрямую.

Использовать соответствующий service/contract.

---

## 99. Critical Invariants

Data Models никогда не должны позволять:

1. использовать symbol как единственный Token identity;

2. использовать binary Float для critical financial values;

3. считать Candidate confirmed Opportunity;

4. создавать Opportunity без successful Level 2 confirmation;

5. смешивать financial data разных confirmation contexts;

6. использовать stale Quote как fresh;

7. использовать missing Fee как zero;

8. использовать missing Gas как zero;

9. менять confirmed financial snapshot обычным workflow;

10. автоматически менять Candidate route/provider pair без explicit rule;

11. использовать UNKNOWN capability как SUPPORTED;

12. передавать provider-specific raw models в domain logic;

13. хранить secrets внутри domain models;

14. создавать uncontrolled duplicate Jobs;

15. создавать uncontrolled duplicate Opportunities;

16. создавать uncontrolled duplicate Notifications;

17. использовать timezone-dependent timestamps;

18. обходить canonical Token/Network identity;

19. позволять infrastructure-specific DTO становиться canonical domain model.

---

## 100. Главный принцип

Data Models Monik должны обеспечить:

**единую, точную и независимую от инфраструктуры модель данных, на которой Level 1, Level 2, Profit Calculator, Provider Adapters, Database и Notification System работают согласованно и предсказуемо.**

Canonical flow:

**external data → normalized model → validated domain model → business processing → persistent/result model → external output.**

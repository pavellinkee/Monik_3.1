# MONIK — CAPABILITY REGISTRY

## 1. Назначение

Capability Registry — централизованный источник информации о том, какие операции фактически поддерживаются конкретными providers, networks, tokens и routes.

Он отвечает за определение:

- поддерживаемых networks;
- поддерживаемых tokens;
- поддерживаемых operations;
- поддерживаемых routes;
- provider capabilities;
- доступных комбинаций provider/network/token.

Capability Registry не выполняет trading operations и не заменяет Health Monitoring.

---

## 2. Главный принцип

Configuration определяет:

**что разрешено использовать.**

Capability Registry определяет:

**что фактически поддерживается.**

Health Monitoring определяет:

**доступно ли это сейчас.**

Эти три понятия не должны смешиваться.

---

## 3. Capability Model

Capability должна описывать конкретную возможность provider.

Минимально:

- provider;
- network;
- token;
- operation;
- route support;
- status;
- source;
- updated_at.

---

## 4. Provider Capability

Для каждого provider необходимо определить:

- поддерживаемые networks;
- поддерживаемые operations;
- поддерживаемые tokens;
- поддерживаемые route types;
- ограничения API.

---

## 5. Network Capability

Для каждой network необходимо знать:

- поддерживается ли она provider;
- поддерживаются ли необходимые operations;
- доступен ли требуемый API endpoint.

---

## 6. Token Capability

Для конкретной пары:

provider + network + token

Registry должен позволять определить, поддерживается ли token.

---

## 7. Route Capability

Route считается допустимым только если все его необходимые компоненты поддерживаются.

---

## 8. Combination Capability

Перед выполнением внешнего request система должна по возможности определить:

provider + network + token + operation

является ли допустимой комбинацией.

---

## 9. No Blind Requests

Если заранее известно, что комбинация unsupported:

request не должен выполняться.

---

## 10. Configuration Boundary

Capability Registry не должен активировать disabled provider.

Если Configuration отключила provider:

его capability не должна приводить к выполнению requests.

---

## 11. Disabled Network

Если network disabled:

её capabilities не должны использоваться Scanner.

---

## 12. Disabled Token

Если token disabled:

его capability не должна использоваться Scanner.

---

## 13. Capability States

Минимально поддерживать:

- SUPPORTED;
- UNSUPPORTED;
- UNKNOWN;
- DEGRADED;
- UNAVAILABLE.

---

## 14. SUPPORTED

SUPPORTED означает, что provider официально или фактически подтверждённо поддерживает capability.

---

## 15. UNSUPPORTED

UNSUPPORTED означает, что capability не поддерживается.

Scanner не должен выполнять такой request.

---

## 16. UNKNOWN

UNKNOWN означает отсутствие достаточной информации.

UNKNOWN не должен автоматически считаться SUPPORTED.

---

## 17. DEGRADED

DEGRADED означает, что capability существует, но имеет временные ограничения.

---

## 18. UNAVAILABLE

UNAVAILABLE означает, что capability временно недоступна.

Это состояние может зависеть от Health Monitoring.

---

## 19. Static Capabilities

Некоторые capabilities могут быть определены статически.

Например:

- provider поддерживает Polygon;
- provider поддерживает конкретную operation.

---

## 20. Dynamic Capabilities

Некоторые capabilities могут зависеть от runtime information.

Например:

- временно недоступный endpoint;
- provider temporarily disabled;
- network outage.

---

## 21. Capability Source

Каждая capability должна иметь source.

Минимально:

- configuration;
- provider metadata;
- API discovery;
- static registry;
- runtime observation.

---

## 22. Source Priority

При конфликте источников должна существовать deterministic precedence policy.

Например:

explicit configuration restriction
→ provider capability
→ runtime state.

---

## 23. Configuration Override

Configuration может запретить capability даже если provider её поддерживает.

Но configuration не должна объявлять unsupported capability supported без explicit approved mechanism.

---

## 24. Provider Metadata

Если provider предоставляет официальную информацию о supported networks/tokens:

она может использоваться для построения Registry.

---

## 25. Runtime Observation

Runtime errors могут обновлять capability state.

Например:

если provider стабильно возвращает unsupported для route:

capability может перейти в UNSUPPORTED или временно DEGRADED согласно policy.

---

## 26. No Immediate Permanent Disable

Одна случайная ошибка не должна автоматически навсегда переводить capability в UNSUPPORTED.

---

## 27. Failure Threshold

Для dynamic capability может использоваться failure threshold.

---

## 28. Recovery Threshold

Для восстановления capability может использоваться success threshold.

---

## 29. Capability Refresh

Capability Registry должен поддерживать refresh.

Refresh может происходить:

- startup;
- scheduled;
- manual;
- после значимого provider configuration change.

---

## 30. Startup Refresh

При startup Registry должен загрузить обязательные capabilities до запуска scanners.

---

## 31. Scheduled Refresh

Dynamic capabilities должны обновляться согласно configuration policy.

---

## 32. Refresh Interval

Refresh interval должен быть configurable.

---

## 33. No Excessive Refresh

Registry не должен постоянно запрашивать provider metadata без необходимости.

---

## 34. Resource Manager

Все external capability discovery requests должны проходить через Resource Manager.

---

## 35. Rate Limits

Capability refresh должен учитывать provider rate limits.

---

## 36. Retry

Retry capability requests выполняется через Resource Manager/Error Handling policy.

---

## 37. Timeout

Capability discovery должен иметь timeout.

---

## 38. Failure Handling

Если refresh не удался:

предыдущая valid capability state может сохраняться до expiration, если это разрешено policy.

---

## 39. Capability Expiration

Dynamic capability data должна иметь expiration/freshness policy.

---

## 40. Stale Capability

Stale capability не должна автоматически считаться текущей.

Если capability критична для безопасности:

stale state должна привести к conservative behavior.

---

## 41. Conservative Default

Если capability неизвестна:

по умолчанию request не должен выполняться, если operation потенциально может создать false result.

---

## 42. Token Registry Integration

Capability Registry должен использовать Token Registry для проверки:

- token address;
- decimals;
- network;
- enabled status.

---

## 43. Token Registry Boundary

Capability Registry не должен становиться вторым Token Registry.

Он хранит capability, а не canonical token metadata.

---

## 44. Provider Adapter Integration

Provider Adapter предоставляет capability information, когда это возможно.

Capability Registry нормализует её.

---

## 45. Scanner Integration

Level 1 Scanner использует Capability Registry для предварительной фильтрации.

---

## 46. Level 2 Integration

Level 2 может использовать Capability Registry для проверки, что Job всё ещё соответствует поддерживаемой capability.

Но final quote validation остаётся обязательной.

---

## 47. Health Integration

Health Monitoring предоставляет runtime availability information.

---

## 48. Capability vs Health

Provider может быть:

HEALTHY

но capability может быть:

UNSUPPORTED

для конкретного token.

И наоборот:

capability может существовать, но provider быть:

UNAVAILABLE.

---

## 49. Capability vs Quote

SUPPORTED capability не означает, что конкретный quote обязательно будет успешным.

Quote validation остаётся отдельной операцией.

---

## 50. Capability vs Profitability

Capability не имеет отношения к profitability calculation.

---

## 51. Fixed Routes

Capability Registry не должен создавать новые routes.

Он только определяет, поддерживается ли уже утверждённый route.

---

## 52. Route Validation

Перед scanner request route должен пройти capability validation.

---

## 53. Route Components

Route validation должна проверять:

- network;
- input token;
- intermediate token;
- output token;
- provider;
- operation.

---

## 54. Provider Pair

Для cross-provider arbitrage Registry должен позволять определить capability каждой leg отдельно.

---

## 55. Pair Compatibility

Даже если оба providers поддерживают свои legs:

это не означает автоматически, что комбинация является valid arbitrage route.

Route policy остаётся authoritative.

---

## 56. Operations

Минимально поддерживать capability для:

- QUOTE;
- SWAP_SUPPORT_METADATA;
- FEE_METADATA;
- TOKEN_METADATA.

На текущем этапе фактическое trading execution не используется.

---

## 57. Quote Capability

Для scanner критически важна QUOTE capability.

Без неё provider не должен получать quote request.

---

## 58. Fee Capability

Если provider предоставляет fee metadata:

это может быть отражено в capability.

---

## 59. Token Metadata Capability

Если provider способен предоставлять token metadata:

это может быть отражено отдельно.

---

## 60. Storage

Capability Registry может хранить normalized capability state в SQLite.

Но SQLite не является единственным источником live provider availability.

---

## 61. Persistence

Persistent storage может использоваться для:

- previous capability state;
- diagnostics;
- recovery;
- audit.

---

## 62. Startup Recovery

После restart persisted capability state может использоваться как initial state.

Но stale dynamic capabilities должны быть refreshed перед critical use.

---

## 63. No Permanent Persistence Assumption

Старый persisted capability не должен считаться актуальным бесконечно.

---

## 64. Capability Identity

Каждая capability должна иметь deterministic identity.

Минимально:

provider + network + token + operation + route context.

---

## 65. Fingerprint

Capability fingerprint может использоваться для:

- change detection;
- deduplication;
- diagnostics.

---

## 66. Change Detection

Registry должен определять изменения capability.

Например:

SUPPORTED → UNSUPPORTED.

---

## 67. Capability Events

Значимые изменения могут создавать events:

- capability added;
- capability removed;
- capability changed;
- capability expired;
- capability recovered.

---

## 68. Event Consumers

Scanner и Health Monitoring могут использовать capability events.

---

## 69. No Direct Scanner Mutation

Scanner не должен самостоятельно изменять Capability Registry.

Он сообщает observations через approved interface.

---

## 70. Provider Adapter Reporting

Provider Adapter может сообщать normalized capability observations.

Registry принимает решение о состоянии согласно policy.

---

## 71. Conflict Resolution

Если разные sources сообщают разные states:

применяется deterministic conflict resolution.

---

## 72. Safety Priority

При конфликте:

unsafe/unknown state должен иметь приоритет над optimistic assumption для critical operations.

---

## 73. Unknown Token

Если token неизвестен Registry:

Scanner не должен отправлять request до разрешения состояния.

---

## 74. Unknown Network

Если network неизвестна:

request не должен выполняться.

---

## 75. Unknown Operation

Если operation неизвестна:

request не должен выполняться.

---

## 76. Unsupported Route

Если route unsupported:

candidate не создаётся.

---

## 77. Capability Query

Registry должен предоставлять простой query interface.

Например логически:

is_supported(provider, network, token, operation)

и:

is_route_supported(route)

Фактический API определяется implementation.

---

## 78. Batch Queries

Для Scanner должен существовать способ эффективно проверять множество capabilities без создания лишних operations.

---

## 79. No Network Calls for Static Query

Запрос к Registry для уже известной static capability не должен выполнять network request.

---

## 80. Performance

Capability lookup должен быть дешёвым и deterministic.

Он используется часто в scanner workflow.

---

## 81. Thread/Async Safety

Registry должен безопасно использоваться concurrent tasks.

---

## 82. Cache

In-memory capability state допустим как runtime state.

Это не должно превращаться в cache для live quotes.

---

## 83. Logging

Structured logging должен содержать:

- provider;
- network;
- token;
- operation;
- previous state;
- new state;
- source;
- timestamp.

Secrets запрещены.

---

## 84. Metrics

Registry должен собирать:

- supported capabilities;
- unsupported capabilities;
- unknown capabilities;
- refresh attempts;
- refresh failures;
- capability changes;
- stale capabilities.

---

## 85. Diagnostics

Diagnostics должны позволять определить:

- почему capability считается supported;
- когда она обновлялась;
- откуда получена информация;
- когда истекает;
- какие failures были зарегистрированы.

---

## 86. Testing

Обязательно тестировать:

- provider capability;
- network capability;
- token capability;
- operation capability;
- route capability;
- configuration restrictions;
- unknown state;
- stale state;
- refresh;
- expiration;
- failure threshold;
- recovery threshold;
- conflict resolution;
- batch queries;
- concurrent access;
- persistence;
- startup recovery.

---

## 87. Integration Tests

Необходимо тестировать:

Configuration → Capability Registry

Token Registry → Capability Registry

Provider Adapter → Capability Registry

Capability Registry → Level 1

Capability Registry → Level 2

Capability Registry → Health Monitoring

---

## 88. Critical Invariants

Capability Registry никогда не должна:

1. создавать новые trading routes;

2. выполнять swaps;

3. получать live quotes для profitability calculation;

4. заменять Token Registry;

5. заменять Health Monitoring;

6. заменять Resource Manager;

7. считать UNKNOWN равным SUPPORTED;

8. считать HEALTHY provider автоматически capable;

9. считать SUPPORTED capability автоматически available;

10. выполнять бесконтрольные refresh requests;

11. обходить Resource Manager;

12. навсегда блокировать capability из-за единичной transient error;

13. изменять configuration;

14. рассчитывать profitability;

15. считать stale dynamic capability актуальной без policy.

---

## 89. Главный принцип

Capability Registry должен обеспечить:

**единое и предсказуемое понимание того, какие операции разрешены и фактически поддерживаются providers, networks, tokens и routes, предотвращая заранее известные бесполезные external requests и не смешивая capability с текущей availability или profitability.**

Configuration отвечает за:

**что разрешено.**

Capability Registry отвечает за:

**что поддерживается.**

Health Monitoring отвечает за:

**что доступно сейчас.**

Scanner отвечает за:

**что имеет смысл проверять.**

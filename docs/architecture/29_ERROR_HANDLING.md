# MONIK — ERROR HANDLING

## 1. Назначение

Этот документ определяет единую архитектуру обработки ошибок Monik.

Цель:

- классифицировать ошибки;
- отделять transient failures от permanent failures;
- определять retryability;
- предотвращать каскадные сбои;
- обеспечивать безопасное восстановление;
- сохранять корректность financial results;
- обеспечивать observability;
- не допускать false-positive opportunities.

---

## 2. Главный принцип

Ошибка должна быть:

1. обнаружена;
2. классифицирована;
3. нормализована;
4. обработана согласно policy;
5. зафиксирована в observability;
6. при возможности безопасно восстановлена.

---

## 3. Error Boundary

Каждая subsystem должна обрабатывать ошибки на своей boundary.

Provider-specific errors должны преобразовываться в normalized errors внутри Adapter.

---

## 4. Normalized Error

Normalized Error должен содержать минимум:

- error code;
- category;
- severity;
- message;
- subsystem;
- operation;
- retryable;
- timestamp;
- correlation context.

---

## 5. Error Categories

Минимально поддерживать:

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
- CANCELLATION_ERROR;
- INTERNAL_ERROR;
- SECURITY_ERROR.

---

## 6. CONFIGURATION_ERROR

Используется при:

- отсутствующей configuration;
- invalid configuration;
- конфликтующих settings;
- invalid environment values.

---

## 7. VALIDATION_ERROR

Используется при:

- invalid input;
- malformed provider data;
- missing required fields;
- invalid domain state.

---

## 8. NETWORK_ERROR

Используется при:

- connection failure;
- DNS failure;
- connection reset;
- network unreachable.

---

## 9. TIMEOUT_ERROR

Используется, когда операция не завершилась в установленный timeout.

---

## 10. RATE_LIMIT_ERROR

Используется при:

- HTTP 429;
- provider rate limit;
- Resource Manager rate limit.

---

## 11. AUTH_ERROR

Используется при:

- invalid API key;
- expired credential;
- unauthorized request.

AUTH_ERROR не должен бесконечно retry.

---

## 12. PROVIDER_ERROR

Используется для normalized provider-side failures, которые не относятся к network/auth/rate limit.

---

## 13. DATABASE_ERROR

Используется при:

- connection failure;
- transaction failure;
- lock failure;
- integrity failure;
- migration failure.

---

## 14. RESOURCE_ERROR

Используется при:

- queue exhaustion;
- concurrency limit;
- resource unavailable;
- circuit breaker rejection.

---

## 15. CALCULATION_ERROR

Используется при:

- invalid financial input;
- inconsistent calculation data;
- impossible calculation state;
- precision/validation failure.

---

## 16. CANCELLATION_ERROR

Используется при explicit cancellation операции.

Cancellation не всегда является failure.

---

## 17. INTERNAL_ERROR

Используется для unexpected application failures.

Internal error должен иметь correlation ID для diagnostics.

---

## 18. SECURITY_ERROR

Используется при:

- blocked unsafe URL;
- invalid security boundary;
- secret exposure detection;
- unauthorized operation;
- suspicious input.

---

## 19. Error Severity

Минимально:

- DEBUG;
- INFO;
- WARNING;
- ERROR;
- CRITICAL.

---

## 20. Severity ≠ Retryability

Severity и retryability являются независимыми properties.

Например:

TIMEOUT может быть WARNING + retryable.

AUTH_ERROR может быть ERROR + non-retryable.

---

## 21. Retryable

Ошибка считается retryable только если повтор операции имеет разумный шанс успешного завершения и не нарушает safety.

---

## 22. Non-Retryable

Ошибки, которые нельзя безопасно повторять, должны немедленно прекращать retry loop.

---

## 23. Retry Policy

Retry policy должна учитывать:

- error category;
- operation;
- attempt count;
- provider;
- timeout;
- Retry-After;
- circuit breaker state.

---

## 24. Centralized Retry

External request retry должен контролироваться Resource Manager.

---

## 25. No Duplicate Retry

Provider Adapter не должен иметь независимый бесконтрольный retry loop поверх Resource Manager.

---

## 26. Maximum Attempts

Каждая retryable operation должна иметь maximum attempts.

---

## 27. Backoff

Retry должен использовать controlled backoff.

---

## 28. Exponential Backoff

Для повторяющихся transient failures рекомендуется exponential backoff.

---

## 29. Jitter

Retry policy должна поддерживать jitter для предотвращения synchronized retry bursts.

---

## 30. Retry-After

Если provider предоставляет Retry-After:

Resource Manager должен учитывать его в пределах configured limits.

---

## 31. Retry Budget

Retry должен иметь ограниченный budget.

---

## 32. Retry Storm

Система никогда не должна создавать:

- infinite retries;
- nested retries;
- synchronized retry storm.

---

## 33. Authentication Errors

AUTH_ERROR по умолчанию non-retryable до изменения credentials или configuration.

---

## 34. Validation Errors

VALIDATION_ERROR обычно non-retryable.

Повторение того же invalid input не должно создавать retry loop.

---

## 35. Unsupported Operations

Unsupported operation должна считаться non-retryable для текущей capability state.

---

## 36. Timeout

Timeout может быть retryable, если operation допускает безопасный retry.

---

## 37. Rate Limit

Rate limit может быть retryable при соблюдении provider policy и Retry-After.

---

## 38. Database Lock

Transient database lock может быть retryable ограниченное количество раз.

---

## 39. Database Integrity Failure

Integrity failure не должен автоматически retry без диагностики.

---

## 40. Configuration Failure

Invalid configuration должна останавливать соответствующую functionality.

---

## 41. Critical Configuration

Если invalid configuration затрагивает critical subsystem:

application не должен переходить в HEALTHY state.

---

## 42. Error Propagation

Ошибка должна передаваться вверх только если consumer может что-то сделать с ней.

---

## 43. Error Translation

Каждый boundary должен переводить низкоуровневые errors в уровень abstraction соответствующей subsystem.

---

## 44. Provider Error Translation

Например:

HTTP 429

может быть преобразован в:

RATE_LIMIT_ERROR.

---

## 45. No Raw Provider Errors

Business logic не должна зависеть от:

- HTTPError;
- AxiosError;
- provider SDK exception;
- provider-specific error class.

---

## 46. Error Context

Error context должен включать только необходимую информацию.

---

## 47. No Sensitive Context

Error context не должен содержать:

- API keys;
- tokens;
- passwords;
- private keys;
- authorization headers.

---

## 48. Error Messages

Messages должны быть понятными человеку и полезными для diagnostics.

---

## 49. Machine-Readable Codes

Каждый error должен иметь stable machine-readable code.

---

## 50. Error Code Stability

Error codes не следует менять без необходимости.

Их могут использовать:

- tests;
- alerts;
- monitoring;
- retry policy;
- operational tooling.

---

## 51. Provider Error Codes

Provider-specific error code может сохраняться как diagnostic metadata.

Но normalized error code остаётся authoritative для Monik.

---

## 52. HTTP Status

HTTP status может сохраняться в metadata.

Он не должен становиться единственным error classification mechanism.

---

## 53. Error Fingerprint

Для recurring errors может использоваться fingerprint.

Он помогает группировать одинаковые incidents.

---

## 54. No Secret Fingerprints

Fingerprint не должен использовать credentials или sensitive data.

---

## 55. Logging

Каждый significant error должен создавать structured log.

---

## 56. Error Log Fields

Минимально:

- timestamp;
- error code;
- category;
- severity;
- subsystem;
- operation;
- retryable;
- correlation ID.

---

## 57. Stack Trace

Stack trace допустим для unexpected INTERNAL_ERROR.

В production он должен быть доступен только через controlled diagnostics.

---

## 58. User-Facing Errors

Пользовательские сообщения не должны содержать:

- stack traces;
- internal paths;
- provider credentials;
- raw provider response.

---

## 59. Telegram Errors

Telegram notification должна получать безопасное normalized message.

---

## 60. No Error Leakage

Notification System не должна отправлять пользователю internal exception details.

---

## 61. Error Handling in Level 1

Level 1 должен:

- продолжать работу при non-critical provider failures;
- пропускать unavailable provider;
- фиксировать failure;
- не создавать invalid candidate.

---

## 62. Partial Level 1

Если часть providers/network unavailable:

Level 1 может завершиться PARTIAL.

---

## 63. Level 1 Critical Failure

Если невозможно получить необходимые данные для безопасной работы:

Level 1 не должен создавать false candidates.

---

## 64. Error Handling in Level 2

Level 2 должен быть более conservative.

При critical data failure:

Job не может стать CONFIRMED.

---

## 65. Level 2 Provider Failure

Если quote provider недоступен:

Job может:

- retry;
- remain queued;
- become FAILED;
- become EXPIRED

согласно policy.

---

## 66. No False Confirmation

Никакая recoverable или unknown error не должна превращаться в CONFIRMED opportunity.

---

## 67. Profit Calculation Errors

При CALCULATION_ERROR:

Opportunity не подтверждается.

---

## 68. Missing Fee

Missing required fee не должен автоматически считаться zero.

---

## 69. Missing Gas

Missing required gas не должен автоматически считаться zero.

---

## 70. Stale Data

Если required quote/fee/gas stale:

соответствующая confirmation должна быть rejected или retried согласно policy.

---

## 71. Database Failure

При критической Database failure:

- не создавать новый persistent state;
- не объявлять operations успешно завершёнными;
- следовать recovery policy.

---

## 72. Transaction Errors

Database transaction failure должен приводить к rollback/atomic recovery согласно repository policy.

---

## 73. Scheduler Errors

Failure одной scheduled task не должен автоматически останавливать весь Scheduler.

---

## 74. Critical Scheduler Failure

Если Scheduler infrastructure itself unavailable:

Health Monitoring должна зафиксировать degraded/unavailable state.

---

## 75. Notification Errors

Notification failure не должен изменять confirmed opportunity.

---

## 76. Notification Retry

Temporary Telegram failures могут retry.

Permanent errors не должны retry бесконечно.

---

## 77. Resource Manager Errors

Resource Manager должен различать:

- queue rejection;
- rate limit;
- timeout;
- circuit breaker;
- cancellation.

---

## 78. Circuit Breaker

Circuit breaker используется для предотвращения repeated calls к failing provider.

---

## 79. Circuit Breaker States

Минимально:

- CLOSED;
- OPEN;
- HALF_OPEN.

---

## 80. OPEN

В OPEN state новые requests к provider блокируются на configured interval.

---

## 81. HALF_OPEN

После cooldown ограниченное количество probe requests проверяет recovery.

---

## 82. CLOSED

После успешного recovery provider возвращается в CLOSED.

---

## 83. Circuit Breaker Scope

Circuit breaker должен иметь scope, соответствующий resource/provider/network policy.

---

## 84. No Global Provider Shutdown

Failure одного provider не должен автоматически отключать остальные providers.

---

## 85. Error Aggregation

Повторяющиеся ошибки должны агрегироваться для observability.

---

## 86. Alert Threshold

Alerts должны использовать threshold/duration, а не каждый отдельный transient failure.

---

## 87. Recovery

Recovery event должен фиксироваться.

Например:

provider recovered after timeout period.

---

## 88. Error State

Subsystem может перейти:

HEALTHY
→ DEGRADED
→ UNAVAILABLE

при накоплении failures.

---

## 89. Recovery State

После успешных operations:

UNAVAILABLE
→ DEGRADED
→ HEALTHY

согласно recovery threshold.

---

## 90. Flapping Protection

Для unstable dependency использовать hysteresis.

---

## 91. Error Rate

Provider health может учитывать error rate.

---

## 92. Error Window

Error rate должен рассчитываться на defined time window.

---

## 93. Error Budget

Для некоторых external providers может использоваться operational error budget.

---

## 94. No Error Suppression

Не скрывать errors только для уменьшения количества logs.

Использовать aggregation/sampling, но сохранять critical information.

---

## 95. Cancellation

Explicit cancellation должна быть безопасной.

Она не должна считаться provider failure.

---

## 96. Shutdown Errors

Во время graceful shutdown ожидаемые cancellation errors не должны создавать false critical alerts.

---

## 97. Startup Errors

Startup errors должны быть явно классифицированы.

---

## 98. Fatal Startup Error

Если critical subsystem не может быть initialized:

application startup должен завершиться failure.

---

## 99. Recovery After Restart

После restart errors не должны автоматически восстанавливаться как previous successful state.

State должен быть проверен заново.

---

## 100. Critical Invariants

Error Handling никогда не должен:

1. создавать infinite retry loops;

2. создавать nested uncontrolled retries;

3. считать AUTH_ERROR автоматически retryable;

4. считать VALIDATION_ERROR автоматически retryable;

5. превращать missing fee в zero;

6. превращать missing gas в zero;

7. подтверждать Opportunity после critical error;

8. скрывать provider failures;

9. останавливать весь application из-за одного provider failure без critical reason;

10. передавать raw provider exceptions в business logic;

11. логировать secrets;

12. отправлять stack traces пользователю;

13. обходить Resource Manager;

14. изменять confirmed opportunity из-за notification failure;

15. считать cancellation provider failure;

16. считать stale financial data valid;

17. выполнять retries после превышения retry budget;

18. использовать error suppression вместо правильной классификации.

---

## 101. Главный принцип

Error Handling должна обеспечить:

**предсказуемую классификацию и безопасное восстановление после ошибок без false confirmations, бесконечных retries, каскадных отказов и утечки внутренней информации.**

Каждая ошибка должна иметь понятный путь:

**detect → classify → normalize → handle → observe → recover или fail safely.**

# MONIK — ERROR HANDLING

## 1. Назначение

Error Handling — единая архитектура обработки ошибок Monik.

Она определяет:

- классификацию ошибок;
- границы ответственности;
- retry policy;
- error propagation;
- recovery;
- logging;
- diagnostics;
- поведение subsystems при сбоях.

Главный принцип:

**ошибка должна быть обработана на том уровне, который лучше всего понимает её причину и последствия.**

---

## 2. Основной принцип

Ошибка не должна:

- бесконтрольно распространяться;
- silently игнорироваться;
- превращаться в успешный результат;
- приводить к остановке всей системы без необходимости.

Каждая ошибка должна иметь определённый:

- type;
- severity;
- source;
- status;
- recovery policy.

---

## 3. Error Categories

Минимально поддерживать категории:

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

## 4. Configuration Error

CONFIGURATION_ERROR означает, что configuration:

- отсутствует;
- имеет неправильный формат;
- содержит недопустимое значение;
- нарушает cross-field validation;
- не позволяет безопасно запустить subsystem.

---

## 5. Configuration Error Policy

Критическая configuration error должна останавливать startup.

Нельзя запускать production workflow с неизвестной или небезопасной configuration.

---

## 6. Validation Error

VALIDATION_ERROR используется, когда входные данные не соответствуют ожидаемым требованиям.

Например:

- invalid token address;
- invalid amount;
- invalid route;
- missing required field.

---

## 7. Network Error

NETWORK_ERROR означает временную или постоянную проблему network communication.

Например:

- connection failure;
- DNS failure;
- connection reset;
- unreachable endpoint.

---

## 8. Timeout Error

TIMEOUT_ERROR возникает, когда операция не завершилась в пределах установленного timeout.

Timeout не означает автоматически, что операция была выполнена или не выполнена на внешней стороне.

---

## 9. Rate Limit Error

RATE_LIMIT_ERROR означает, что provider ограничил количество requests.

Такая ошибка должна передаваться Resource Manager.

---

## 10. Authentication Error

AUTH_ERROR означает:

- invalid API key;
- expired credentials;
- invalid Telegram credentials;
- rejected authentication.

Authentication errors обычно являются permanent errors до изменения credentials.

---

## 11. Provider Error

PROVIDER_ERROR используется для provider-specific failures, которые не относятся к transport-level errors.

Например:

- unsupported pair;
- invalid provider response;
- provider internal error;
- unavailable route.

---

## 12. Database Error

DATABASE_ERROR используется для:

- connection failure;
- transaction failure;
- lock timeout;
- migration failure;
- integrity failure;
- query failure.

---

## 13. Resource Error

RESOURCE_ERROR используется для внутренних ограничений:

- queue full;
- concurrency limit;
- resource unavailable;
- capacity exceeded.

---

## 14. Calculation Error

CALCULATION_ERROR возникает при невозможности безопасно выполнить финансовый расчёт.

Например:

- missing mandatory input;
- invalid decimal;
- inconsistent units;
- impossible conversion.

---

## 15. Internal Error

INTERNAL_ERROR означает непредвиденную ошибку приложения.

Она должна логироваться с достаточной diagnostic information.

---

## 16. Cancellation Error

CANCELLATION_ERROR означает, что operation была отменена:

- user;
- Scheduler;
- shutdown;
- timeout policy;
- supervisor.

Cancellation не должна автоматически считаться provider failure.

---

## 17. Error Severity

Минимально поддерживать:

- DEBUG;
- INFO;
- WARNING;
- ERROR;
- CRITICAL.

---

## 18. Severity Meaning

DEBUG:

техническая информация для разработки.

INFO:

нормальное operational событие.

WARNING:

проблема, не нарушающая основную работу.

ERROR:

операция завершилась неуспешно.

CRITICAL:

состояние, при котором продолжение работы может быть небезопасным.

---

## 19. Error Code

Каждая нормализованная ошибка должна иметь стабильный error code.

Например:

- CONFIG_INVALID;
- PROVIDER_TIMEOUT;
- PROVIDER_RATE_LIMIT;
- DATABASE_LOCK;
- FEE_UNKNOWN;
- QUOTE_INVALID;
- QUOTE_STALE;
- PROFIT_CALCULATION_FAILED.

---

## 20. Error Message

Error message должна быть понятной для diagnostics.

Она не должна содержать:

- API keys;
- bot tokens;
- private keys;
- authentication headers;
- secrets.

---

## 21. Error Context

Error context может содержать:

- subsystem;
- operation;
- provider;
- network;
- token;
- amount;
- job ID;
- scan ID;
- execution ID.

Sensitive data должна быть исключена.

---

## 22. Exception Normalization

External exceptions должны преобразовываться в application-level errors.

Business logic не должна зависеть от конкретных HTTP/client library exceptions.

---

## 23. Error Boundary

Каждая subsystem должна иметь boundary, на которой external errors преобразуются в normalized application errors.

---

## 24. Adapter Errors

Aggregator Adapter отвечает за преобразование provider-specific errors в normalized provider errors.

---

## 25. Resource Manager Errors

Resource Manager отвечает за:

- timeout;
- retry;
- rate limit;
- concurrency;
- backoff.

Subsystem не должна повторно реализовывать эту логику без необходимости.

---

## 26. Scanner Errors

Scanner должен отличать:

- invalid quote;
- provider failure;
- timeout;
- configuration problem;
- internal failure.

---

## 27. Level 1 Error Policy

Ошибка одного:

- token;
- amount;
- provider;
- route;
- network

не должна автоматически останавливать весь Level 1 scan.

---

## 28. Level 1 Partial Scan

Если часть Level 1 requests завершилась ошибкой:

scan может получить:

PARTIAL

если policy допускает продолжение.

---

## 29. Level 1 Complete Failure

Если scanner не смог получить достаточный набор данных для meaningful scan:

scan получает:

FAILED

а не COMPLETED.

---

## 30. Level 2 Error Policy

Ошибка critical data во время Level 2 confirmation должна предотвращать confirmation.

Например:

- stale quote;
- missing fee;
- invalid output;
- unavailable required provider.

---

## 31. No False Success

Ошибка не должна превращаться в:

- profitable;
- confirmed;
- sent.

Если critical information отсутствует:

результат должен быть rejected/failed согласно policy.

---

## 32. UNKNOWN Values

UNKNOWN не является zero.

Особенно для:

- fees;
- gas;
- output;
- profitability components.

---

## 33. Retry Classification

Ошибки должны классифицироваться как:

- retryable;
- non-retryable;
- conditionally retryable.

---

## 34. Retryable

Обычно retryable:

- temporary network failure;
- timeout;
- temporary provider outage;
- rate limit.

---

## 35. Non-Retryable

Обычно non-retryable:

- invalid configuration;
- invalid credentials;
- invalid token;
- unsupported route;
- malformed request;
- permanent validation error.

---

## 36. Conditionally Retryable

Некоторые errors требуют context.

Например:

- provider error;
- database lock;
- resource capacity;
- temporary authentication issue.

---

## 37. Retry Ownership

Retry должен выполняться на уровне, который владеет соответствующей operation.

Для внешних requests:

Resource Manager.

Для application jobs:

Scheduler/Job policy.

---

## 38. No Nested Retry Storm

Не допускать ситуации:

Adapter retry
+
Resource Manager retry
+
Scanner retry
+
Scheduler retry

без общего лимита.

---

## 39. Retry Budget

Каждая retryable operation должна иметь ограниченный retry budget.

---

## 40. Max Attempts

Количество attempts должно быть configuration-driven.

Не использовать бесконечный retry.

---

## 41. Backoff

Retry должен использовать backoff.

Минимально поддерживать:

- initial delay;
- maximum delay;
- backoff factor.

---

## 42. Jitter

Для конкурентных requests может использоваться jitter.

Это предотвращает synchronized retry storm.

---

## 43. Rate Limit Backoff

RATE_LIMIT_ERROR должен использовать provider-specific или Resource Manager policy.

---

## 44. Retry After

Если provider предоставляет Retry-After:

Resource Manager должен учитывать его.

---

## 45. Timeout Policy

Каждая external operation должна иметь timeout.

Timeout должен быть configuration-driven или задан approved subsystem policy.

---

## 46. Timeout Propagation

Timeout не должен оставлять бесконтрольные background tasks.

После timeout operation должна быть корректно отменена либо завершена согласно client policy.

---

## 47. Cancellation

Cancellation должна быть cooperative.

Subsystem должна корректно прекращать работу после cancellation signal.

---

## 48. Shutdown

При shutdown:

- новые tasks не создаются;
- retry loops прекращаются;
- queued operations отменяются;
- active operations получают cancellation.

---

## 49. Error Propagation

Ошибка должна передаваться вверх только если вышестоящий уровень действительно должен принять решение.

Не передавать низкоуровневые implementation exceptions напрямую в business logic.

---

## 50. Error Recovery

Recovery policy зависит от error category.

Например:

provider timeout
→ retry/backoff

invalid configuration
→ startup failure

stale quote
→ reject candidate

database corruption
→ critical failure

---

## 51. Provider Failure Isolation

Один provider failure не должен автоматически останавливать другие providers.

---

## 52. Network Failure Isolation

Проблема одной network не должна автоматически останавливать другие enabled networks.

---

## 53. Token Failure Isolation

Проблема одного token не должна автоматически останавливать весь scan.

---

## 54. Notification Failure Isolation

Telegram failure не должен отменять подтверждённую opportunity.

---

## 55. Database Failure

Если Database становится недоступной для критической операции:

application должен следовать explicit safety policy.

Нельзя silently продолжать работу с неизвестным persistent state.

---

## 56. Critical Database Failure

Если невозможно гарантировать persistence критического состояния:

application может потребовать controlled shutdown.

---

## 57. Configuration Failure

Если configuration invalid:

application не должен переходить в production scanning mode.

---

## 58. Fee Failure

Если обязательная fee неизвестна:

profitability confirmation не должна считаться безопасной.

---

## 59. Gas Failure

Если gas является обязательным cost component и его нельзя получить:

Level 2 не должен считать final profitability подтверждённой без explicit policy.

---

## 60. Quote Failure

Если required quote отсутствует:

opportunity не подтверждается.

---

## 61. Quote Stale

STALE quote должен иметь отдельный error code:

QUOTE_STALE

Он не должен использоваться как fresh confirmation data.

---

## 62. Invalid Quote

INVALID quote получает:

QUOTE_INVALID

и исключается из profitability calculation.

---

## 63. Inconsistent Quote

Если quote содержит противоречивые данные:

например:

input amount не соответствует requested amount,

quote должен быть rejected.

---

## 64. Profitability Error

Если Profit Calculator не может выполнить безопасный calculation:

Level 2 не должен подтверждать opportunity.

---

## 65. Notification Error

Notification failure должна иметь собственный lifecycle.

Она не должна изменять final calculation.

---

## 66. Error State Persistence

Critical errors, влияющие на recovery или audit, должны сохраняться в persistent state согласно retention policy.

---

## 67. Error History

Не требуется сохранять каждую техническую ошибку навсегда.

Retention должен быть configuration-driven.

---

## 68. Error Aggregation

Повторяющиеся одинаковые ошибки могут агрегироваться для diagnostics.

Например:

provider timeout за 5 минут.

Но aggregation не должна скрывать critical state.

---

## 69. Error Rate

Metrics должны позволять определить error rate по:

- subsystem;
- provider;
- network;
- operation;
- error code.

---

## 70. Health Degradation

Высокий error rate может переводить subsystem/provider в degraded state.

---

## 71. Degraded Provider

Provider может считаться:

- HEALTHY;
- DEGRADED;
- UNAVAILABLE.

Фактическое состояние определяется health/capability/resource policies.

---

## 72. Circuit Breaker

Resource Manager может использовать circuit breaker для providers.

Circuit breaker должен предотвращать бесполезные requests при длительном outage.

---

## 73. Circuit Recovery

Circuit breaker должен иметь controlled recovery mechanism.

После периода cooldown можно выполнять ограниченное количество probe requests.

---

## 74. No Permanent Lockout

Circuit breaker не должен оставлять provider permanently unavailable без возможности recovery.

---

## 75. Diagnostics

Diagnostics должны позволять определить:

- когда ошибка произошла;
- какая subsystem;
- какая operation;
- какой provider;
- какой network;
- какой Job/Scan;
- какой error code;
- сколько retries;
- финальный status.

---

## 76. Structured Logging

Все application errors должны использовать structured logging.

Минимальные поля:

- timestamp;
- severity;
- error code;
- subsystem;
- operation;
- status.

---

## 77. Correlation IDs

Связанные operations должны использовать correlation identifiers.

Например:

- scan ID;
- Job ID;
- execution ID;
- notification ID.

---

## 78. No Secret Logging

Никогда не логировать:

- private keys;
- API keys;
- bot tokens;
- passwords;
- authentication headers.

---

## 79. User-Facing Errors

User-facing error messages должны быть понятными.

Не показывать пользователю raw stack trace без необходимости.

---

## 80. Testing

Обязательно тестировать:

- configuration errors;
- validation errors;
- provider errors;
- timeout;
- rate limit;
- authentication;
- retry;
- backoff;
- jitter;
- cancellation;
- shutdown;
- database errors;
- stale quote;
- invalid quote;
- unknown fees;
- calculation errors;
- notification errors;
- circuit breaker;
- recovery.

---

## 81. Critical Invariants

Error Handling никогда не должен:

1. считать ошибку успешным результатом;

2. считать UNKNOWN равным zero;

3. превращать stale quote в fresh quote;

4. подтверждать opportunity при отсутствии critical data;

5. создавать бесконечные retry loops;

6. создавать nested retry storms;

7. логировать secrets;

8. останавливать всю систему из-за изолированной ошибки provider;

9. silently игнорировать critical database failure;

10. превращать Telegram failure в отмену подтверждённой opportunity;

11. передавать raw provider exceptions через всю архитектуру;

12. обходить Resource Manager для retry/rate-limit logic;

13. восстанавливать cancelled operation как successful;

14. продолжать production workflow после критической configuration error.

---

## 82. Главный принцип

Error Handling должен обеспечить:

**предсказуемое, безопасное и диагностируемое поведение Monik при любых ожидаемых и неожиданных сбоях, сохраняя изоляцию subsystems и не позволяя ошибкам превращаться в ложные прибыльные opportunities.**

Ошибка должна быть:

**обнаружена → классифицирована → обработана → залогирована → при необходимости восстановлена или передана выше.** 

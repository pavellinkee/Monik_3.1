# MONIK — RESOURCE MANAGER

## 1. Назначение

Resource Manager — центральная подсистема контроля доступа к внешним ресурсам Monik.

Он отвечает за:

- concurrency;
- rate limits;
- resource locks;
- priority;
- retry coordination;
- cooldown;
- circuit breaker;
- backpressure;
- resource availability;
- безопасное предоставление ресурсов Scheduler и workers.

Главный принцип:

**ни один внешний API request не должен выполняться в обход Resource Manager.**

---

## 2. Что является ресурсом

Resource Manager должен поддерживать ресурсы различного уровня.

В зависимости от реального API ресурсом может быть:

- aggregator;
- aggregator + network;
- aggregator + API key;
- aggregator + endpoint;
- aggregator + network + endpoint;
- другой scope, необходимый согласно официальным ограничениям API.

Конкретный scope определяется Adapter и конфигурацией.

---

## 3. Минимальный необходимый scope

Lock должен быть настолько узким, насколько это возможно.

Если 1inch на Polygon и 1inch на другой сети могут безопасно работать параллельно, они не должны блокировать друг друга.

Если ограничение относится ко всему API key:

lock должен охватывать соответствующий API key scope.

Не создавать более широкий lock без технической необходимости.

---

## 4. Resource Identity

Каждый ресурс должен иметь deterministic identity.

Например:

aggregator + network + endpoint

или:

aggregator + API key

Resource identity не должен зависеть от случайного runtime ID.

---

## 5. Resource State

Каждый ресурс должен иметь состояние.

Минимально:

- AVAILABLE;
- BUSY;
- RATE_LIMITED;
- COOLDOWN;
- CIRCUIT_OPEN;
- DISABLED;
- UNKNOWN.

---

## 6. AVAILABLE

AVAILABLE означает:

- ресурс доступен;
- нет активного блокирующего lock;
- rate limit позволяет request;
- circuit breaker не блокирует запрос;
- ресурс может быть предоставлен task.

---

## 7. BUSY

BUSY означает, что ресурс используется текущей операцией согласно установленному lock scope.

Другие операции, требующие тот же конфликтующий ресурс, должны ждать.

Если ресурс допускает concurrency > 1, BUSY не означает абсолютную блокировку.

В этом случае Resource Manager должен отслеживать текущее количество использований.

---

## 8. RATE_LIMITED

RATE_LIMITED означает, что дальнейшие requests временно запрещены из-за rate limit.

Если API предоставляет:

`Retry-After`

Resource Manager должен использовать его.

Нельзя продолжать отправлять requests до истечения допустимого периода.

---

## 9. COOLDOWN

COOLDOWN используется для временной паузы после определённых ошибок или ограничений.

Cooldown не означает:

UNSUPPORTED.

После окончания cooldown ресурс может снова стать AVAILABLE.

---

## 10. Circuit Breaker

Для каждого соответствующего ресурса поддерживать:

CLOSED

OPEN

HALF_OPEN

CLOSED:

обычная работа.

OPEN:

requests временно блокируются.

HALF_OPEN:

разрешается ограниченная проверочная операция.

Успешная проверка возвращает ресурс в CLOSED.

Неудачная возвращает в OPEN.

---

## 11. Circuit Breaker не меняет Capability

Circuit Breaker не должен изменять Capability Registry.

Если API временно недоступен:

это не означает, что:

network = unsupported

или:

token = unsupported.

Capability изменяется только через соответствующий capability/maintenance механизм.

---

## 12. Resource Acquisition

Перед внешним API request worker должен запросить ресурс.

Запрос должен содержать:

- task ID;
- task type;
- priority;
- resource identity;
- operation type;
- network;
- aggregator;
- endpoint, если применимо.

---

## 13. Resource Lease

При предоставлении ресурса Resource Manager выдаёт lease/handle.

Worker использует этот lease для выполнения разрешённой операции.

После завершения операции lease должен быть освобождён.

Освобождение должно происходить даже при exception.

---

## 14. Защита от утечки lock

Resource Manager должен гарантировать освобождение ресурса при:

- success;
- exception;
- timeout;
- cancellation;
- worker crash, если процесс продолжает работать;
- graceful shutdown.

Runtime lock не должен навсегда оставаться занятым из-за исключения.

---

## 15. Lease Timeout

Для операций, которые могут зависнуть, должен существовать защитный timeout.

Если lease превышает допустимое время:

Resource Manager должен определить состояние операции.

Нельзя просто освободить ресурс, пока внешний request всё ещё может выполняться и нарушать rate/concurrency constraints.

Сначала необходимо безопасно завершить или признать операцию потерянной согласно policy конкретного Adapter.

---

## 16. Priority

Resource Manager получает priority от Scheduler.

Базовый порядок:

Level 2

>

Level 1 SELL-ready

>

Level 1 BUY

>

Maintenance

Приоритет применяется только при конфликте за ресурс.

---

## 17. FIFO внутри одного priority

Если две задачи имеют одинаковый priority и требуют один ресурс:

по умолчанию используется FIFO.

Порядок определяется:

- priority;
- created_at;
- sequence number.

Profitability не должна менять порядок автоматически.

---

## 18. Level 2 Priority

Если Level 2 и Level 1 ждут один ресурс:

Level 2 получает его первым после завершения текущей неделимой операции.

Resource Manager не должен прерывать уже выполняемый безопасный API request только ради передачи ресурса Level 2.

---

## 19. SELL Priority

Если Level 1 SELL-ready task конкурирует с Level 1 BUY:

SELL получает ресурс первым.

Если BUY уже выполняется:

не прерывать его без безопасного механизма cancellation.

После освобождения ресурса SELL получает следующий доступ.

---

## 20. Maintenance Priority

Maintenance имеет самый низкий priority.

Если ресурс необходим:

- Level 2;
- Level 1 SELL;
- Level 1 BUY;

Maintenance должна ждать.

Maintenance не должна блокировать scanning work.

---

## 21. Concurrency

Resource Manager должен отдельно контролировать:

1. logical task concurrency;
2. resource concurrency.

Например:

Level 2:

max_parallel = 20

но 1inch:

max_concurrent = 2

Это означает:

до 20 Level 2 workflows могут существовать одновременно,

но одновременно использовать конкретный 1inch resource могут только 2 операции.

---

## 22. Rate Limit

Rate limit должен поддерживать как минимум:

- requests per second;
- requests per minute;
- burst, если API его предоставляет;
- cooldown;
- Retry-After.

Конкретные значения не должны быть hard-coded, если они могут изменяться конфигурацией или официальными правилами API.

---

## 23. Sliding Window

Если API использует временное окно:

Resource Manager должен использовать соответствующий механизм window tracking.

Например:

10 requests / second

означает, что система не должна отправлять 11-й request до момента, когда он снова становится разрешённым.

---

## 24. Token Bucket

Если API имеет burst allowance:

может использоваться token bucket или эквивалентная модель.

Выбранная реализация должна точно соблюдать фактические ограничения API.

---

## 25. Retry-After

При HTTP 429:

если присутствует Retry-After:

использовать его как минимум для соответствующего resource scope.

Не выполнять немедленный повторный request.

---

## 26. HTTP 5xx

5xx обычно рассматриваются как Temporary Error.

Resource Manager может использовать:

- retry;
- exponential backoff;
- jitter;
- circuit breaker.

Нельзя выполнять бесконечные retries.

---

## 27. Timeout

Timeout должен быть классифицирован как Temporary Error, если причина соответствует временной недоступности.

Timeout не означает:

unsupported.

---

## 28. Authentication Error

Ошибки authentication/authorization обычно являются Permanent Error до изменения credentials.

Не выполнять бесконечный retry.

Resource Manager должен передать ошибку Supervisor/diagnostics.

---

## 29. Invalid Request

Invalid request не должен автоматически повторяться бесконечно.

Если ошибка вызвана bug в Adapter:

она должна быть передана как Data/Permanent Error.

---

## 30. Retry Coordination

Resource Manager должен координировать retry с Scheduler.

Не создавать отдельные uncontrolled background retries внутри Adapter.

Adapter сообщает:

- error;
- retryability;
- Retry-After, если есть;
- relevant metadata.

Resource Manager/Scheduler решает, когда повторить операцию.

---

## 31. Exponential Backoff

Default retry strategy:

exponential backoff + jitter.

Например:

attempt 1 → короткая задержка

attempt 2 → увеличенная задержка

attempt 3 → ещё большая задержка

Конкретные значения должны быть конфигурируемыми.

---

## 32. Максимальное количество Retry

Default:

3 attempts.

Количество должно быть конфигурируемым.

Нельзя использовать бесконечные retry loops.

---

## 33. Retry и Priority

Retry не должен автоматически получать более высокий priority, чем исходная операция.

Он сохраняет исходный task priority, если отдельная policy не определяет другое.

---

## 34. Retry и Deduplication

Retry существующей операции не создаёт новый Level 2 Job.

Retry является частью того же workflow.

---

## 35. Backpressure

Если ресурс перегружен:

Resource Manager должен создавать backpressure.

Нельзя позволять workers создавать бесконечное количество ожидающих requests.

---

## 36. Queue Limits

Очередь ожидающих resource requests должна иметь контролируемый размер.

Если очередь переполнена:

Resource Manager применяет установленную policy:

- отклонение;
- deduplication;
- ожидание;
- backpressure.

Нельзя молча терять уже созданный критический Level 2 Job.

---

## 37. Waiting State

Task, которая ожидает ресурс, должна иметь состояние:

WAITING_RESOURCE.

Это состояние должно быть видно Scheduler/observability.

---

## 38. Resource Wait Metrics

Система должна собирать:

- количество ожидающих requests;
- среднее время ожидания;
- максимальное время ожидания;
- время получения ресурса;
- количество отказов;
- количество rate-limit waits.

---

## 39. Resource Starvation

Resource Manager не должен допускать бесконечного starvation.

Высокоприоритетные задачи имеют приоритет, но при длительной нагрузке Scheduler может использовать fairness policy, если это не нарушает критические priority rules и API limits.

---

## 40. Fairness

Fairness не должна:

- нарушать Level 2 priority;
- нарушать rate limits;
- нарушать active locks;
- нарушать fixed-route requirements.

Она применяется только внутри допустимого scheduler/resource policy.

---

## 41. Parallel Resources

Если task требует несколько независимых ресурсов:

Resource Manager должен уметь управлять их совместным получением.

Нельзя создавать deadlock из-за неправильного порядка acquisition.

---

## 42. Multi-resource Acquisition

Если операция требует:

Resource A

и:

Resource B

они должны приобретаться в deterministic order.

Например:

resource identity в отсортированном порядке.

Это снижает вероятность deadlock.

---

## 43. Partial Acquisition

Если task получила Resource A, но не может получить Resource B:

она не должна бесконечно удерживать A.

Resource Manager должен:

- освободить A;
- либо использовать атомарный acquisition mechanism;
- затем повторить попытку согласно policy.

---

## 44. Deadlock Prevention

Resource Manager должен предотвращать deadlock.

Нельзя допускать:

Task A:

A → ждёт B

Task B:

B → ждёт A

Для этого использовать deterministic acquisition order или другой надёжный механизм.

---

## 45. Resource Release Order

При освобождении нескольких ресурсов использовать обратный порядок acquisition, если это необходимо для корректности lock management.

---

## 46. Resource Health

Resource Manager должен получать информацию о состоянии:

- availability;
- rate limit;
- circuit breaker;
- recent errors;
- latency.

Эта информация доступна Supervisor и diagnostics.

---

## 47. Latency Tracking

Для каждого ресурса измерять:

- request duration;
- average latency;
- recent latency;
- timeout rate.

Это используется для observability и диагностики.

Не использовать latency как скрытый механизм изменения бизнес-логики Scanner.

---

## 48. Resource Failure Isolation

Ошибка одного агрегатора не должна автоматически останавливать другие агрегаторы.

Например:

1inch недоступен.

Это не должно блокировать:

- 0x;
- Velora;
- Uniswap;

если они используют независимые resources.

---

## 49. Network Isolation

Если проблема возникает в Polygon:

не блокировать автоматически тот же aggregator в другой сети, если ресурс scope не требует этого.

Resource identity должен соответствовать реальному scope ограничения.

---

## 50. Endpoint Isolation

Если rate limit относится только к конкретному endpoint:

не блокировать остальные endpoint того же агрегатора.

Если официальный API ограничивает весь API key:

использовать более широкий resource scope.

---

## 51. API Key Scope

Если несколько requests используют один API key:

Resource Manager должен учитывать общий limit этого key.

Нельзя создавать отдельные независимые rate-limit buckets, если API фактически ограничивает общий key.

---

## 52. Capability Independence

Resource Manager не определяет:

- token supported;
- network supported;
- route supported.

Это ответственность Capability Registry.

Resource Manager определяет только runtime доступность ресурса.

---

## 53. Maintenance Interaction

Maintenance может использовать Resource Manager для:

- capability requests;
- fee discovery;
- health checks;
- other maintenance API calls.

Maintenance requests имеют низкий priority.

---

## 54. Fee Discovery Interaction

Fee discovery также проходит через Resource Manager.

Если несколько fee requests могут быть объединены:

Fee subsystem должна передать Resource Manager одну grouped/batched operation вместо множества отдельных requests.

---

## 55. Batch Requests

Resource Manager должен поддерживать понятие batch/grouped request, если внешний API это позволяет.

Batch считается одной логической операцией, но внутренне должен учитывать фактическое потребление rate limit согласно правилам API.

Нельзя считать batch автоматически одним request, если API считает каждый элемент отдельно.

---

## 56. Request Accounting

Для каждого request/resource необходимо хранить или вычислять:

- request count;
- timestamp;
- resource;
- endpoint;
- response status;
- retry count.

Это необходимо для корректного rate-limit accounting.

---

## 57. Rate Limit Changes

Если официальный API изменил rate limit:

изменяется соответствующая configuration/Adapter policy.

Resource Manager не должен требовать переписывания Scanner.

---

## 58. Configuration

Resource Manager должен получать конфигурацию для:

- max concurrency;
- rate limits;
- retry;
- backoff;
- cooldown;
- circuit breaker;
- queue limits;
- timeouts.

Secrets не должны находиться в Resource Manager configuration.

---

## 59. Dynamic Limits

Если API предоставляет динамический limit или headers, Resource Manager должен учитывать фактическую информацию.

Например:

- Retry-After;
- remaining requests;
- reset time.

Не игнорировать серверные ограничения ради локальной конфигурации.

---

## 60. Safe Defaults

Если неизвестно, какой rate limit действует:

использовать консервативное значение.

Не использовать агрессивный unlimited mode.

Если невозможно безопасно определить допустимую частоту запросов:

resource может быть временно недоступен до определения корректной policy.

---

## 61. No Unlimited Concurrency

Запрещено использовать:

unlimited concurrency

для production API.

Каждый внешний ресурс должен иметь контролируемую concurrency.

---

## 62. Resource Manager API

Внутренний интерфейс Resource Manager должен позволять:

- acquire;
- release;
- try_acquire;
- get_state;
- get_metrics;
- reset_circuit;
- apply_cooldown;
- update_limits.

Конкретный публичный API может отличаться, но функциональность должна быть доступна соответствующим подсистемам.

---

## 63. Try Acquire

try_acquire должен возвращать результат без бесконечного ожидания.

Например:

- acquired;
- unavailable;
- rate_limited;
- circuit_open.

Scheduler решает, что делать дальше.

---

## 64. Acquire

Acquire может ожидать ресурс.

Ожидание должно быть cancellation-aware.

Если task отменена во время ожидания:

request удаляется из очереди.

---

## 65. Cancellation

Cancellation должна корректно обрабатывать:

- queued resource request;
- waiting resource request;
- acquired resource;
- active operation.

После cancellation не должно оставаться потерянных locks.

---

## 66. Crash Safety

Runtime locks не должны сохраняться как вечные locks после process restart.

После restart Resource Manager создаёт runtime resource state заново.

Persisted state используется для recovery workflow, но не для восстановления старых in-memory locks.

---

## 67. Recovery

После restart Resource Manager должен:

1. загрузить configuration;
2. инициализировать resources;
3. восстановить rate-limit metadata, если это безопасно;
4. reset runtime locks;
5. восстановить circuit state согласно policy;
6. сообщить Scheduler готовность.

---

## 68. Circuit Recovery

Не считать ресурс автоматически здоровым после restart, если предыдущий state показывал серьёзную проблему.

Однако нельзя навсегда сохранять OPEN без возможности проверки.

Использовать controlled HALF_OPEN/health check policy.

---

## 69. Observability

Resource Manager должен предоставлять:

- resource state;
- current usage;
- queue size;
- rate-limit status;
- circuit state;
- cooldown;
- recent errors;
- latency;
- retries.

---

## 70. Logging

Каждая resource operation должна иметь structured logging:

- task ID;
- resource ID;
- operation;
- acquire time;
- release time;
- wait duration;
- execution duration;
- status;
- error category.

Secrets запрещены.

---

## 71. Testing

Обязательно тестировать:

- concurrency;
- resource locks;
- priority;
- FIFO;
- rate limits;
- Retry-After;
- retry;
- exponential backoff;
- circuit breaker;
- cooldown;
- cancellation;
- queue limits;
- backpressure;
- multi-resource acquisition;
- deadlock prevention;
- resource release;
- crash/restart;
- independent aggregator isolation;
- network isolation;
- endpoint isolation;
- API key scope.

---

## 72. Critical Invariants

Resource Manager никогда не должен нарушать:

1. Resource concurrency limits.

2. Aggregator rate limits.

3. API key limits.

4. Active resource locks.

5. Level 2 priority при конфликте.

6. Level 1 SELL priority при конфликте с BUY.

7. Independent resources могут работать параллельно.

8. Runtime locks освобождаются после завершения операции.

9. Cancellation не оставляет permanent lock.

10. Retry не создаёт uncontrolled requests.

11. Circuit breaker не меняет Capability Registry.

12. Unknown rate limit не превращается в unlimited.

13. Один неисправный aggregator не блокирует независимые resources.

14. Multi-resource acquisition не создаёт deadlock.

---

## 73. Главный принцип

Resource Manager должен обеспечить:

**максимально возможное использование внешних API без нарушения их ограничений, без конфликтов между задачами и без неконтролируемого количества запросов.**

При сомнении между скоростью и безопасностью resource policy:

**приоритет имеет безопасность и соблюдение ограничений API.**

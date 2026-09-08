# MONIK — RESOURCE MANAGER

## 1. Назначение

Resource Manager — централизованный слой управления всеми внешними ресурсами и ограничениями Monik.

Он отвечает за:

- API rate limits;
- concurrency;
- request priority;
- retries;
- cooldown;
- timeouts;
- backpressure;
- request scheduling;
- provider-specific restrictions;
- предотвращение неконтролируемого количества requests.

Главный принцип:

**ни один внешний API request не должен выполняться в обход Resource Manager.**

---

## 2. Основные потребители

Resource Manager используется:

- Level 1 Scanner;
- Level 2 Scanner;
- Fee System;
- Capability Registry;
- Maintenance;
- Conversion/Market Data subsystems;
- Aggregator Adapters.

---

## 3. Центральное управление

Resource Manager является единой точкой контроля внешних requests.

Не создавать отдельные независимые rate-limit механизмы внутри каждого Scanner.

Provider-specific ограничения могут находиться в configuration, но enforcement выполняется Resource Manager.

---

## 4. Request Model

Каждый внешний request должен иметь normalized request context.

Минимально:

- request ID;
- task ID;
- subsystem;
- aggregator/provider;
- network;
- operation;
- priority;
- created_at;
- timeout;
- retry policy.

---

## 5. Request ID

Каждый request получает unique request ID.

Он используется для:

- logging;
- tracing;
- diagnostics;
- retry tracking;
- metrics.

---

## 6. Task ID

Request должен быть связан с task.

Например:

- Level 1 Scan Task;
- Level 2 Job;
- Fee Discovery Task;
- Capability Discovery Task.

---

## 7. Opportunity ID

Если request относится к Opportunity:

он должен также содержать Opportunity ID.

---

## 8. Priority

Минимальные priority levels:

1. LEVEL_2;
2. LEVEL_1_SELL;
3. LEVEL_1_BUY;
4. MAINTENANCE;
5. DISCOVERY.

Чем выше priority, тем раньше request должен получить ресурс при конкуренции.

---

## 9. Level 2 Priority

Level 2 имеет priority выше Level 1.

Это необходимо для быстрой проверки уже найденных возможностей.

---

## 10. Level 1 SELL

SELL requests Level 1 имеют более высокий priority, чем BUY requests Level 1.

Это позволяет быстрее завершать уже начатую цепочку поиска.

---

## 11. Maintenance

Maintenance requests имеют более низкий priority.

Они не должны вытеснять Level 2 и обычный scanning без необходимости.

---

## 12. Discovery

Capability/Fee discovery имеет низкий priority.

Он выполняется тогда, когда это позволяет текущая нагрузка.

---

## 13. Queue

Resource Manager должен иметь централизованную очередь requests.

Очередь должна учитывать:

- priority;
- creation time;
- provider;
- resource availability;
- task state.

---

## 14. Fairness

Priority не должен приводить к бесконечному голоданию низкоприоритетных задач.

Если система долго занята Level 2:

Maintenance и Discovery должны иметь возможность получить ресурс согласно starvation-prevention policy.

---

## 15. Provider Isolation

Каждый внешний provider должен иметь собственный resource context.

Например:

- 1inch;
- 0x;
- Velora;
- Uniswap.

Проблема одного provider не должна блокировать остальные.

---

## 16. Network Isolation

Если provider имеет отдельные ограничения по network:

Resource Manager должен учитывать их отдельно.

Например:

Ethereum и Polygon могут иметь разные limits.

---

## 17. Rate Limit

Resource Manager должен поддерживать provider-specific rate limits.

Минимально:

- requests per second;
- requests per minute;
- requests per window;
- burst limit.

Конкретные значения находятся в configuration.

---

## 18. Concurrency Limit

Для каждого provider/resource context может существовать максимальное количество одновременно выполняемых requests.

Например:

max_concurrency = N

Значение не должно быть hard-coded внутри Scanner.

---

## 19. Rate Limit и Concurrency — разные ограничения

Не смешивать:

rate limit

и:

concurrency limit.

Можно иметь:

- 10 concurrent requests;
- 5 requests per second.

Оба ограничения должны соблюдаться одновременно.

---

## 20. Burst

Если provider допускает burst:

Resource Manager может использовать burst capacity.

Если burst не разрешён:

requests должны равномерно распределяться согласно rate policy.

---

## 21. Retry

Retries централизуются Resource Manager.

Scanner и другие consumers не должны создавать собственные бесконечные retry loops.

---

## 22. Retryable Errors

Обычно retryable:

- timeout;
- connection reset;
- temporary network error;
- 429;
- 500;
- 502;
- 503;
- 504.

Конкретная provider policy может расширять или ограничивать список.

---

## 23. Non-retryable Errors

Обычно не retry:

- invalid request;
- authentication failure;
- malformed parameters;
- unsupported operation;
- permanent provider error.

---

## 24. Retry Count

Каждый request имеет ограниченный retry count.

Не выполнять бесконечные retries.

---

## 25. Exponential Backoff

Для retry использовать exponential backoff с configurable parameters.

Минимально:

- initial delay;
- multiplier;
- maximum delay;
- maximum attempts.

---

## 26. Jitter

Retry delay должен поддерживать jitter.

Это предотвращает synchronized retry bursts.

---

## 27. Retry-After

Если provider возвращает Retry-After:

Resource Manager должен учитывать его.

Не отправлять retry раньше указанного provider interval без явного исключения policy.

---

## 28. Rate Limit Response

429 не означает:

UNSUPPORTED.

Это означает:

RESOURCE_LIMITED / RATE_LIMITED.

---

## 29. Cooldown

При повторяющихся rate-limit errors Resource Manager может временно снизить request rate или установить provider cooldown.

---

## 30. Provider Cooldown

Cooldown должен применяться к конкретному resource context.

Проблема 1inch Polygon не должна автоматически блокировать 0x Ethereum.

---

## 31. Circuit Breaker

Resource Manager должен поддерживать circuit breaker для provider/resource contexts.

Минимальные состояния:

- CLOSED;
- OPEN;
- HALF_OPEN.

---

## 32. CLOSED

Нормальная работа.

Requests выполняются согласно limits.

---

## 33. OPEN

Provider/resource context временно считается недоступным.

Новые requests не отправляются до завершения cooldown.

---

## 34. HALF_OPEN

После cooldown выполняется ограниченное количество test requests.

Если provider восстановился:

circuit возвращается в CLOSED.

Если нет:

возвращается в OPEN.

---

## 35. Circuit Breaker Safety

Circuit breaker не должен превращать временную проблему в permanent unsupported capability.

---

## 36. Timeout

Каждый request должен иметь timeout.

Минимально:

- connection timeout;
- response timeout;
- total request timeout.

---

## 37. Task Timeout

Кроме individual request timeout может существовать общий timeout task.

Например:

Level 2 Job timeout.

---

## 38. Timeout Hierarchy

Если:

task timeout

истёк раньше request timeout:

request должен быть отменён.

---

## 39. Cancellation

Resource Manager должен поддерживать cancellation.

Cancelled requests не должны оставаться в очереди.

---

## 40. Lock Release

После:

- success;
- failure;
- timeout;
- cancellation;

ресурс должен быть освобождён.

---

## 41. No Resource Leak

Ни один request не должен оставлять:

- semaphore;
- lock;
- queue slot;
- concurrency slot

занятым после завершения.

---

## 42. Backpressure

Если очередь переполнена:

Resource Manager не должен бесконечно принимать новые requests.

Он должен:

- отклонять;
- объединять;
- дедуплицировать;
- или откладывать

requests согласно policy.

---

## 43. Queue Limit

Queue size должна быть configurable.

Не использовать бесконечную очередь.

---

## 44. Duplicate Requests

Если два requests имеют одинаковый:

- provider;
- network;
- operation;
- parameters;
- task context;

Resource Manager должен иметь возможность дедупликации, если это безопасно.

---

## 45. In-flight Deduplication

Если одинаковый request уже выполняется:

новый consumer может присоединиться к существующему operation вместо отправки второго API request.

---

## 46. Дедупликация не должна менять semantics

Requests можно объединять только если результаты полностью совместимы.

Если различается:

- amount;
- route;
- token;
- parameters;

это разные requests.

---

## 47. Batch

Если provider API поддерживает batch:

Resource Manager должен позволять Adapter использовать batch request.

Batch должен считаться одним внешним request с точки зрения provider rate limit, если это соответствует provider policy.

---

## 48. Batch Accounting

Внутри системы batch должен сохранять связь:

один external request

→ несколько logical operations.

---

## 49. Batch Failure

Если batch возвращает частичные результаты:

валидные элементы должны быть обработаны отдельно.

Один failed element не должен автоматически уничтожать весь batch result.

---

## 50. Request Grouping

Если provider не имеет batch endpoint:

Resource Manager может группировать requests логически для scheduling.

Но grouping не должен создавать фиктивный API batch.

---

## 51. Fee Requests

Fee requests проходят те же:

- priority;
- rate limits;
- concurrency;
- retry;
- timeout;
- circuit breaker.

---

## 52. Capability Requests

Capability discovery requests также проходят Resource Manager.

---

## 53. Conversion Requests

Если conversion subsystem использует внешний API:

requests также проходят Resource Manager.

---

## 54. No Direct HTTP

Scanner, Fee System и Registry не должны самостоятельно создавать uncontrolled HTTP clients для provider API.

Все внешние requests должны проходить через соответствующий Adapter/Resource Manager path.

---

## 55. Adapter Responsibility

Adapter отвечает за:

- endpoint;
- request format;
- provider-specific parameters;
- response parsing;
- provider error normalization.

Resource Manager отвечает за:

- scheduling;
- limits;
- retries;
- concurrency;
- resource state.

---

## 56. Error Normalization

Resource Manager должен получать normalized error categories.

Например:

- RATE_LIMITED;
- TEMPORARY;
- PERMANENT;
- AUTH;
- INVALID_REQUEST;
- TIMEOUT;
- NETWORK;
- UNKNOWN.

---

## 57. Provider Error Preservation

Помимо normalized category необходимо сохранять:

- HTTP status;
- provider error code;
- provider message, если безопасно;
- retry-after;
- request ID.

---

## 58. Secrets

Resource Manager не должен логировать:

- API keys;
- private keys;
- authorization tokens;
- secrets.

---

## 59. API Keys

API credentials должны находиться в configuration/secret management.

Resource Manager получает только необходимые credentials references.

---

## 60. Metrics

Resource Manager должен собирать:

- total requests;
- successful;
- failed;
- retries;
- rate limits;
- timeouts;
- queue depth;
- queue wait time;
- execution time;
- active concurrency;
- circuit breaker state;
- deduplicated requests;
- batch requests.

---

## 61. Provider Metrics

Metrics должны позволять отдельно анализировать:

- provider;
- network;
- operation;
- priority.

---

## 62. Queue Latency

Измерять:

request created
→ request started

Это показывает влияние нагрузки на latency.

---

## 63. Execution Latency

Также измерять:

request started
→ request completed.

---

## 64. Total Latency

Для Level 2 важно измерять:

Opportunity created
→ API resource acquired
→ request executed
→ result received.

---

## 65. Configuration

Resource Manager configuration должна содержать provider-specific limits.

Например:

providers:
  1inch:
    requests_per_second: ...
    max_concurrency: ...

Конкретные значения не должны быть зафиксированы в architecture document.

---

## 66. Runtime Configuration

Если система поддерживает runtime configuration update:

новые limits применяются безопасно.

Нельзя менять limits способом, который оставляет активные locks/concurrency slots в неконсистентном состоянии.

---

## 67. Default Limits

Если provider limit неизвестен:

использовать безопасный консервативный default.

Никогда не считать:

unlimited

без подтверждённой policy.

---

## 68. Provider-specific Policy

Каждый provider может иметь:

- rate limit;
- concurrency limit;
- retry policy;
- cooldown;
- timeout.

Эти параметры должны быть конфигурируемыми.

---

## 69. Network-specific Policy

Если provider имеет разные limits для сетей:

policy должна поддерживать:

provider + network

как resource key.

---

## 70. Operation-specific Policy

Если provider ограничивает конкретные endpoint types:

policy может учитывать:

provider + operation.

---

## 71. Resource Key

Resource key должен быть deterministic.

Примеры:

1inch

1inch + polygon

1inch + polygon + quote

Используемый уровень определяется реальными provider limits.

---

## 72. Hierarchical Limits

Если одновременно существуют:

provider-wide limit

и:

network-specific limit

должны соблюдаться оба.

---

## 73. Resource Acquisition

Перед внешним request:

1. определить resource key;
2. проверить circuit state;
3. проверить cooldown;
4. получить priority;
5. дождаться concurrency slot;
6. проверить rate limit;
7. выполнить request.

---

## 74. Resource Release

После request:

1. освободить concurrency slot;
2. обновить rate accounting;
3. обновить metrics;
4. обработать error state;
5. уведомить waiting consumers.

---

## 75. Waiting

Ожидание ресурса не должно блокировать весь Scanner.

Ожидающий request находится в async queue.

---

## 76. Async Architecture

Resource Manager должен быть совместим с asynchronous application architecture.

Не использовать blocking sleep внутри общего event loop.

---

## 77. Retry Scheduling

Retry должен возвращаться в scheduling system с соответствующим delay.

Не блокировать worker на длительное время.

---

## 78. Priority During Retry

Retry сохраняет исходный business priority, если policy не предусматривает иное.

Например:

Level 2 retry остаётся Level 2 priority.

---

## 79. Retry Storm Prevention

При массовой ошибке provider:

Resource Manager должен предотвращать retry storm.

Использовать:

- exponential backoff;
- jitter;
- circuit breaker;
- queue limits.

---

## 80. Provider Recovery

После восстановления provider Resource Manager должен постепенно возвращать нормальную нагрузку.

Не отправлять сразу огромный burst накопленных requests.

---

## 81. Queue Expiration

Request, который больше не актуален, должен быть удалён из очереди.

Например:

если Level 2 Opportunity expired:

ожидающие requests этой Opportunity больше не нужны.

---

## 82. Stale Task Cancellation

Scheduler/Supervisor должен иметь возможность отменить связанные requests.

Resource Manager должен корректно обработать cancellation.

---

## 83. Shutdown

При shutdown:

- новые requests не принимаются;
- queued requests отменяются;
- активные requests получают graceful cancellation;
- resources освобождаются;
- state корректно сохраняется.

---

## 84. Startup Recovery

После startup Resource Manager должен начать с чистого runtime state.

Не восстанавливать старые in-flight HTTP requests как активные.

---

## 85. Persistent State

Не требуется сохранять в SQLite каждый runtime semaphore или queue slot.

Persistent storage используется только для необходимого configuration/diagnostics state.

---

## 86. Health

Resource Manager должен предоставлять health information:

- provider reachable;
- circuit state;
- rate-limit state;
- active requests;
- queue depth.

---

## 87. Health не равен Capability

Provider health:

DEGRADED

не означает:

UNSUPPORTED.

Capability Registry и Resource Manager state остаются отдельными.

---

## 88. Testing

Обязательно тестировать:

- concurrency;
- rate limit;
- priority;
- retries;
- exponential backoff;
- jitter;
- Retry-After;
- timeout;
- cancellation;
- queue limits;
- deduplication;
- batch;
- circuit breaker;
- cooldown;
- provider isolation;
- network isolation;
- graceful shutdown;
- recovery.

---

## 89. Load Testing

Необходимо тестировать:

- большое количество Level 1 requests;
- большое количество Level 2 requests;
- одновременный Level 2 + Level 1;
- массовые 429;
- массовые timeouts;
- provider outage.

---

## 90. Critical Invariants

Resource Manager никогда не должен:

1. позволять внешнему API request обходить resource control;

2. превышать configured provider limits;

3. выполнять бесконечные retries;

4. блокировать весь application из-за одного provider;

5. считать 429 признаком unsupported;

6. оставлять locks/concurrency slots после завершения request;

7. создавать бесконечную очередь;

8. позволять низкоприоритетным maintenance requests вытеснять Level 2 без policy;

9. отправлять retry раньше обязательного Retry-After;

10. логировать secrets;

11. смешивать provider-specific resource states;

12. превращать provider outage в permanent capability change.

---

## 91. Главный принцип

Resource Manager должен обеспечить:

**контролируемое, приоритетное и безопасное использование всех внешних API ресурсов Monik при минимальном количестве лишних requests.**

Он является обязательным промежуточным слоем между внутренними подсистемами и внешними API.

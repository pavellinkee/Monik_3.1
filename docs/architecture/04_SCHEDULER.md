# MONIK — SCHEDULER

## 1. Назначение

Scheduler является центральной системой планирования Monik.

Scheduler отвечает за:

- запуск Level 1;
- постановку Level 2 в очередь;
- управление приоритетами;
- координацию параллельных задач;
- передачу запросов в Resource Manager;
- deduplication Level 2;
- cancellation;
- graceful shutdown;
- взаимодействие с Maintenance;
- соблюдение архитектурных ограничений.

Scheduler не реализует API-логику агрегаторов.

Scheduler не выполняет финансовые расчёты.

Scheduler не должен самостоятельно обходить Resource Manager.

---

## 2. Основной принцип

Scheduler отвечает на вопрос:

**какая операция должна выполняться следующей и когда она может получить необходимые ресурсы?**

Scheduler не решает:

- какой API endpoint использовать;
- как формируется quote;
- как разбирается response;
- как рассчитывается комиссия;
- как рассчитывается прибыль.

Эти задачи принадлежат соответствующим подсистемам.

---

## 3. Типы задач

Scheduler должен поддерживать как минимум:

- Level 1 BUY;
- Level 1 SELL;
- Level 1 evaluation;
- Level 2;
- Maintenance.

Каждая задача должна иметь:

- task ID;
- task type;
- priority;
- creation timestamp;
- state;
- required resources;
- cancellation state;
- correlation ID.

---

## 4. Task States

Минимальные состояния:

- CREATED;
- QUEUED;
- WAITING_RESOURCE;
- RUNNING;
- COMPLETED;
- FAILED;
- CANCELLED;
- INTERRUPTED.

Переходы между состояниями должны быть deterministic.

---

## 5. Приоритеты

Глобальный порядок приоритетов:

Level 2
>
Level 1 SELL-ready
>
Level 1 BUY
>
Maintenance

Приоритет применяется только при конкуренции за один и тот же ресурс.

Если задачи не конфликтуют за ресурсы, они должны выполняться параллельно независимо от разницы приоритетов.

---

## 6. Level 2 Priority

Любая Level 2 задача имеет более высокий приоритет, чем Level 1.

Если Level 2 ожидает ресурс, который используется Level 1:

Resource Manager должен передать ресурс Level 2 после завершения текущей неделимой операции или согласно правилам конкретного ресурса.

Scheduler не должен нарушать текущую атомарную операцию ради приоритета.

---

## 7. Level 1 SELL Priority

Если для токена завершены необходимые BUY-проверки и определён MAX BUY:

создаётся SELL-ready task.

Эта задача получает повышенный приоритет.

Если она конкурирует за тот же ресурс с BUY другого токена:

SELL получает ресурс первой.

Если ресурсы различаются:

обе задачи выполняются параллельно.

---

## 8. Важный принцип параллельности

Scheduler не должен использовать глобальную очередь, которая блокирует весь Scanner.

Нельзя делать:

одна задача → завершение → следующая задача.

Вместо этого Scheduler должен работать с независимыми ресурсами и задачами.

Например:

AAVE BUY ждёт 1inch.

Одновременно:

LINK BUY работает через 0x.

И одновременно:

UNI SELL работает через Velora.

Все три операции могут выполняться параллельно, если Resource Manager разрешает соответствующие ресурсы.

---

## 9. Resource Manager

Scheduler не управляет фактическими API limits самостоятельно.

Scheduler передаёт Resource Manager:

- required resource;
- priority;
- task type;
- request metadata;
- operation context.

Resource Manager решает:

- можно ли получить ресурс;
- когда можно получить ресурс;
- какой lock требуется;
- можно ли выполнить request;
- нужно ли ждать;
- нужно ли retry.

---

## 10. Resource Requirements

Каждая task должна явно сообщать Scheduler/Resource Manager, какие ресурсы ей необходимы.

Например:

- aggregator;
- network;
- endpoint;
- API key scope;
- routing resource.

Нельзя скрывать необходимость ресурса внутри worker после начала выполнения.

---

## 11. Resource Scope

Resource lock должен иметь минимально необходимый scope.

Если конфликт существует только на уровне:

aggregator + network

не нужно блокировать весь aggregator на всех сетях.

Если официальный API ограничивает:

aggregator + API key

использовать соответствующий scope.

Если endpoint имеет отдельный rate limit:

использовать endpoint-level resource.

---

## 12. Level 2 Resource Ownership

Если Level 2 требует ресурс для последовательности связанных операций, ресурс должен удерживаться в соответствии с требованиями конкретного агрегатора и Resource Manager.

Scheduler не должен преждевременно отдавать ресурс другой задаче, если это может нарушить требования текущего Level 2 workflow.

---

## 13. Конфликт ресурсов

Если две задачи требуют один ресурс:

Scheduler передаёт их Resource Manager.

Resource Manager применяет:

- priority;
- FIFO/sequence;
- rate limits;
- current lock;
- cooldown;
- circuit breaker.

Scheduler не должен самостоятельно обходить эти правила.

---

## 14. Независимые ресурсы

Если две задачи используют разные ресурсы:

они должны иметь возможность выполняться одновременно.

Пример:

Level 2 → 1inch

Level 1 BUY → 0x

Обе операции должны быть разрешены параллельно.

---

## 15. Level 1 Token Independence

Каждый token cycle Level 1 должен быть независимым.

Завершение или ошибка:

AAVE

не должны автоматически блокировать:

LINK, UNI, WBTC и другие токены.

---

## 16. Early SELL Trigger

Scheduler должен реагировать на событие:

MAX_BUY_READY

для конкретного token/amount.

После этого он должен создать SELL task без ожидания завершения остальных token cycles.

---

## 17. Level 1 Event Flow

Пример последовательности:

BUY_STARTED

→

BUY_RESULT_RECEIVED

→

BUY_COMPLETE

→

MAX_BUY_READY

→

SELL_QUEUED

→

SELL_RUNNING

→

SELL_COMPLETE

→

EVALUATION_READY

→

OPPORTUNITY_CREATED или NO_OPPORTUNITY

---

## 18. BUY Partial State

Если часть BUY requests завершена, а часть ещё выполняется:

MAX_BUY не считается окончательно определённым, если отсутствующий результат может изменить максимальный результат.

Scheduler должен дождаться необходимых BUY results.

Нельзя запускать SELL на неполном наборе данных только ради ускорения.

---

## 19. BUY Errors

Если один агрегатор завершился временной ошибкой:

Scheduler должен следовать Retry Policy.

Если агрегатор окончательно недоступен:

Scheduler может считать его недоступным для текущего cycle.

Это не означает, что агрегатор становится globally unsupported.

---

## 20. SELL Trigger Boundary

SELL запускается только после выполнения условия:

- необходимый набор BUY results получен;
- MAX BUY определён;
- MAX BUY является валидным;
- соответствующий route information доступен.

Если хотя бы одно условие не выполнено:

SELL не запускается.

---

## 21. Level 2 Queue

Level 2 jobs помещаются в очередь при достижении:

level2.max_parallel.

Default:

20.

Scheduler не должен запускать больше логических Level 2 workflows, чем разрешено конфигурацией.

---

## 22. Level 2 Deduplication

Перед добавлением Level 2 Job Scheduler должен проверить наличие уже активного идентичного workflow.

Если такой workflow существует:

новый workflow не создаётся.

Запрос должен быть объединён с уже существующим workflow.

---

## 23. Deduplication Identity

Для deduplication использовать стабильный identity key.

Он должен учитывать необходимые параметры Opportunity, включая:

- network;
- input token;
- output token;
- BUY aggregator;
- SELL aggregator;
- route fingerprint;
- Opportunity identity.

Случайный K-ID не может использоваться как единственный критерий deduplication.

---

## 24. Retry и Deduplication

Retry существующего Level 2 Job не создаёт новый Job.

Retry создаёт новый attempt внутри существующего K-ID.

---

## 25. Queue Ordering

Если несколько задач имеют одинаковый priority:

по умолчанию использовать порядок создания/постановки в очередь.

Для определения порядка использовать:

- priority;
- created_at;
- sequence number.

Не использовать profitability как средство изменения порядка выполнения.

---

## 26. Profitability не меняет Scheduler Priority

Более прибыльная Opportunity не должна автоматически получать более высокий priority, если это не определено отдельной утверждённой policy.

Основной priority определяется:

- типом операции;
- resource conflict;
- установленными архитектурными правилами.

---

## 27. Cancellation

Scheduler должен поддерживать cancellation.

Можно отменить:

- queued task;
- waiting-resource task;
- running task, если операция допускает безопасную отмену.

После cancellation:

- новые API requests не создаются;
- состояние сохраняется;
- resource locks освобождаются;
- task получает CANCELLED.

---

## 28. Cancellation During API Request

Если API request уже выполняется и его нельзя безопасно отменить:

Scheduler не должен создавать дополнительный параллельный request только ради cancellation.

Нужно дождаться безопасного завершения текущей операции или использовать поддерживаемый механизм cancellation.

---

## 29. Graceful Shutdown

При shutdown Scheduler должен:

1. прекратить создание новых задач;
2. прекратить запуск новых Level 1 operations;
3. прекратить запуск новых Level 2 jobs;
4. сохранить queued jobs;
5. корректно обработать running tasks;
6. освободить ресурсы;
7. сохранить состояние.

---

## 30. Shutdown Timeout

Shutdown должен иметь конечный timeout.

Scheduler не должен зависать бесконечно в состоянии:

SHUTTING_DOWN.

После истечения timeout система должна перейти к безопасному завершению согласно общей shutdown policy.

---

## 31. Recovery

После перезапуска Scheduler должен восстановить:

- queued Level 2 jobs;
- незавершённые state transitions;
- необходимые Level 1 cycles;
- interrupted attempts.

Running jobs, которые были прерваны crash, не должны считаться успешно завершёнными.

---

## 32. Recovery Priority

После восстановления задачи не должны автоматически запускаться без проверки состояния Resource Manager.

Сначала необходимо:

- восстановить state;
- проверить ресурсы;
- проверить circuit breaker;
- проверить rate limits;
- затем запускать tasks.

---

## 33. Scheduler и Maintenance

Maintenance является отдельным типом task.

Maintenance имеет более низкий priority:

Level 2
>
Level 1 SELL
>
Level 1 BUY
>
Maintenance

Maintenance может выполняться параллельно с scanning work, если не конфликтует за ресурс.

---

## 34. Maintenance Resource Conflict

Если Maintenance требует ресурс, который нужен Level 2 или Level 1:

Maintenance ждёт.

Она не должна блокировать scanning work.

---

## 35. Startup Maintenance

Если Maintenance настроен на:

startup

Scheduler запускает maintenance workflow после инициализации необходимых компонентов и до перехода системы в полностью готовое состояние, если это предусмотрено startup policy.

При этом критические capability checks должны быть выполнены до начала обычного scanning, если без них безопасное сканирование невозможно.

---

## 36. Daily Maintenance

Если Maintenance настроен:

daily

Scheduler создаёт maintenance task согласно:

- interval_days;
- time.

Например:

maintenance.mode = daily

maintenance.interval_days = 2

maintenance.time = 03:00

означает выполнение maintenance каждые два дня в заданное время.

---

## 37. Scheduler не выполняет Maintenance напрямую

Scheduler отвечает за планирование.

Фактическую maintenance-логику выполняет Maintenance worker/service.

Scheduler только:

- создаёт task;
- устанавливает priority;
- передаёт task worker'у;
- контролирует state.

---

## 38. Task Dependencies

Task может иметь dependency.

Например:

SELL зависит от:

MAX_BUY_READY.

Level 2 зависит от:

Opportunity_CREATED.

Scheduler не должен запускать task, если её обязательная dependency ещё не выполнена.

---

## 39. Dependency Failure

Если dependency завершилась ошибкой:

зависимая task не должна запускаться автоматически.

Она должна получить соответствующее состояние или быть отменена согласно policy.

---

## 40. Event-driven Scheduling

Scheduler должен использовать события для запуска зависимых операций.

Например:

MAX_BUY_READY

создаёт:

SELL_READY.

Opportunity_CREATED

создаёт:

LEVEL2_QUEUED.

Это предпочтительнее постоянного polling состояния всех tasks.

---

## 41. Polling

Polling разрешён только там, где он действительно необходим:

- recovery;
- health checks;
- внешние API, не поддерживающие события;
- maintenance.

Не создавать агрессивный polling для каждой внутренней state transition.

---

## 42. Task Context

Каждая task должна иметь context.

Context должен позволять определить:

- cycle ID;
- V-ID;
- K-ID;
- token;
- network;
- amount;
- aggregator;
- route fingerprint;
- attempt ID.

Context не должен содержать secrets.

---

## 43. Structured Logging

Scheduler должен логировать:

- task creation;
- queue entry;
- resource wait;
- resource acquisition;
- task start;
- task completion;
- task failure;
- retry;
- cancellation.

Логи должны содержать correlation IDs.

---

## 44. Metrics

Scheduler должен предоставлять метрики:

- queued tasks;
- running tasks;
- completed tasks;
- failed tasks;
- cancelled tasks;
- waiting-resource tasks;
- Level 1 BUY count;
- Level 1 SELL count;
- Level 2 running;
- Level 2 queued;
- average wait time;
- average execution time.

---

## 45. Fairness

Priority не должен приводить к бесконечному starvation низкоприоритетных задач.

Если система долго работает под высокой нагрузкой Level 2:

Maintenance и Level 1 должны получать возможность выполнения, когда высокоприоритетная нагрузка освобождает ресурсы.

При этом глобальный приоритет Level 2 сохраняется.

---

## 46. Resource-aware Fairness

Fairness применяется только когда это не нарушает:

- Level 2 priority;
- aggregator rate limits;
- resource locks;
- fixed-route requirements.

Нельзя запускать низкоприоритетную задачу только ради fairness, если это нарушает обязательную resource policy.

---

## 47. No Global Lock

Не использовать один глобальный lock для всего Scheduler.

Глобальный lock создаст ненужную последовательность выполнения.

Locks должны быть связаны с конкретными ресурсами или атомарными state transitions.

---

## 48. No Direct API Calls

Scheduler не должен выполнять:

- HTTP requests;
- quote parsing;
- fee extraction;
- route parsing.

Он только планирует и координирует.

---

## 49. No Business Calculations

Scheduler не должен самостоятельно рассчитывать:

- profit;
- ROI;
- fees;
- gas;
- threshold.

Эти задачи выполняют специализированные сервисы.

---

## 50. No Route Selection

Scheduler не выбирает:

- лучший BUY route;
- лучший SELL route;
- альтернативный route.

Route selection относится к Scanner/Route subsystem.

Scheduler только обеспечивает выполнение уже определённых операций.

---

## 51. Configuration

Scheduler должен получать конфигурацию через централизованный configuration system.

Не хранить hard-coded:

- max_parallel;
- thresholds;
- API limits;
- maintenance time;
- token lists.

Если значение должно быть настраиваемым пользователем, оно должно находиться в configuration.

---

## 52. Invalid Configuration

Если configuration содержит невозможные значения:

Scheduler не должен запускаться в небезопасном состоянии.

Например:

- max_parallel <= 0;
- invalid maintenance time;
- invalid interval_days;
- invalid priority.

Configuration validator должен сообщить ошибку до запуска соответствующей подсистемы.

---

## 53. Backpressure

Если внешний ресурс перегружен:

Scheduler должен применять backpressure.

Не создавать бесконечную очередь задач.

Очередь должна иметь контролируемый размер или policy.

---

## 54. Queue Persistence

Критические Level 2 jobs должны сохраняться в SQLite.

После restart queued jobs должны быть восстановлены.

Transient Level 1 tasks могут быть пересозданы согласно recovery policy.

---

## 55. Queue Overflow

Если очередь достигает установленного лимита:

Scheduler не должен бесконечно принимать новые задачи.

Новая task должна:

- быть отклонена;
- быть объединена с существующей;
- или обработана согласно установленной backpressure policy.

Нельзя молча терять Level 2 Job, который уже должен быть сохранён.

---

## 56. Idempotency

Повторная доставка одного события Scheduler не должна создавать duplicate task.

Например:

MAX_BUY_READY

может быть доставлен повторно.

Scheduler должен определить, что соответствующий SELL task уже существует.

---

## 57. Event Identity

Внутренние события должны иметь уникальный event ID или другой механизм idempotency.

Минимально необходимо отличать:

- cycle;
- operation;
- event type;
- sequence.

---

## 58. State Persistence

Критические state transitions должны быть сохранены до публикации событий, если это необходимо для обеспечения recovery и idempotency.

Например:

Opportunity_CREATED

должно быть надёжно сохранено до создания внешнего Level 2 workflow.

---

## 59. Event Ordering

Для одного workflow события должны обрабатываться в логическом порядке.

Например:

BUY_STARTED

не может обрабатываться после:

MAX_BUY_READY.

Если события приходят повторно или с задержкой, Scheduler должен использовать state validation.

---

## 60. Stale Events

Если событие относится к уже завершённому или отменённому workflow:

не запускать новую task автоматически.

Событие должно быть записано в diagnostics при необходимости.

---

## 61. Level 1 Cycle Independence

Scheduler должен позволять одному токену находиться в:

SELL_RUNNING

в то время как другой токен находится в:

BUY_RUNNING.

Это является обязательным требованием.

---

## 62. Level 2 During Level 1

Level 2 может выполняться одновременно с Level 1.

Level 1 не должен ждать завершения Level 2.

Level 2 не должен ждать завершения всего Level 1 scanner.

Ограничение возникает только при конфликте ресурсов.

---

## 63. Scheduler State

Scheduler должен иметь состояние:

- STARTING;
- RUNNING;
- DEGRADED;
- SHUTTING_DOWN;
- STOPPED.

При критической ошибке persistence Scheduler должен сообщить Supervisor и перейти в безопасное состояние.

---

## 64. DEGRADED

DEGRADED означает:

Scheduler продолжает работать, но одна или несколько некритических функций недоступны.

Например:

- один aggregator resource временно unavailable;
- Telegram worker недоступен;
- maintenance временно не работает.

Это не должно автоматически останавливать весь Scanner.

---

## 65. Critical Failure

Критическими считаются ошибки, при которых невозможно гарантировать корректность state.

Например:

- невозможность сохранить обязательное состояние;
- corruption SQLite;
- нарушение критической concurrency invariant;
- потеря Resource Manager state.

При такой ситуации Scheduler должен сообщить Supervisor.

Система может перейти в SAFE_STOP.

---

## 66. Testing

Scheduler должен иметь отдельные тесты для:

- priority;
- FIFO;
- Level 2 max_parallel;
- Level 1 SELL priority;
- resource conflict;
- independent resources;
- deduplication;
- dependencies;
- retries;
- cancellation;
- shutdown;
- recovery;
- stale events;
- duplicate events;
- queue persistence;
- backpressure;
- fairness;
- resource locking.

---

## 67. Critical Invariants

Scheduler никогда не должен нарушать:

1. Level 2 max_parallel.

2. Resource Manager limits.

3. Aggregator rate limits.

4. Level 2 priority over conflicting Level 1.

5. SELL-ready priority over conflicting unfinished BUY.

6. Independent operations may execute in parallel.

7. Duplicate Level 2 workflows are not started.

8. Fixed-route requirements are not changed by Scheduler.

9. Scheduler does not make API-specific decisions.

10. Scheduler does not perform financial calculations.

11. Scheduler does not bypass Resource Manager.

12. Critical persisted state is recoverable.

---

## 68. Главный принцип Scheduler

Scheduler должен обеспечивать:

**максимально возможную параллельность без нарушения resource limits, priority rules, fixed-route requirements и других утверждённых архитектурных ограничений.**

Scheduler должен запускать готовую приоритетную работу как можно скорее, но никогда не должен нарушать ограничения внешнего ресурса ради скорости.

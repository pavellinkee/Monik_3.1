# MONIK — SCHEDULER

## 1. Назначение

Scheduler — централизованная подсистема управления временем запуска задач Monik.

Он отвечает за:

- запуск Level 1 Scanner;
- запуск Level 2 Jobs;
- startup tasks;
- daily tasks;
- configurable intervals;
- configurable execution time;
- ночные проверки;
- fee refresh;
- capability refresh;
- maintenance tasks;
- предотвращение неконтролируемого overlapping;
- передачу задач соответствующим подсистемам.

Главный принцип:

**Scheduler определяет когда задача должна быть запущена, но не выполняет бизнес-логику самой задачи.**

---

## 2. Основные задачи

Scheduler должен поддерживать как минимум:

- Level 1 scanning;
- Level 2 verification;
- Fee System refresh;
- Capability discovery/refresh;
- Maintenance;
- startup initialization tasks.

---

## 3. Scheduler не выполняет бизнес-логику

Scheduler не должен:

- получать quotes;
- рассчитывать profitability;
- выбирать routes;
- получать комиссии напрямую;
- отправлять Telegram messages;
- выполнять swaps.

Он только запускает соответствующие задачи.

---

## 4. Startup

Configuration должна поддерживать режим:

STARTUP

Startup task выполняется при запуске приложения.

---

## 5. Daily

Configuration должна поддерживать режим:

DAILY

Daily task выполняется регулярно согласно заданному интервалу и времени.

---

## 6. Daily Interval

Для daily task пользователь должен иметь возможность задать количество дней между запусками.

Например:

- 1 день;
- 2 дня;
- 3 дня;
- 7 дней.

Значение должно быть configuration parameter.

---

## 7. Daily Time

Для daily task пользователь должен иметь возможность задать точное время запуска.

Например:

02:00

---

## 8. Ночные проверки

Scheduler должен позволять устанавливать время запуска ночью.

Например:

- 01:00;
- 02:00;
- 03:30;
- 04:00.

Scheduler не должен предполагать, что scheduled task выполняется только днём.

---

## 9. Timezone

Scheduler должен использовать явно определённую timezone.

Timezone должна находиться в configuration.

Не использовать неявное предположение о UTC.

---

## 10. DST

Scheduler должен корректно работать при переходе на летнее/зимнее время.

Нельзя строить scheduling logic только на фиксированном UTC offset.

---

## 11. Schedule Model

Каждая scheduled task должна иметь:

- task type;
- enabled;
- mode;
- interval;
- execution time;
- timezone;
- priority;
- overlap policy.

---

## 12. Task Modes

Минимально поддерживать:

- STARTUP;
- DAILY;
- MANUAL.

---

## 13. STARTUP

STARTUP task выполняется один раз после запуска приложения.

Повторно автоматически не запускается до следующего application startup.

---

## 14. DAILY

DAILY task запускается согласно:

- interval_days;
- time;
- timezone.

---

## 15. MANUAL

MANUAL task запускается по явной команде пользователя или внутреннего Supervisor.

Manual запуск не должен менять scheduled configuration.

---

## 16. Enable/Disable

Каждая scheduled task должна иметь:

enabled = true/false

Disabled task не должна автоматически запускаться.

---

## 17. Configuration Validation

При startup Scheduler должен проверить:

- корректность mode;
- корректность interval_days;
- корректность time;
- корректность timezone;
- корректность priority;
- корректность overlap policy.

Invalid configuration должна приводить к понятной configuration error.

---

## 18. Time Format

Время пользователя хранится в формате:

HH:MM

Например:

02:30

---

## 19. Interval Validation

interval_days должен быть положительным целым числом.

Недопустимо:

0

или отрицательное значение.

---

## 20. Startup + Daily

Одна subsystem может иметь одновременно:

- startup refresh;
- daily refresh.

Например Fee System:

startup: enabled
daily: enabled
interval_days: 1
time: 02:00

---

## 21. Independent Schedules

Расписание одной subsystem не должно автоматически менять расписание другой.

Например:

Fee refresh и Capability refresh могут иметь разные:

- interval;
- time;
- priority.

---

## 22. Level 1 Schedule

Level 1 Scanner запускается согласно отдельной scan configuration.

Scanner не должен самостоятельно выбирать периодичность.

---

## 23. Level 2 Schedule

Level 2 не должен запускаться обычным fixed interval вместо Job-based processing.

Level 2 Jobs создаются Level 1/Supervisor и передаются Scheduler/Queue system.

---

## 24. Level 2 Priority

Level 2 Job имеет более высокий priority, чем новый Level 1 scan.

Scheduler должен учитывать это при планировании.

---

## 25. Immediate Level 2

Если Level 1 создаёт Opportunity:

Level 2 Job должен быть поставлен в очередь без ожидания следующего scheduled Level 1 cycle.

---

## 26. Queue Separation

Scheduler должен логически разделять:

- scheduled tasks;
- immediate jobs;
- Level 2 verification jobs;
- maintenance tasks.

---

## 27. Overlap

Для каждой task должен существовать overlap policy.

Минимально:

- ALLOW;
- SKIP;
- QUEUE;
- REPLACE.

---

## 28. Level 1 Overlap

Для Level 1 Scanner по умолчанию:

SKIP

если предыдущий полный scan ещё выполняется.

Это предотвращает накопление одинаковых scans.

---

## 29. Fee Refresh Overlap

Для Fee Refresh по умолчанию:

SKIP

если предыдущий refresh ещё выполняется.

---

## 30. Capability Refresh Overlap

Capability Refresh также не должен запускаться повторно, если предыдущий refresh ещё выполняется.

---

## 31. Level 2 Overlap

Level 2 Jobs не должны автоматически заменять друг друга.

Каждый Job имеет собственный Job ID.

Duplicate Job requests обрабатываются через deduplication policy.

---

## 32. Manual Run During Scheduled Run

Если пользователь запускает task вручную, когда scheduled instance уже выполняется:

поведение определяется overlap policy.

По умолчанию не создавать duplicate execution.

---

## 33. Missed Schedule

Если приложение было выключено во время scheduled time:

Scheduler должен использовать явную missed-run policy.

---

## 34. Missed Daily Task

По умолчанию пропущенный daily task не должен автоматически запускаться несколько раз подряд после старта приложения.

Scheduler должен выполнить максимум одну допустимую catch-up execution согласно configuration.

---

## 35. Startup Recovery

После запуска приложения:

1. загрузить configuration;
2. проверить schedules;
3. определить startup tasks;
4. восстановить необходимые runtime states;
5. запустить startup tasks;
6. активировать daily schedules.

---

## 36. Startup Ordering

Startup tasks могут иметь dependencies.

Например:

configuration
→ Resource Manager
→ Token Registry
→ Capability Registry
→ Fee System
→ Scanner

Зависимости должны быть явно определены.

---

## 37. Resource Manager First

Resource Manager должен быть готов до запуска задач, которые выполняют внешние API requests.

---

## 38. Token Registry First

Token Registry должен быть доступен до запуска scanner tasks, которым нужен список токенов.

---

## 39. Fee System Startup

Fee System startup refresh должен выполняться после того, как доступны:

- configuration;
- networks;
- aggregators;
- required token metadata;
- Resource Manager.

---

## 40. Capability Startup

Capability discovery должен выполняться после инициализации:

- configuration;
- providers;
- networks;
- Resource Manager.

---

## 41. Scanner Startup

Level 1 Scanner не должен запускаться до завершения обязательной initialization policy.

---

## 42. Dependency Failure

Если обязательная startup dependency не инициализировалась:

зависимые задачи не должны запускаться как будто система полностью готова.

---

## 43. Partial Startup

Если необязательная subsystem недоступна:

Scheduler может запустить независимые tasks.

Например:

проблема одного aggregator не должна автоматически останавливать сканирование других доступных aggregators.

---

## 44. Task State

Каждая task должна иметь runtime state.

Минимально:

- SCHEDULED;
- QUEUED;
- RUNNING;
- COMPLETED;
- FAILED;
- CANCELLED;
- SKIPPED.

---

## 45. Task ID

Каждый запуск task получает unique execution ID.

Он отличается от постоянного schedule ID.

---

## 46. Schedule ID

Каждая configuration schedule имеет unique schedule ID.

Например:

fee_daily_refresh

---

## 47. Execution ID

Каждая конкретная execution получает:

execution_id

Это позволяет отличать разные запуски одной и той же task.

---

## 48. Task Metadata

Execution metadata должна содержать:

- schedule ID;
- execution ID;
- task type;
- started_at;
- finished_at;
- status;
- priority;
- error code.

---

## 49. Cancellation

Scheduler должен поддерживать cancellation tasks.

Cancellation должна корректно передаваться выполняющей subsystem.

---

## 50. Timeout

Каждая task может иметь configurable timeout.

Если timeout истёк:

task получает соответствующий failure/timeout status.

---

## 51. Timeout не означает Retry

Истечение timeout не означает автоматический бесконечный retry.

Retry policy определяется task type и Resource Manager.

---

## 52. Retry

Scheduler может повторно поставить task согласно policy.

Но внешний API retry должен выполняться через Resource Manager.

---

## 53. No Retry Storm

Scheduler не должен создавать массовые retries после общего provider outage.

Resource Manager отвечает за provider-level retry protection.

---

## 54. Task Priority

Каждая task имеет priority.

Priority Scheduler должен быть согласован с Resource Manager.

---

## 55. Priority Examples

Рекомендуемый порядок:

LEVEL_2
LEVEL_1_SELL
LEVEL_1_BUY
MAINTENANCE
DISCOVERY

---

## 56. Fairness

Priority не должен приводить к бесконечному starvation низкоприоритетных tasks.

Scheduler должен учитывать starvation-prevention policy.

---

## 57. Persistent Schedule

User configuration schedules должны храниться в persistent configuration.

Runtime execution state не обязан полностью храниться в SQLite.

---

## 58. Configuration Source

Scheduler должен получать schedule configuration из утверждённого Configuration subsystem.

Не hard-code расписания внутри Python modules.

---

## 59. User Configuration

Пользовательский документ должен позволять задавать:

- enabled/disabled;
- startup;
- daily;
- interval_days;
- time;
- timezone.

---

## 60. Example

Пример конфигурации:

    fee_refresh:
      enabled: true
      mode: daily
      interval_days: 1
      time: "02:00"
      timezone: "Europe/Lisbon"

---

## 61. Another Example

    capability_refresh:
      enabled: true
      mode: daily
      interval_days: 3
      time: "03:00"
      timezone: "Europe/Lisbon"

---

## 62. Startup Example

    token_registry:
      enabled: true
      mode: startup

---

## 63. Multiple Modes

Если configuration позволяет одновременно startup и daily для одной subsystem:

они должны рассматриваться как отдельные schedule instances.

---

## 64. Schedule Calculation

Scheduler должен вычислять следующий запуск deterministic образом.

Одинаковая configuration + timezone + current schedule state должны давать одинаковый next run.

---

## 65. Next Run

Для каждой schedule необходимо иметь:

- last_run;
- next_run;
- status.

---

## 66. Clock Changes

Если системное время изменилось:

Scheduler должен корректно пересчитать next run.

Не запускать множество duplicate tasks из-за изменения часов.

---

## 67. Application Restart

После restart Scheduler должен восстановить next scheduled execution из configuration и runtime state.

---

## 68. No Duplicate Startup

Один application startup не должен создавать несколько одинаковых STARTUP executions.

---

## 69. Manual Trigger

Manual trigger должен:

- создавать отдельный execution ID;
- использовать тот же task implementation;
- проходить Resource Manager;
- не изменять schedule.

---

## 70. Maintenance

Scheduler может запускать maintenance tasks:

- database cleanup;
- diagnostics;
- health checks;
- approved retention cleanup.

---

## 71. Maintenance Priority

Maintenance имеет более низкий priority, чем Level 2.

---

## 72. Health Checks

Health check schedules могут иметь отдельную периодичность.

Они не должны выполнять scanner logic.

---

## 73. Metrics

Scheduler должен собирать:

- schedules configured;
- schedules enabled;
- executions;
- completed;
- failed;
- skipped;
- cancelled;
- overdue;
- queue wait;
- execution duration;
- next-run latency.

---

## 74. Logging

Structured logs должны содержать:

- schedule ID;
- execution ID;
- task type;
- priority;
- start time;
- end time;
- status;
- error code.

Secrets запрещены.

---

## 75. Diagnostics

Scheduler должен позволять определить:

- какая task запущена;
- когда она была запущена;
- когда следующий запуск;
- почему task была skipped;
- почему task failed;
- какой overlap policy применился.

---

## 76. Graceful Shutdown

При shutdown:

1. новые scheduled executions не создаются;
2. queued tasks отменяются согласно policy;
3. active tasks получают cancellation;
4. Scheduler освобождает runtime resources;
5. application корректно завершает работу.

---

## 77. Restart Safety

После restart Scheduler не должен:

- создавать duplicate Level 1 scans;
- создавать duplicate startup tasks;
- восстанавливать старые in-flight executions как RUNNING.

---

## 78. Timezone Default

Если пользователь явно не указал timezone:

используется системная timezone приложения согласно Configuration Policy.

Не зашивать конкретную timezone в Scheduler.

---

## 79. Configuration Error

Если timezone или time имеют неправильный формат:

Scheduler не должен молча исправлять значение.

Необходимо сообщить configuration error.

---

## 80. Testing

Обязательно тестировать:

- startup;
- daily;
- interval_days;
- exact time;
- timezone;
- DST;
- missed runs;
- restart;
- overlap;
- skip;
- queue;
- manual trigger;
- cancellation;
- timeout;
- dependencies;
- priority;
- duplicate prevention;
- graceful shutdown.

---

## 81. Critical Invariants

Scheduler никогда не должен:

1. выполнять бизнес-логику Scanner;

2. самостоятельно обращаться к внешним API;

3. рассчитывать profitability;

4. самостоятельно получать комиссии;

5. выбирать route;

6. создавать бесконечный timer loop внутри каждой subsystem;

7. запускать duplicate scans без policy;

8. игнорировать timezone;

9. запускать Level 2 только по следующему scheduled interval;

10. заменять Level 2 Job новым route;

11. создавать бесконечную очередь tasks;

12. запускать зависимую task до обязательной initialization dependency;

13. считать timeout причиной автоматического бесконечного retry.

---

## 82. Главный принцип

Scheduler должен обеспечить:

**предсказуемый, конфигурируемый и безопасный запуск всех задач Monik в нужное время, с поддержкой startup, daily, интервала в днях и точного времени, включая ночные проверки.**

Scheduler отвечает за **когда**.

Соответствующая subsystem отвечает за **что именно выполнять**.

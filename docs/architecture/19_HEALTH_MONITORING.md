# MONIK — HEALTH MONITORING

## 1. Назначение

Health Monitoring — подсистема наблюдения за состоянием Monik.

Она отвечает за:

- определение состояния основных subsystems;
- обнаружение degraded/unavailable состояния;
- предоставление health status;
- диагностику проблем;
- контроль критических зависимостей;
- передачу информации в monitoring/logging layer.

Health Monitoring не выполняет бизнес-логику торговли.

---

## 2. Главный принцип

Health Monitoring должна отвечать на вопрос:

**«Может ли Monik сейчас безопасно выполнять свою основную работу?»**

Она не должна самостоятельно:

- исправлять бизнес-логику;
- выполнять swaps;
- менять routes;
- изменять profitability;
- отправлять opportunities пользователю.

---

## 3. Health States

Минимально поддерживать:

- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STARTING;
- STOPPING.

---

## 4. HEALTHY

Subsystem считается HEALTHY, если:

- она инициализирована;
- её обязательные dependencies доступны;
- нет критических ошибок;
- она может выполнять свои функции.

---

## 5. DEGRADED

Subsystem считается DEGRADED, если:

- она частично работает;
- часть providers недоступна;
- присутствуют временные ошибки;
- функциональность ограничена;
- но основная работа ещё возможна.

---

## 6. UNAVAILABLE

Subsystem считается UNAVAILABLE, если она не может выполнять обязательную функцию.

Например:

- Database недоступна;
- configuration не загружена;
- все необходимые providers недоступны;
- критическая subsystem остановлена.

---

## 7. STARTING

Во время startup subsystem может находиться в STARTING.

STARTING не должен считаться ошибкой.

---

## 8. STOPPING

Во время graceful shutdown subsystem переводится в STOPPING.

---

## 9. Application Health

Общий health status приложения определяется состоянием критических subsystems.

Он не должен определяться только одним provider.

---

## 10. Critical Subsystems

Критическими для основной работы являются:

- Configuration;
- Database;
- Resource Manager;
- Scheduler;
- Level 1 Scanner;
- Level 2 Scanner;
- Fee System;
- Profit Calculator;
- Notification System.

---

## 11. Provider Health

Каждый provider должен иметь собственное health state.

Например:

- 1inch: HEALTHY;
- 0x: HEALTHY;
- Velora: DEGRADED;
- Uniswap: UNAVAILABLE.

---

## 12. Provider Isolation

UNAVAILABLE provider не должен автоматически переводить всё приложение в UNAVAILABLE, если существуют другие доступные providers и configuration допускает продолжение работы.

---

## 13. All Providers Unavailable

Если все необходимые providers для конкретного scan scope недоступны:

соответствующий scanner должен перейти в DEGRADED или UNAVAILABLE согласно policy.

---

## 14. Network Health

Каждая enabled network должна иметь отдельный health state.

---

## 15. Network Isolation

Проблема одной network не должна автоматически останавливать другие enabled networks.

---

## 16. Database Health

Database health check должен проверять минимум:

- connection;
- basic query;
- schema availability;
- migration state;
- integrity state.

---

## 17. Database Criticality

Если Database необходима для безопасного выполнения критических operations и недоступна:

application должен следовать critical database failure policy.

---

## 18. Resource Manager Health

Health Monitoring должна контролировать:

- active requests;
- queue depth;
- concurrency;
- provider states;
- retry pressure;
- circuit breakers.

---

## 19. Resource Saturation

Если Resource Manager регулярно достигает configured limits:

его состояние может перейти в DEGRADED.

---

## 20. Queue Health

Необходимо контролировать:

- Level 1 queue;
- Level 2 queue;
- Notification queue;
- Resource Manager queues.

---

## 21. Queue Saturation

Если queue достигает configured capacity:

система должна фиксировать degraded condition.

---

## 22. Level 1 Health

Level 1 health может учитывать:

- last successful scan;
- scan duration;
- failed scans;
- partial scans;
- provider availability;
- candidate production.

---

## 23. Stale Level 1

Если Level 1 не выполнялся дольше допустимого interval:

его состояние может перейти в DEGRADED.

---

## 24. Level 2 Health

Level 2 health может учитывать:

- queue depth;
- confirmation latency;
- failed jobs;
- expired jobs;
- provider availability;
- last successful confirmation.

---

## 25. Level 2 Backlog

Большой backlog Level 2 Jobs может привести к DEGRADED состоянию.

---

## 26. Notification Health

Notification System должна контролировать:

- queue depth;
- delivery failures;
- retry count;
- last successful delivery;
- Telegram availability.

---

## 27. Telegram Unavailable

Telegram outage не должен отменять confirmed opportunities.

Notification System может перейти в DEGRADED/UNAVAILABLE.

---

## 28. Fee System Health

Fee System должна контролировать:

- last successful refresh;
- fee snapshot freshness;
- provider availability;
- refresh failures.

---

## 29. Stale Fee State

Если обязательные fees стали stale:

Fee System должна перейти в DEGRADED.

---

## 30. Scheduler Health

Scheduler должен контролировать:

- last execution;
- next execution;
- failed tasks;
- missed schedules;
- active tasks.

---

## 31. Missed Schedule

Если scheduled task не была выполнена в допустимое время:

это должно быть диагностировано.

---

## 32. Profit Calculator Health

Profit Calculator является в основном deterministic subsystem.

Health должен учитывать:

- initialization;
- configuration;
- calculation errors;
- validation errors.

---

## 33. Configuration Health

Configuration считается HEALTHY только если:

- configuration загружена;
- validation завершена успешно;
- active configuration является valid.

---

## 34. Token Registry Health

Token Registry должна иметь health state.

Минимально проверять:

- registry loaded;
- required tokens available;
- required networks represented;
- metadata valid.

---

## 35. Capability Registry Health

Capability Registry должна контролировать:

- initialization;
- refresh state;
- available providers;
- network capabilities.

---

## 36. Health Checks

Health checks должны быть:

- lightweight;
- deterministic;
- безопасными;
- ограниченными по времени.

---

## 37. No Heavy Health Checks

Health Monitoring не должна запускать полный Level 1 или Level 2 scan только ради health check.

---

## 38. External Health Checks

External health checks могут использовать минимальные safe requests.

Они не должны создавать значительную нагрузку на providers.

---

## 39. Provider Probe

Provider probe должен выполняться только согласно policy.

Не отправлять постоянные requests каждому provider без необходимости.

---

## 40. Health Check Timeout

Каждый external health check должен иметь timeout.

---

## 41. Health Check Retry

Health check retry должен быть ограниченным.

Не создавать бесконечный retry loop.

---

## 42. Health Check Frequency

Частота health checks должна быть configuration-driven.

---

## 43. Event-Based Health

Health state может обновляться на основании уже полученных runtime events.

Например:

provider timeout во время реального quote request может обновить provider health.

---

## 44. No Duplicate Requests

Если runtime operation уже предоставляет достаточную информацию о состоянии provider:

не выполнять дополнительный health request без необходимости.

---

## 45. Health State Persistence

Необязательно сохранять каждое кратковременное health изменение в SQLite.

Persistent state используется только если это необходимо для:

- recovery;
- diagnostics;
- audit.

---

## 46. Health History

Health history должна иметь retention policy.

Не хранить бесконечную историю.

---

## 47. Incident

Существенное изменение состояния может создавать incident/event.

Например:

HEALTHY → UNAVAILABLE.

---

## 48. Recovery Event

Возвращение:

UNAVAILABLE → HEALTHY

должно фиксироваться как recovery event.

---

## 49. Flapping

Health Monitoring должна избегать постоянного переключения:

HEALTHY ↔ DEGRADED

из-за единичных transient errors.

---

## 50. Failure Threshold

Для некоторых health checks может использоваться configurable failure threshold.

---

## 51. Recovery Threshold

Для восстановления может использоваться отдельный success threshold.

---

## 52. Hysteresis

Для unstable providers может использоваться hysteresis между failure и recovery states.

---

## 53. Provider Reliability

Health Monitoring может предоставлять provider reliability metrics.

Например:

- success rate;
- timeout rate;
- average latency;
- recent failures.

---

## 54. Health ≠ Profitability

Health state provider не должен напрямую определять profitability.

Например:

HEALTHY provider не означает profitable quote.

---

## 55. Health ≠ Capability

HEALTHY provider не означает, что он поддерживает конкретный token/network/route.

Capability Registry остаётся отдельной subsystem.

---

## 56. Health ≠ Availability for Every Route

Provider может быть HEALTHY, но конкретная route может быть unavailable.

---

## 57. Degraded Mode

Monik может продолжать работу в DEGRADED mode, если safety conditions сохраняются.

Например:

один из четырёх aggregators unavailable.

---

## 58. Safe Degradation

При DEGRADED состоянии система должна:

- продолжать доступные операции;
- не использовать unavailable dependencies;
- не создавать false opportunities;
- сохранять diagnostics.

---

## 59. Unsafe Degradation

Если невозможно гарантировать корректность profitability:

система должна остановить соответствующую confirmation path.

---

## 60. No False Health

Health status не должен сообщать HEALTHY, если критическая dependency фактически недоступна.

---

## 61. Health Snapshot

Health Monitoring должна иметь возможность создать health snapshot.

Snapshot должен содержать:

- timestamp;
- application status;
- subsystem statuses;
- provider statuses;
- network statuses;
- queue states;
- critical incidents.

---

## 62. Health Snapshot Version

Snapshot может иметь version для совместимости diagnostics.

---

## 63. Health Endpoint

Архитектура должна позволять предоставить health information через internal interface.

Конкретный transport определяется implementation/deployment policy.

---

## 64. No Public Exposure by Default

Health endpoint не должен автоматически становиться публично доступным в Internet.

---

## 65. Sensitive Information

Health output не должен содержать:

- API keys;
- Telegram bot token;
- passwords;
- private keys;
- authentication headers;
- secrets.

---

## 66. Logging

Health events должны использовать structured logging.

Минимально:

- timestamp;
- subsystem;
- previous state;
- new state;
- reason;
- severity.

---

## 67. Metrics

Health Monitoring должна собирать:

- subsystem status;
- provider status;
- network status;
- queue depth;
- health check latency;
- failures;
- recoveries;
- incidents.

---

## 68. Error Correlation

Health events должны иметь возможность связываться с:

- scan ID;
- Job ID;
- execution ID;
- notification ID.

---

## 69. Startup

Во время startup application status:

STARTING.

После успешной инициализации критических subsystems:

HEALTHY или DEGRADED.

---

## 70. Startup Failure

Если критическая subsystem не может быть initialized:

application не должен объявляться HEALTHY.

---

## 71. Shutdown

При graceful shutdown:

application status:

STOPPING.

После завершения:

health monitoring прекращает active checks.

---

## 72. Recovery

После restart health states должны определяться заново.

Нельзя безусловно считать предыдущий HEALTHY state актуальным.

---

## 73. Stale Health State

Health state должен иметь timestamp.

Слишком старый health state не должен считаться актуальным.

---

## 74. Health Check Scheduling

Health checks должны запускаться через Scheduler или утверждённый centralized scheduling mechanism.

Health Monitoring не должна создавать собственные бесконтрольные timers.

---

## 75. Resource Manager Integration

Health checks внешних providers должны учитывать Resource Manager limits.

Health Monitoring не должна обходить centralized request controls.

---

## 76. Health and Circuit Breaker

Health state может использовать информацию Circuit Breaker.

Но Health Monitoring не должна самостоятельно реализовывать отдельный circuit breaker.

---

## 77. Health and Scanner

Scanner может использовать health information для выбора доступных providers.

Но health state не должен заменять actual quote validation.

---

## 78. Health and Notification

Notification System может использовать health information Telegram для diagnostics.

Но confirmed opportunity не должна изменяться из-за временной Telegram failure.

---

## 79. Testing

Обязательно тестировать:

- startup;
- shutdown;
- healthy state;
- degraded state;
- unavailable state;
- provider failure;
- provider recovery;
- network failure;
- database failure;
- queue saturation;
- stale state;
- failure threshold;
- recovery threshold;
- hysteresis;
- health snapshots;
- timeout;
- retry;
- sensitive data redaction.

---

## 80. Integration Tests

Необходимо тестировать:

Health Monitoring → Resource Manager

Health Monitoring → Database

Health Monitoring → Scheduler

Health Monitoring → Provider state

Health Monitoring → Scanner state

Health Monitoring → Notification state

---

## 81. Critical Invariants

Health Monitoring никогда не должна:

1. выполнять swaps;

2. считать HEALTHY provider автоматически capable для любой route;

3. считать HEALTHY provider автоматически profitable;

4. обходить Resource Manager;

5. выполнять полный scanner только ради health check;

6. создавать бесконечные health retries;

7. раскрывать secrets;

8. автоматически отключать всю систему из-за одного provider failure;

9. игнорировать критическую Database failure;

10. объявлять application HEALTHY при недоступной critical subsystem;

11. считать старый health state актуальным бесконечно;

12. заменять Capability Registry;

13. заменять Error Handling;

14. заменять Resource Manager Circuit Breaker.

---

## 82. Главный принцип

Health Monitoring должна обеспечить:

**постоянное, лёгкое и безопасное понимание текущего состояния Monik, позволяя системе работать в DEGRADED режиме при безопасных частичных сбоях и предотвращая использование системы в ситуациях, когда корректность результатов больше не гарантируется.**

Health Monitoring отвечает за:

**понять состояние системы.**

Error Handling отвечает за:

**обработать ошибку.**

Resource Manager отвечает за:

**контролировать внешние ресурсы.**

# MONIK — OBSERVABILITY

## 1. Назначение

Observability определяет единые требования к наблюдаемости Monik.

Система должна позволять понять:

- что происходит;
- где происходит;
- почему это происходит;
- насколько часто это происходит;
- как система реагирует на ошибки;
- восстановилась ли система после сбоя.

Observability включает:

- structured logging;
- metrics;
- tracing/correlation;
- health information;
- operational diagnostics.

---

## 2. Главный принцип

Observability должна позволять восстановить историю критической операции без необходимости изменять её состояние или повторно выполнять её.

---

## 3. Три основных компонента

Monik должен использовать:

1. Logs;
2. Metrics;
3. Tracing/Correlation.

Health Monitoring является отдельной subsystem, но использует observability infrastructure.

---

## 4. Structured Logging

Все application logs должны использовать structured format.

Предпочтительно JSON или другой machine-readable формат.

---

## 5. Log Fields

Critical logs должны по возможности содержать:

- timestamp;
- level;
- subsystem;
- event;
- message;
- scan_id;
- job_id;
- execution_id;
- notification_id;
- provider;
- network.

---

## 6. Optional Context

Context fields добавляются только если они действительно относятся к событию.

Не создавать огромные log records без необходимости.

---

## 7. Timestamp

Logs должны использовать timezone-aware timestamps.

Предпочтительно UTC.

---

## 8. Log Levels

Минимально поддерживать:

- DEBUG;
- INFO;
- WARNING;
- ERROR;
- CRITICAL.

---

## 9. DEBUG

DEBUG используется для development diagnostics.

В production DEBUG logging не должен быть включён постоянно без необходимости.

---

## 10. INFO

INFO используется для важных operational events.

Например:

- startup;
- shutdown;
- scan completed;
- provider state changed;
- deployment version.

---

## 11. WARNING

WARNING используется для потенциально проблемных, но не критических состояний.

Например:

- provider degraded;
- stale data;
- queue pressure;
- retry scheduled.

---

## 12. ERROR

ERROR используется для операций, которые не завершились успешно.

Например:

- provider request failed;
- database operation failed;
- notification failed.

---

## 13. CRITICAL

CRITICAL используется для событий, которые могут остановить или серьёзно нарушить работу Monik.

Например:

- database corruption;
- unrecoverable initialization failure;
- critical security incident.

---

## 14. No Secret Logging

Никогда не логировать:

- API keys;
- Telegram bot token;
- passwords;
- private keys;
- authentication headers;
- secret environment variables.

---

## 15. Redaction

Перед записью external data в logs sensitive values должны быть sanitized/redacted.

---

## 16. Provider Response Logging

Raw provider responses не должны логироваться полностью в production без explicit reason.

---

## 17. Financial Logging

Financial values могут логироваться только если это необходимо для diagnostics.

Не логировать лишние sensitive financial details.

---

## 18. Opportunity Logging

Для confirmed opportunity желательно иметь:

- opportunity_id;
- job_id;
- network;
- route fingerprint;
- input amount;
- final profit;
- timestamp.

---

## 19. No Credential Context

Opportunity logs никогда не должны содержать provider credentials.

---

## 20. Correlation ID

Каждая значимая workflow operation должна иметь correlation context.

---

## 21. Scan ID

Каждый Level 1 scan должен иметь уникальный `scan_id`.

---

## 22. Job ID

Каждый Level 2 Job должен иметь уникальный `job_id`.

---

## 23. Execution ID

Для конкретного execution attempt может использоваться `execution_id`.

---

## 24. Notification ID

Каждая Notification должна иметь `notification_id`.

---

## 25. Correlation Propagation

Correlation identifiers должны передаваться через subsystem boundaries.

---

## 26. Provider Correlation

Provider requests должны по возможности иметь внутренний correlation context.

Если provider поддерживает собственный request ID:

его можно сохранить для diagnostics.

---

## 27. No Provider Dependency

Monik не должен зависеть от наличия provider request ID.

---

## 28. Metrics

Metrics должны использоваться для численных и агрегируемых характеристик системы.

---

## 29. Core Metrics

Минимально отслеживать:

- scan count;
- scan duration;
- quote requests;
- quote failures;
- Level 2 jobs;
- confirmation success;
- confirmation failures;
- notifications;
- provider latency;
- provider errors;
- queue depth;
- database latency.

---

## 30. Scanner Metrics

Level 1 должен иметь metrics:

- scans started;
- scans completed;
- scans failed;
- candidates created;
- candidates rejected;
- provider requests;
- provider failures;
- scan duration.

---

## 31. Level 2 Metrics

Level 2 должен иметь:

- jobs queued;
- jobs started;
- jobs confirmed;
- jobs rejected;
- jobs expired;
- jobs failed;
- confirmation latency.

---

## 32. Profit Calculator Metrics

Можно отслеживать:

- calculations;
- rejected calculations;
- invalid calculations;
- calculation latency.

---

## 33. Fee Metrics

Fee System должен отслеживать:

- refresh attempts;
- refresh success;
- refresh failures;
- stale snapshots;
- fee records.

---

## 34. Resource Metrics

Resource Manager должен отслеживать:

- requests;
- success;
- failure;
- timeout;
- rate limit;
- retries;
- queue depth;
- active requests;
- circuit breaker state.

---

## 35. Provider Metrics

Для каждого provider желательно иметь:

- request count;
- success rate;
- error rate;
- timeout rate;
- rate-limit count;
- latency.

---

## 36. Network Metrics

Для каждой enabled network можно отслеживать:

- requests;
- failures;
- latency;
- active scans;
- Level 2 jobs.

---

## 37. Notification Metrics

Notification System должна отслеживать:

- queued;
- sent;
- failed;
- retries;
- duplicate notifications;
- delivery latency.

---

## 38. Database Metrics

Database layer должна отслеживать:

- query count;
- query latency;
- transaction failures;
- lock errors;
- migration status;
- database size.

---

## 39. Scheduler Metrics

Scheduler должен отслеживать:

- tasks executed;
- tasks failed;
- tasks skipped;
- tasks delayed;
- overlapping tasks;
- execution latency.

---

## 40. Health Metrics

Health Monitoring должна предоставлять:

- application state;
- subsystem state;
- provider state;
- network state;
- incident count;
- recovery count.

---

## 41. Metric Labels

Metrics labels должны быть ограниченными и predictable.

---

## 42. High Cardinality

Не использовать в metric labels:

- opportunity_id;
- job_id;
- arbitrary token address;
- raw URL;
- user-generated text;

если это создаёт high cardinality.

---

## 43. No Secrets in Metrics

Metrics labels и values не должны содержать secrets.

---

## 44. Provider Label

Provider является допустимым low-cardinality label.

---

## 45. Network Label

Network является допустимым label при ограниченном количестве поддерживаемых networks.

---

## 46. Operation Label

Operation type может использоваться как label.

---

## 47. Status Label

Stable status enums могут использоваться как labels.

---

## 48. Tracing

Если используется distributed tracing infrastructure:

критические workflows должны поддерживать spans.

---

## 49. Trace Scope

Минимально полезно трассировать:

Level 1 scan;
Level 2 confirmation;
provider request;
profit calculation;
notification delivery.

---

## 50. Trace IDs

Trace ID должен позволять связать несколько связанных operations.

---

## 51. Trace Context

Trace context должен передаваться через internal boundaries.

---

## 52. Provider Requests

Каждый external request должен быть связан с parent operation, если tracing включён.

---

## 53. Trace Sampling

В production допускается sampling для высокочастотных operations.

Но critical failures должны оставаться observable.

---

## 54. Error Events

Errors должны иметь structured event.

Минимально:

- error code;
- subsystem;
- operation;
- severity;
- retryable;
- correlation ID.

---

## 55. Error Aggregation

Повторяющиеся одинаковые errors должны быть агрегируемыми.

---

## 56. Error Fingerprint

Для recurring errors может использоваться deterministic fingerprint.

Он помогает группировать одинаковые проблемы.

---

## 57. No Sensitive Fingerprint

Fingerprint не должен строиться из secrets.

---

## 58. Incident Detection

Observability должна позволять обнаруживать:

- application down;
- database failure;
- all providers unavailable;
- queue saturation;
- repeated Level 2 failures;
- notification outage;
- disk exhaustion.

---

## 59. Alerting

Alerting policy должна основываться на:

- thresholds;
- duration;
- aggregation;
- severity.

---

## 60. No Alert on Every Error

Одиночная transient ошибка не должна автоматически создавать critical alert.

---

## 61. Provider Alert

Provider alert должен учитывать:

- error rate;
- timeout rate;
- duration;
- availability.

---

## 62. All Providers Alert

Если все необходимые providers недоступны:

создаётся high-severity operational event.

---

## 63. Queue Alert

Queue alert должен срабатывать при устойчивом превышении configured threshold.

---

## 64. Database Alert

Database unavailable/critical failure должен иметь high-severity alert.

---

## 65. Notification Alert

Repeated notification failures должны быть observable.

---

## 66. Disk Alert

Critical low disk space должен иметь alert.

---

## 67. Memory Alert

Unexpected sustained memory growth должен быть observable.

---

## 68. CPU Alert

Sustained abnormal CPU usage должен быть observable.

---

## 69. Health Integration

Observability и Health Monitoring должны использовать общие correlation identifiers.

---

## 70. Health vs Metrics

Health state описывает текущую operational state.

Metrics описывают измеряемые значения и историю.

Они не должны смешиваться.

---

## 71. Logs vs Metrics

Logs предназначены для событий и контекста.

Metrics предназначены для агрегированных числовых значений.

Не использовать logs как единственный способ получения operational metrics.

---

## 72. Traces vs Logs

Trace связывает workflow.

Logs содержат подробности отдельных событий.

Они дополняют друг друга.

---

## 73. Diagnostic Snapshot

Для critical incidents должна существовать возможность получить diagnostic snapshot.

Snapshot может содержать:

- application version;
- health state;
- subsystem states;
- provider states;
- queue depths;
- recent errors;
- scheduler state;
- database state.

---

## 74. No Secrets in Snapshot

Diagnostic snapshot не должен содержать secrets.

---

## 75. Version

Diagnostic snapshot должен содержать application version/commit.

---

## 76. Configuration Summary

Snapshot может содержать configuration summary.

Но sensitive configuration values должны быть redacted.

---

## 77. Runtime State

Snapshot может содержать безопасную информацию о:

- queues;
- active jobs;
- providers;
- scheduler;
- database.

---

## 78. No Full Runtime Dump

Не создавать неконтролируемый полный dump памяти/process state.

---

## 79. Log Retention

Logs должны иметь retention policy.

---

## 80. Metrics Retention

Metrics retention определяется monitoring infrastructure.

Не хранить бесконечные local metrics files без необходимости.

---

## 81. Diagnostic Retention

Diagnostic artifacts должны иметь ограниченный retention.

---

## 82. Disk Protection

Observability сама не должна привести к заполнению disk.

---

## 83. Log Rotation

Production logs должны ротироваться.

---

## 84. Log Size Limits

Один log file не должен расти бесконечно.

---

## 85. Failure During Logging

Logging failure не должен останавливать основную business logic, если это безопасно.

---

## 86. Metrics Failure

Metrics backend failure не должен автоматически останавливать scanning.

---

## 87. Tracing Failure

Tracing backend failure не должен ломать business workflow.

---

## 88. Observability Isolation

Observability является вспомогательной capability.

Она не должна становиться single point of failure для business logic.

---

## 89. Performance

Logging/metrics/tracing overhead должен оставаться контролируемым.

---

## 90. High-Frequency Paths

В high-frequency Level 1 paths нельзя выполнять чрезмерно дорогие diagnostic operations.

---

## 91. Sampling

Для high-volume events допускается sampling.

Critical errors не должны теряться из-за sampling.

---

## 92. Structured Context

Для scanner operations рекомендуется включать:

- scan_id;
- provider;
- network;
- token pair;
- operation.

---

## 93. Job Context

Для Level 2:

- job_id;
- candidate_id;
- provider;
- network;
- route fingerprint.

---

## 94. Notification Context

Для Notification:

- notification_id;
- opportunity_id;
- destination;
- attempt.

---

## 95. Database Context

Для database errors:

- operation;
- repository;
- entity type;
- transaction context.

Не логировать SQL с sensitive values.

---

## 96. Security Observability

Security-related events должны быть observable:

- invalid credentials;
- blocked requests;
- suspicious URL;
- authentication failure;
- secret scanning failure.

---

## 97. Deployment Observability

Deployment должен записывать:

- version;
- commit;
- start time;
- result;
- health result.

---

## 98. Release Correlation

После deployment operational events должны быть связаны с deployed version.

---

## 99. Testing Observability

Tests должны проверять, что critical failures создают необходимые observability events.

---

## 100. Critical Invariants

Observability никогда не должна:

1. логировать secrets;

2. хранить API credentials в metrics;

3. использовать high-cardinality identifiers без необходимости;

4. останавливать business logic из-за временного отказа metrics backend;

5. останавливать business logic из-за tracing failure;

6. создавать бесконечный рост logs;

7. создавать бесконтрольные diagnostic dumps;

8. выполнять heavy diagnostics в high-frequency paths без необходимости;

9. скрывать critical failures из-за sampling;

10. использовать logs как единственный operational monitoring mechanism;

11. раскрывать sensitive configuration в diagnostic snapshots;

12. изменять business state только ради observability.

---

## 101. Главный принцип

Observability должна обеспечить:

**полную и безопасную видимость состояния Monik без вмешательства в его business logic, позволяя быстро связать конкретную проблему с subsystem, provider, network, operation, version и временем возникновения.**

Logs отвечают на вопрос:

**«Что произошло?»**

Metrics:

**«Насколько часто и насколько сильно это происходит?»**

Tracing:

**«Как событие прошло через систему?»**

Health Monitoring:

**«В каком состоянии система находится сейчас?»**

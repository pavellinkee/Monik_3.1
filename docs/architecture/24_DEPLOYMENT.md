# MONIK — DEPLOYMENT

## 1. Назначение

Deployment определяет требования к запуску Monik в production environment.

Документ описывает:

- структуру deployment;
- environment;
- installation;
- configuration;
- secrets;
- startup;
- shutdown;
- updates;
- rollback;
- monitoring;
- backups;
- recovery;
- безопасность deployment.

---

## 2. Главный принцип

Production deployment должен быть:

- reproducible;
- predictable;
- secure;
- observable;
- recoverable;
- максимально автоматизированным.

Ручные действия допускаются только там, где они действительно необходимы.

---

## 3. Target Environment

Основной production environment:

Linux VPS/server.

Monik не должен зависеть от:

- Google Colab;
- локального компьютера пользователя;
- IDE;
- GitHub Codespaces.

---

## 4. GitHub

GitHub является source of truth для application source code и утверждённых architecture documents.

Production deployment получает code из Git repository.

---

## 5. Repository

Production deployment должен использовать определённую branch/tag/release согласно deployment policy.

Не рекомендуется запускать production напрямую из произвольного незакоммиченного состояния.

---

## 6. Version

Каждый production deployment должен иметь однозначно определяемую application version.

Version может определяться через:

- Git commit;
- Git tag;
- release version;
- build metadata.

---

## 7. Reproducibility

Один и тот же commit должен по возможности создавать одинаковый application artifact/environment.

---

## 8. Dependencies

Production dependencies должны быть явно определены.

Не устанавливать случайные latest versions без контроля.

---

## 9. Python Environment

Если Monik реализован на Python:

production должен использовать isolated Python environment.

Например:

- virtualenv;
- venv;
- container.

---

## 10. Dependency Locking

Production dependencies должны иметь контролируемые versions.

По возможности использовать lock file или equivalent mechanism.

---

## 11. Containerization

Container deployment допускается.

Если используется Docker:

image должна быть reproducible и не содержать secrets.

---

## 12. Non-Root

Monik рекомендуется запускать от отдельного non-root user.

---

## 13. Filesystem

Application должен иметь доступ только к необходимым directories.

Минимально необходимы:

- application directory;
- configuration;
- database;
- logs;
- backups, если они локальные.

---

## 14. Writable Directories

Application code directory по возможности должен быть read-only во время runtime.

Writable должны быть только необходимые directories.

---

## 15. Configuration

Production configuration должна находиться вне source code или использовать безопасный deployment mechanism.

---

## 16. Secrets

Production secrets должны поступать через secure environment/secret mechanism.

Не хранить их в Git.

---

## 17. Secret Separation

Development и production secrets должны быть полностью разделены.

---

## 18. Environment Variables

Deployment должен поддерживать environment variables для:

- provider API keys;
- Telegram credentials;
- database path;
- configuration path;
- runtime environment;
- logging settings.

---

## 19. Environment Name

Production environment должен быть явно обозначен.

Например:

MONIK_ENV=production

---

## 20. Startup

Production startup должен выполнять:

1. загрузку configuration;
2. validation;
3. secrets resolution;
4. database initialization;
5. migrations;
6. Token Registry initialization;
7. Capability Registry initialization;
8. Resource Manager initialization;
9. Fee System initialization;
10. Health Monitoring initialization;
11. Scheduler initialization;
12. Scanner initialization.

---

## 21. Startup Order

Зависимости должны инициализироваться до consumers.

Например:

Configuration
→ Database
→ Registries
→ Resource Manager
→ Fee System
→ Profit Calculator
→ Scanners
→ Notification
→ Scheduler.

---

## 22. Startup Failure

Если critical initialization не завершилась успешно:

application не должен запускать production scanning.

---

## 23. Startup Validation

Перед переходом в production operational state необходимо проверить:

- configuration;
- database;
- networks;
- providers;
- token registry;
- capabilities;
- resource limits;
- notification configuration.

---

## 24. Safe Startup

Production startup должен использовать conservative defaults.

Если critical information неизвестна:

лучше не запускать соответствующую operation.

---

## 25. Health State

Во время startup:

STARTING.

После успешного запуска:

HEALTHY или DEGRADED.

---

## 26. Process Supervisor

Production process должен запускаться под supervisor.

Допустимые варианты:

- systemd;
- Docker restart policy;
- другой approved process supervisor.

---

## 27. Automatic Restart

Transient process crash может приводить к automatic restart.

Но restart loop должен иметь protection.

---

## 28. Restart Loop

Если application постоянно падает:

deployment environment не должен выполнять бесконечный uncontrolled restart loop.

---

## 29. Graceful Shutdown

При SIGTERM/SIGINT application должен:

1. остановить создание новых scan operations;
2. остановить Scheduler;
3. прекратить создание новых Jobs;
4. обработать или отменить допустимые active operations;
5. завершить critical database transactions;
6. сохранить необходимый state;
7. закрыть external connections;
8. закрыть database;
9. завершить process.

---

## 30. Shutdown Timeout

Graceful shutdown должен иметь configurable timeout.

После его превышения применяется controlled forced termination policy.

---

## 31. No New Work During Shutdown

После начала shutdown новые:

- scans;
- Level 2 Jobs;
- notifications

не должны бесконтрольно создаваться.

---

## 32. Restart Recovery

После restart application должен восстановить необходимый persistent state.

Минимально:

- Level 2 Jobs;
- confirmed opportunities;
- notification state;
- scheduler state.

---

## 33. Database Recovery

SQLite database должна использовать safe transaction semantics.

После crash application должен выполнить integrity/startup checks.

---

## 34. Migration During Deployment

Database migrations должны выполняться до запуска зависимых subsystems.

---

## 35. Migration Failure

Если migration failed:

production application не должен запускаться с несовместимой schema.

---

## 36. Migration Backup

Перед destructive/major migration должна существовать backup strategy.

---

## 37. Deployment Sequence

Рекомендуемый порядок:

1. backup;
2. obtain target version;
3. validate environment;
4. install dependencies;
5. validate configuration;
6. migrate database;
7. run startup checks;
8. run tests;
9. start application;
10. verify health;
11. verify scheduler;
12. verify critical providers.

---

## 38. Pre-Deployment Tests

Перед production startup необходимо выполнить:

- unit tests;
- architecture tests;
- database migration tests;
- security checks;
- critical integration tests.

---

## 39. Production Smoke Test

После deployment необходимо проверить:

- application process;
- database;
- configuration;
- provider connectivity;
- scheduler;
- Level 1;
- Level 2;
- notification;
- health state.

---

## 40. Smoke Test Safety

Smoke test не должен выполнять real trading transaction.

---

## 41. Provider Verification

После deployment можно выполнить ограниченный provider connectivity check.

Он должен использовать Resource Manager.

---

## 42. Telegram Verification

Telegram delivery verification должна быть explicit и controlled.

Не отправлять пользователю бесконечные test messages.

---

## 43. Logs

Production logs должны быть:

- structured;
- timestamped;
- rotation-enabled;
- protected from secrets.

---

## 44. Log Rotation

Logs не должны бесконечно увеличивать disk usage.

---

## 45. Disk Monitoring

Deployment должен контролировать:

- disk space;
- database size;
- log size;
- backup size.

---

## 46. Disk Full

Если disk space становится критически низким:

application должен перейти в safe/degraded state согласно policy.

---

## 47. Database Backup

Production database должна иметь регулярный backup policy.

---

## 48. Backup Frequency

Backup frequency должна быть configuration/deployment policy.

---

## 49. Backup Retention

Старые backups должны удаляться согласно retention policy.

---

## 50. Backup Verification

Backup должен периодически проверяться на возможность восстановления.

Создание backup без проверки restore не считается достаточной гарантией recovery.

---

## 51. Offsite Backup

Для production рекомендуется хранить backup отдельно от основного VPS.

---

## 52. Backup Security

Backups должны быть защищены так же, как production database.

---

## 53. Recovery Point

Deployment policy должна определять допустимый Recovery Point Objective.

---

## 54. Recovery Time

Deployment policy должна определять допустимый Recovery Time Objective.

---

## 55. Disaster Recovery

При полном повреждении VPS должна существовать возможность:

1. создать новый server;
2. получить application code;
3. восстановить configuration;
4. восстановить secrets;
5. восстановить database backup;
6. установить dependencies;
7. выполнить migrations, если необходимо;
8. запустить Monik;
9. проверить health.

---

## 56. Infrastructure Documentation

Production environment должен иметь документированные:

- OS;
- runtime;
- dependencies;
- directories;
- environment variables;
- service configuration;
- backup configuration.

---

## 57. No Manual Secrets in Commands

Не рекомендуется передавать secrets напрямую в shell command arguments.

---

## 58. Process Environment

Secrets в environment variables допустимы, если deployment environment обеспечивает необходимую protection.

---

## 59. Secret Rotation

Deployment должен позволять менять credentials без изменения source code.

---

## 60. Application Update

Для update:

1. остановить/подготовить application;
2. сохранить backup;
3. получить новую version;
4. установить dependencies;
5. выполнить tests;
6. выполнить migrations;
7. запустить application;
8. выполнить health check.

---

## 61. Zero-Downtime

Zero-downtime deployment не является обязательным на текущем этапе.

Безопасность и consistency важнее минимизации downtime.

---

## 62. Rollback

Для каждой production update должна существовать rollback strategy.

---

## 63. Code Rollback

При проблеме application code должен иметь возможность вернуться на предыдущий known-good version.

---

## 64. Database Rollback

Database rollback сложнее code rollback.

Destructive migrations не должны рассчитывать на автоматический rollback без explicit tested mechanism.

---

## 65. Migration Compatibility

При возможности сначала использовать backward-compatible migration.

Это облегчает rollback application code.

---

## 66. Failed Deployment

Если smoke test failed:

application не должен считаться успешно deployed.

---

## 67. Automatic Rollback

Automatic rollback допускается только если он безопасен и migration strategy поддерживает его.

---

## 68. Health Verification

После deployment необходимо проверить:

application health.

Если status:

UNAVAILABLE

deployment считается failed.

---

## 69. Degraded Deployment

DEGRADED deployment требует diagnostics.

Если degraded состояние не влияет на critical functionality:

deployment может считаться partially successful согласно policy.

---

## 70. Monitoring

Production должен иметь monitoring для:

- process;
- CPU;
- RAM;
- disk;
- database;
- network;
- providers;
- queues;
- scheduler;
- notifications.

---

## 71. CPU

Unexpected CPU spikes должны быть диагностируемыми.

---

## 72. Memory

Memory usage должен контролироваться.

---

## 73. Memory Leak

Длительный рост memory usage должен приводить к investigation.

---

## 74. Network

Deployment monitoring должен отслеживать:

- external connectivity;
- request failures;
- latency;
- provider availability.

---

## 75. Provider Monitoring

Provider health должен отслеживаться через Health Monitoring.

---

## 76. Alerts

Critical operational failures должны иметь alert mechanism.

Например:

- application down;
- database unavailable;
- all providers unavailable;
- queue permanently saturated;
- repeated notification failures;
- disk critically low.

---

## 77. Alert Fatigue

Не создавать alerts для каждого transient error.

Использовать thresholds и aggregation.

---

## 78. Deployment Audit

Каждый production deployment должен иметь:

- version;
- commit;
- timestamp;
- operator/process;
- result.

---

## 79. Deployment Metadata

Deployment metadata не должна содержать secrets.

---

## 80. Security

Production server должен:

- использовать актуальные security updates;
- ограничивать открытые ports;
- использовать firewall;
- использовать SSH security best practices;
- не предоставлять unnecessary public services.

---

## 81. Public Ports

Monik не должен открывать public ports без необходимости.

---

## 82. Health Endpoint Security

Если health endpoint используется:

по умолчанию он должен быть internal-only.

---

## 83. SSH

SSH access должен быть ограничен согласно server security policy.

---

## 84. OS Updates

Operating system и critical security packages должны регулярно обновляться.

---

## 85. Dependency Updates

Application dependencies должны периодически обновляться и тестироваться.

---

## 86. Version Pinning

Production deployment должен использовать контролируемые dependency versions.

---

## 87. Reproducible Installation

Новая production machine должна иметь возможность получить environment из:

- repository;
- dependency definitions;
- configuration;
- secrets;
- backup.

---

## 88. Deployment Script

Installation/startup steps рекомендуется автоматизировать.

Не создавать deployment, который зависит от длинной последовательности ручных команд без необходимости.

---

## 89. Idempotent Deployment

Повторный запуск deployment procedure не должен ломать уже корректно установленный environment.

---

## 90. Deployment Validation

Deployment procedure должен проверять prerequisites до destructive actions.

---

## 91. No Destructive Defaults

Deployment scripts не должны автоматически:

- удалять database;
- удалять backups;
- удалять configuration;
- удалять secrets.

---

## 92. Production Database Protection

Production deployment не должен автоматически создавать новую пустую database поверх существующей.

---

## 93. Environment Verification

Перед deployment необходимо убедиться, что target environment действительно production target.

---

## 94. Wrong Server Protection

Deployment должен иметь способ подтвердить target identity перед destructive operations.

---

## 95. Release Artifacts

Если используется build artifact:

он должен иметь version/commit identifier.

---

## 96. Artifact Integrity

Deployment должен по возможности проверять integrity полученного artifact.

---

## 97. Deployment Logs

Deployment logs должны сохраняться для diagnostics.

Secrets должны быть redacted.

---

## 98. Failed Installation

Если dependency installation failed:

не запускать partially installed application.

---

## 99. Final Production Checklist

Перед завершением deployment необходимо проверить:

- correct version;
- dependencies;
- configuration;
- secrets;
- database;
- migrations;
- tests;
- health;
- provider capabilities;
- scheduler;
- notification;
- backups;
- monitoring.

---

## 100. Critical Invariants

Deployment никогда не должен:

1. запускать production с invalid configuration;

2. запускать application до обязательных database migrations;

3. удалять production database автоматически;

4. удалять backups автоматически без retention policy;

5. хранить secrets в Git;

6. включать automatic trading;

7. запускать application от root без необходимости;

8. отключать TLS verification;

9. запускать production с непроверенными dependencies;

10. считать deployment успешным без health verification;

11. выполнять real trading transaction во время smoke test;

12. бесконечно restart application при crash loop;

13. публиковать health endpoint в Internet без необходимости;

14. выполнять destructive migration без backup/recovery strategy;

15. использовать production credentials в tests;

16. терять возможность определить deployed version.

---

## 101. Главный принцип

Deployment должен обеспечить:

**воспроизводимый, безопасный и восстанавливаемый запуск Monik на production VPS с контролируемыми обновлениями, backup, rollback, monitoring и минимальным количеством ручных действий.**

Production deployment должен быть построен вокруг принципа:

**сначала сохранить состояние → проверить environment → установить version → проверить database/configuration → запустить → проверить health → только после этого считать deployment успешным.**

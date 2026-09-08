# MONIK — SECURITY

## 1. Назначение

Этот документ определяет обязательные требования безопасности Monik.

Цель:

- защитить credentials;
- предотвратить unauthorized access;
- изолировать external providers;
- защитить database;
- предотвратить unsafe operations;
- обеспечить безопасную обработку external data;
- минимизировать последствия компрометации отдельных компонентов.

---

## 2. Главный принцип

Security должна быть построена по принципу:

**least privilege + defense in depth + fail safe.**

При неопределённости система должна выбирать безопасное поведение.

---

## 3. Secrets

К secrets относятся:

- API keys;
- Telegram bot tokens;
- passwords;
- private keys;
- authentication credentials;
- signing secrets.

---

## 4. Secret Storage

Secrets никогда не должны храниться:

- в Git;
- в source code;
- в architecture documents;
- в tests;
- в database без explicit security requirement;
- в logs;
- в metrics;
- в diagnostic snapshots.

---

## 5. Environment Secrets

Production secrets могут передаваться через secure environment/secret management mechanism.

---

## 6. Example Secrets

`.env.example` может содержать только placeholder values.

Например:

`PROVIDER_API_KEY=CHANGE_ME`

---

## 7. Secret Redaction

Любой вывод configuration или diagnostics должен автоматически redacted sensitive fields.

---

## 8. Secret Rotation

Credentials должны иметь возможность быть заменены без изменения source code.

---

## 9. Least Privilege

Каждый component должен иметь только необходимые permissions.

---

## 10. Provider Credentials

Каждый provider должен использовать только свои credentials.

Provider A не должен получать credential Provider B.

---

## 11. Telegram Credentials

Telegram token должен использоваться только Notification Adapter.

Другие subsystems не должны иметь прямого доступа к нему.

---

## 12. Database Credentials

SQLite не требует network credentials.

Filesystem permissions должны ограничивать доступ к database.

---

## 13. Filesystem Permissions

Application должен иметь доступ только к необходимым:

- source;
- config;
- data;
- logs;
- temporary directories.

---

## 14. Production User

Monik рекомендуется запускать от отдельного non-root user.

---

## 15. Root Prohibition

Application не должен требовать root privileges для обычной работы.

---

## 16. Network Exposure

Monik не должен открывать public network ports без explicit requirement.

---

## 17. Internal Services

Если service доступен только локально:

использовать localhost/internal binding вместо public binding.

---

## 18. Health Endpoint

Health endpoint по умолчанию должен быть internal-only.

---

## 19. Health Information

Health endpoint не должен раскрывать:

- secrets;
- API keys;
- filesystem paths;
- internal credentials;
- sensitive configuration.

---

## 20. External Input

Любые external inputs должны считаться untrusted.

Это включает:

- provider responses;
- Telegram responses;
- HTTP responses;
- configuration values;
- command-line input;
- environment variables;
- database content.

---

## 21. Input Validation

External data должна проходить:

- schema validation;
- type validation;
- range validation;
- semantic validation.

---

## 22. Fail Closed

Если required security validation не прошла:

операция должна быть отклонена.

---

## 23. No Unsafe Defaults

Invalid/missing security configuration не должна автоматически превращаться в permissive behavior.

---

## 24. URLs

External URLs должны проходить validation перед HTTP request.

---

## 25. Allowed Providers

Provider requests должны выполняться только к configured/approved provider endpoints.

---

## 26. URL Allowlist

По возможности использовать explicit allowlist для provider domains.

---

## 27. SSRF Protection

Не позволять arbitrary external input определять destination URL без validation.

---

## 28. Redirects

HTTP client должен контролировать redirects.

Нельзя позволять redirect автоматически переводить request на запрещённый internal/private destination.

---

## 29. Private Networks

Provider requests не должны обращаться к:

- localhost;
- loopback;
- private network;
- metadata endpoints

если это не является explicit approved destination.

---

## 30. DNS Rebinding

Security validation должна учитывать риск DNS rebinding при необходимости.

---

## 31. HTTP Security

External HTTP clients должны:

- использовать TLS;
- проверять certificates;
- иметь timeout;
- ограничивать response size.

---

## 32. TLS Verification

TLS certificate verification никогда не отключать в production.

---

## 33. HTTP Timeout

Каждый external request должен иметь bounded timeout.

---

## 34. Response Size

Не принимать бесконечно большие provider responses.

---

## 35. Compression

Если поддерживается compressed response:

не допускать uncontrolled decompression resource exhaustion.

---

## 36. JSON Parsing

Malformed JSON должен приводить к controlled error.

---

## 37. Schema Validation

JSON response не должен считаться valid только потому, что JSON syntactically корректен.

---

## 38. Numeric Validation

External numeric values должны проверяться на:

- type;
- range;
- precision;
- sign;
- overflow.

---

## 39. Financial Security

Financial data должна использовать exact numeric representation.

---

## 40. Float Prohibition

Binary Float запрещён для critical financial calculations.

---

## 41. Negative Values

Неожиданные negative financial values должны проходить explicit validation.

---

## 42. Overflow

Large numeric values должны быть ограничены/validated до financial calculation.

---

## 43. Token Addresses

Token/network identifiers должны проходить validation.

---

## 44. Network Validation

Network identifier должен соответствовать configured supported network.

---

## 45. Provider Validation

Provider identifier должен соответствовать known provider registry.

---

## 46. Capability Validation

Unsupported operation должна быть rejected, а не выполнена через fallback неизвестного типа.

---

## 47. Authentication

Authentication failures должны быть observable.

---

## 48. Authorization

Application components должны иметь только необходимые internal permissions.

---

## 49. Component Isolation

Notification System не должна иметь:

- database admin privileges;
- provider credentials;
- arbitrary filesystem access.

---

## 50. Scanner Isolation

Scanner не должен иметь direct access к Telegram credentials.

---

## 51. Domain Isolation

Domain layer не должен иметь доступ к secrets или infrastructure credentials.

---

## 52. Provider Isolation

Provider Adapter не должен получать credentials других providers.

---

## 53. Database Isolation

Database access должен проходить через Repository layer.

---

## 54. SQL Injection

Raw external input никогда не должен конкатенироваться непосредственно в SQL.

Использовать parameterized queries.

---

## 55. SQL Safety

Repository должен использовать safe query parameters.

---

## 56. Migration Security

Migration scripts должны быть reviewed и version-controlled.

---

## 57. Database File

Database file должен быть защищён filesystem permissions.

---

## 58. Database Backup

Backups должны иметь permissions не менее строгие, чем production database.

---

## 59. Backup Encryption

Если backup хранится вне защищённого server environment:

рекомендуется encryption at rest.

---

## 60. Logs

Logs не должны содержать secrets.

---

## 61. Log Injection

External strings должны быть безопасно представлены в logs.

Не позволять external input ломать structured logging format.

---

## 62. Sensitive Errors

Error messages для users не должны раскрывать internal implementation details.

---

## 63. Stack Traces

Stack traces предназначены для controlled diagnostics, а не user-facing notifications.

---

## 64. Telegram Security

Telegram bot token должен быть защищён как credential.

---

## 65. Telegram Destination

Notification destination должен быть validated/configured.

Не отправлять сообщения на arbitrary destination, полученный из untrusted input.

---

## 66. Telegram Content

Notification content должен содержать только approved data.

---

## 67. No Secrets in Telegram

Telegram notifications никогда не должны содержать:

- API keys;
- credentials;
- internal secrets;
- private keys.

---

## 68. Git Security

Secrets не должны попадать в Git history.

---

## 69. Secret Leak

При обнаружении leaked secret:

1. credential должен быть revoked;
2. credential должен быть rotated;
3. exposure должен быть оценён;
4. Git history должен быть проверен;
5. affected systems должны быть проверены.

---

## 70. GitHub Security

Repository должен использовать:

- protected branches;
- required CI checks;
- minimal permissions;
- repository secrets.

если эти возможности доступны.

---

## 71. CI Security

CI workflows не должны предоставлять production secrets недоверенному code.

---

## 72. Pull Request Security

Untrusted pull requests не должны автоматически получать privileged production credentials.

---

## 73. Dependency Security

Dependencies являются security boundary.

Перед добавлением dependency необходимо учитывать:

- maintenance;
- vulnerabilities;
- provenance;
- license;
- permissions;
- supply-chain risk.

---

## 74. Dependency Updates

Security-critical dependency updates должны проходить tests.

---

## 75. Dependency Pinning

Production dependencies должны иметь controlled versions.

---

## 76. Supply Chain

Не устанавливать неизвестные packages без проверки происхождения и необходимости.

---

## 77. Build Security

Production build не должен включать:

- secrets;
- development credentials;
- test databases;
- debug artifacts.

---

## 78. Container Security

Если используется Docker:

- не запускать application от root без необходимости;
- использовать минимальный base image;
- не включать secrets в image;
- контролировать image versions.

---

## 79. Container Secrets

Secrets не должны записываться в Docker image layers.

---

## 80. Runtime Security

Production process должен иметь:

- ограниченные permissions;
- controlled filesystem access;
- controlled network access.

---

## 81. Process Isolation

Не разрешать application произвольно выполнять shell commands без explicit requirement.

---

## 82. Command Execution

Если system commands необходимы:

использовать allowlist и безопасную argument handling.

---

## 83. Shell Injection

External input не должен напрямую попадать в shell command.

---

## 84. Path Traversal

External input не должен напрямую определять filesystem path без validation.

---

## 85. File Access

File paths должны:

- быть validated;
- ограничиваться approved directories;
- не позволять `../` escape.

---

## 86. Temporary Files

Temporary files должны создаваться безопасным mechanism.

---

## 87. Permissions

Не создавать files с world-writable permissions.

---

## 88. Configuration Security

Configuration parser должен валидировать:

- types;
- ranges;
- allowed values;
- required fields.

---

## 89. Secret Configuration

Configuration display/export должен redacted sensitive values.

---

## 90. Environment Security

Не считать environment variables автоматически trusted, если они приходят из untrusted execution environment.

---

## 91. Authentication Errors

Repeated authentication failures должны быть observable.

---

## 92. Rate Limiting

Resource Manager должен защищать Monik от excessive requests.

---

## 93. Outbound Rate Limiting

Не отправлять provider requests быстрее configured limits.

---

## 94. Notification Rate Limiting

Telegram requests должны иметь controlled rate limit.

---

## 95. Resource Exhaustion

Security model должна учитывать:

- memory exhaustion;
- CPU exhaustion;
- disk exhaustion;
- queue exhaustion;
- response-size exhaustion.

---

## 96. Queue Limits

Queues должны иметь bounded capacity.

---

## 97. Backpressure

При перегрузке система должна использовать backpressure или controlled rejection.

---

## 98. No Infinite Queues

Не создавать unbounded queues для external requests.

---

## 99. DoS Protection

Не позволять одному provider/error source привести к uncontrolled resource consumption.

---

## 100. Critical Invariants

Security никогда не должна позволять:

1. хранить secrets в Git;

2. логировать credentials;

3. отправлять secrets в Telegram;

4. отключать TLS verification в production;

5. выполнять arbitrary external URLs без validation;

6. допускать SSRF к private/internal endpoints;

7. выполнять raw SQL с untrusted input;

8. выполнять arbitrary shell commands с external input;

9. допускать path traversal;

10. запускать application от root без необходимости;

11. давать одному provider credentials другого provider;

12. использовать production secrets в untrusted CI;

13. считать malformed external data valid;

14. использовать Float для critical financial calculations;

15. создавать unbounded resource consumption;

16. автоматически превращать неизвестное состояние в безопасное только на основании fallback;

17. раскрывать stack traces пользователю;

18. выполнять real trading operations без explicit trading subsystem и соответствующей authorization model.

---

## 101. Главный принцип

Security Monik должна обеспечить:

**защиту credentials, данных, infrastructure и financial integrity при работе с недоверенными внешними источниками, ограниченных permissions, безопасной обработке ошибок и fail-safe поведении при любой неопределённости.**

Основное правило:

**если система не может доказать, что операция безопасна, она не должна выполнять её.**

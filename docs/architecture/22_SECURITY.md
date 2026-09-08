# MONIK — SECURITY

## 1. Назначение

Security определяет обязательные требования безопасности для Monik.

Подсистема должна защищать:

- API credentials;
- Telegram credentials;
- database;
- configuration;
- runtime state;
- external requests;
- внутренние interfaces;
- application logs;
- deployment environment.

На текущем этапе Monik не выполняет автоматические swaps и не хранит private keys.

---

## 2. Главный принцип

Security должна строиться по принципу:

**минимально необходимые права + отсутствие secrets в коде + безопасные defaults + явная изоляция ответственности.**

---

## 3. No Private Keys

На текущем этапе Monik не должна:

- хранить private keys;
- импортировать private keys;
- подписывать transactions;
- управлять wallet credentials;
- выполнять swaps.

---

## 4. No Automatic Trading

Даже наличие profitable opportunity не должно предоставлять системе возможность автоматически отправить transaction.

Trading execution является отдельной будущей subsystem.

---

## 5. Secrets

К secrets относятся:

- API keys;
- API secrets;
- Telegram bot token;
- passwords;
- authentication tokens;
- private credentials.

Secrets никогда не должны находиться в source code.

---

## 6. Repository Safety

Secrets запрещено хранить:

- в Git repository;
- в обычных configuration files;
- в документации;
- в tests;
- в example configuration с реальными значениями.

---

## 7. Environment Variables

Для deployment secrets могут использоваться environment variables.

Например:

MONIK_1INCH_API_KEY

MONIK_0X_API_KEY

MONIK_TELEGRAM_BOT_TOKEN

Фактические имена определяются implementation.

---

## 8. Secret References

Configuration должна хранить reference на secret source, а не сам secret.

---

## 9. Secret Redaction

При logging и diagnostics secrets должны автоматически заменяться на:

[REDACTED]

---

## 10. No Secret Logging

Никогда не логировать:

- API keys;
- bot tokens;
- passwords;
- authentication headers;
- private keys;
- secret environment values.

---

## 11. Error Messages

Error messages также не должны раскрывать secrets.

Raw external responses необходимо sanitise перед logging.

---

## 12. Configuration Security

Configuration validation должна предотвращать:

- пустые обязательные credentials;
- invalid secret references;
- accidental production defaults;
- insecure endpoints, если они запрещены policy.

---

## 13. Least Privilege

Каждый provider credential должен иметь только необходимые permissions.

Если API key позволяет ограничить права:

использовать минимально необходимый scope.

---

## 14. Provider Credentials

Provider credentials должны использоваться только соответствующим Adapter.

Другие subsystems не должны иметь прямой доступ к raw credentials.

---

## 15. Telegram Credentials

Telegram bot token должен быть доступен только Telegram Adapter/Notification layer.

---

## 16. Secret Boundary

Поток должен быть:

Configuration
→ Secret Resolver
→ Adapter

Business logic не должна получать credentials без необходимости.

---

## 17. No Credential Propagation

Quote, Candidate, Job и Opportunity contracts не должны содержать API credentials.

---

## 18. Network Security

Все внешние API requests должны использовать защищённый transport, например HTTPS, если provider его поддерживает.

---

## 19. TLS

Не отключать TLS certificate verification в production.

Нельзя использовать insecure HTTP вместо HTTPS без explicit approved exception.

---

## 20. External Endpoints

External endpoints должны быть configuration-driven.

Не разрешать произвольные runtime URLs из непроверенных внешних данных.

---

## 21. SSRF Protection

Если приложение получает URL из external data:

необходимо предотвращать запросы к:

- localhost;
- private networks;
- metadata endpoints;
- internal services;

если такие requests не являются explicit частью approved configuration.

---

## 22. URL Validation

External URL должен проходить validation:

- protocol;
- host;
- allowed endpoint;
- network policy.

---

## 23. API Response Validation

Нельзя доверять external API response.

Перед использованием response должен пройти:

- schema validation;
- type validation;
- semantic validation.

---

## 24. Malformed Response

Malformed provider response должен приводить к normalized error.

Не пытаться использовать частично распарсенные financial values.

---

## 25. Financial Data Integrity

Financial values должны использовать exact representation.

Binary floating point запрещён для:

- amounts;
- fees;
- gas values;
- profit;
- percentages.

---

## 26. Token Address Validation

Token addresses должны проходить network-specific validation.

Symbol сам по себе не является достаточным идентификатором token.

---

## 27. Input Validation

Все внешние и configuration inputs должны проходить validation до использования.

---

## 28. Injection Protection

Database queries должны использовать parameterized queries.

Нельзя строить SQL statements через небезопасную string interpolation.

---

## 29. Command Execution

Application не должна выполнять shell commands на основании непроверенных external inputs.

---

## 30. File Access

Пути к файлам, которые поступают из configuration или external input, должны быть validated.

Не допускать произвольный path traversal.

---

## 31. Path Traversal

Не разрешать конструкции, позволяющие выйти за пределы разрешённого directory.

---

## 32. Configuration File Permissions

Production configuration с sensitive references должна иметь минимально необходимые filesystem permissions.

---

## 33. Database Permissions

SQLite database и её backup files должны быть доступны только пользователю/process, которому это необходимо.

---

## 34. Database Backup

Database backups должны иметь такие же или более строгие permissions, как основная database.

---

## 35. Temporary Files

Sensitive temporary files должны:

- использовать controlled directory;
- удаляться после использования;
- не попадать в Git;
- не попадать в logs.

---

## 36. Git Safety

Repository должен содержать безопасные defaults для предотвращения случайного commit secrets.

---

## 37. Gitignore

В `.gitignore` должны быть предусмотрены sensitive/local files.

Минимально рассмотреть:

- `.env`;
- local configuration;
- SQLite database;
- logs;
- backups;
- temporary files.

---

## 38. Example Configuration

Repository может содержать example configuration.

Она должна содержать только placeholders.

Например:

API_KEY=YOUR_API_KEY

Никогда не использовать реальные credentials.

---

## 39. Dependency Security

External dependencies должны быть ограничены необходимыми библиотеками.

Не добавлять dependency без практической необходимости.

---

## 40. Dependency Pinning

Production dependencies должны иметь контролируемые versions.

Изменение dependency должно проходить testing.

---

## 41. Dependency Updates

Dependencies должны периодически обновляться для устранения известных security vulnerabilities.

---

## 42. Vulnerability Handling

Если dependency содержит критическую vulnerability:

необходимо оценить:

- affected functionality;
- exploitability;
- available patch;
- compatibility.

---

## 43. HTTP Client Security

HTTP client должен иметь:

- timeout;
- TLS verification;
- ограничение response size;
- controlled redirects;
- normalized error handling.

---

## 44. Response Size

Не принимать бесконечно большие external responses.

Должен существовать разумный maximum response size.

---

## 45. Redirects

External HTTP redirects должны быть контролируемыми.

Нельзя автоматически доверять redirect на любой arbitrary host.

---

## 46. Rate Limits

Security и Resource Manager должны предотвращать:

- accidental request floods;
- runaway loops;
- external API abuse.

---

## 47. Concurrency Limits

Нельзя создавать неограниченное количество concurrent external requests.

---

## 48. Retry Safety

Retries должны быть:

- ограниченными;
- controlled;
- idempotent, когда это возможно.

---

## 49. Retry Amplification

Нельзя допускать nested retry mechanisms, создающих request amplification.

---

## 50. Authentication Failures

AUTH_ERROR не должен приводить к бесконечным retry.

---

## 51. API Key Rotation

Архитектура должна позволять заменять API credentials без изменения business code.

---

## 52. Telegram Token Rotation

Telegram bot token должен заменяться через secret configuration mechanism.

---

## 53. Runtime Secret Exposure

Secrets не должны попадать в:

- domain models;
- database records;
- notifications;
- metrics labels;
- exception messages.

---

## 54. Metrics Security

Metrics labels не должны содержать:

- API keys;
- tokens;
- passwords;
- sensitive URLs;
- secret values.

---

## 55. Logs

Logs должны считаться потенциально доступными оператору/администратору.

Поэтому туда нельзя записывать secrets.

---

## 56. Log Injection

External strings, попадающие в logs, должны быть безопасно структурированы.

Не позволять external data подделывать log entries.

---

## 57. Sensitive Provider Responses

Raw provider responses не следует сохранять целиком без необходимости.

Особенно если response может содержать credentials или internal metadata.

---

## 58. Telegram Security

Telegram messages должны содержать только необходимые opportunity data.

Не отправлять:

- API keys;
- internal credentials;
- database paths;
- server secrets;
- stack traces.

---

## 59. Notification Security

Notification System должна получать только normalized confirmed data.

Она не должна иметь доступа к private keys или unrelated credentials.

---

## 60. Database Security

Database должна защищаться от:

- unauthorized filesystem access;
- accidental exposure;
- unbounded growth;
- unsafe SQL;
- corrupted state.

---

## 61. Integrity

Critical database operations должны использовать transactions.

---

## 62. Migration Security

Database migrations должны быть versioned и reviewable.

Нельзя выполнять arbitrary SQL migration из непроверенного external input.

---

## 63. Backup Security

Backup files не должны:

- попадать в Git;
- отправляться в Telegram;
- становиться публичными;
- храниться без access control.

---

## 64. Access Control

Production server/user account должен иметь минимально необходимые filesystem permissions.

---

## 65. Process Isolation

Если deployment environment позволяет:

Monik должен запускаться под отдельным non-root user.

---

## 66. Root

Не рекомендуется запускать Monik от root без необходимости.

---

## 67. Container Security

Если Monik запускается в container:

рекомендуется:

- non-root user;
- read-only filesystem где возможно;
- ограниченные capabilities;
- минимальный base image;
- secrets вне image.

---

## 68. No Secrets in Images

Docker/container images не должны содержать production credentials.

---

## 69. Environment Separation

Development, testing и production credentials должны быть разделены.

---

## 70. Test Credentials

Automated tests должны использовать mock/test credentials.

Не использовать production credentials.

---

## 71. Provider Mocks

Tests provider adapters должны по возможности использовать mocks/fixtures.

Не выполнять ненужные production API requests во время unit tests.

---

## 72. Security Testing

Необходимо тестировать:

- secret redaction;
- invalid input;
- malformed provider response;
- SQL injection;
- path traversal;
- oversized response;
- timeout;
- retry amplification;
- credential errors;
- unauthorized configuration;
- sensitive data leakage.

---

## 73. Static Analysis

Проект должен по возможности использовать:

- linter;
- type checker;
- dependency vulnerability scanner;
- secret scanner.

---

## 74. Secret Scanning

Перед production deployment необходимо проверять repository на случайно закоммиченные secrets.

---

## 75. Code Review

Изменения, затрагивающие:

- authentication;
- secrets;
- external requests;
- database;
- configuration;
- security boundaries

должны проходить дополнительную проверку.

---

## 76. Security Events

Существенные security-related events должны логироваться.

Например:

- authentication failure;
- invalid credential;
- blocked endpoint;
- invalid configuration;
- repeated provider failures.

---

## 77. No Sensitive Event Data

Security logs не должны раскрывать сами credentials.

---

## 78. Incident Handling

При обнаружении потенциальной утечки credentials необходимо:

1. прекратить использование compromised credential;
2. заменить/отозвать credential;
3. проверить repository/logs;
4. определить scope exposure;
5. восстановить безопасную configuration.

---

## 79. Credential Compromise

Если API key или Telegram token был опубликован:

нельзя считать удаление commit достаточным.

Credential должен быть rotated/revoked.

---

## 80. Security Defaults

Production defaults должны быть conservative.

По умолчанию:

- trading execution disabled;
- insecure transport disabled;
- secrets logging disabled;
- unlimited retries disabled;
- public health endpoint disabled;
- arbitrary external URLs disabled.

---

## 81. Critical Invariants

Security никогда не должна позволять:

1. хранить production secrets в Git;

2. логировать secrets;

3. отправлять secrets в Telegram;

4. хранить private keys на текущем этапе;

5. выполнять automatic swaps;

6. отключать TLS verification в production;

7. выполнять unlimited retries;

8. выполнять SQL через unsafe string interpolation;

9. принимать arbitrary external URLs без validation;

10. принимать бесконечно большие responses;

11. запускать production application с invalid credentials;

12. использовать production credentials в tests;

13. хранить secrets в Docker/container image;

14. запускать application с избыточными privileges без необходимости;

15. считать external API response доверенным без validation.

---

## 82. Главный принцип

Security должна обеспечить:

**защиту credentials, финансовых данных, infrastructure и внутренних boundaries Monik при сохранении минимально необходимого уровня доступа для каждой subsystem.**

Главное правило:

**если системе не нужен доступ к данным или ресурсу для выполнения её задачи, система не должна этот доступ получать.**

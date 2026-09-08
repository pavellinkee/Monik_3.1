# MONIK — CONFIGURATION

## 1. Назначение

Этот документ определяет обязательную архитектуру configuration system Monik.

Configuration отвечает за:

- runtime settings;
- provider settings;
- network settings;
- scanner parameters;
- fee parameters;
- scheduler parameters;
- notification settings;
- resource limits;
- retention policies;
- observability settings.

Configuration не является местом хранения secrets.

---

## 2. Главный принцип

Configuration должна быть:

- explicit;
- validated;
- version-controlled where appropriate;
- environment-aware;
- predictable;
- безопасной;
- доступной через единый interface.

Business logic не должна самостоятельно читать environment variables или configuration files.

---

## 3. Configuration Boundary

Все configuration values должны проходить через Configuration subsystem.

Логически:

configuration source
→ parser
→ validation
→ normalized configuration
→ application services.

---

## 4. Sources

Configuration может поступать из:

- configuration file;
- environment variables;
- command-line arguments;
- secret manager;
- deployment parameters.

---

## 5. Source Priority

Если несколько источников задают одно значение:

должен существовать deterministic priority order.

Рекомендуемый порядок:

1. explicit runtime override;
2. environment/deployment override;
3. configuration file;
4. safe default.

---

## 6. No Ambiguous Overrides

Один configuration value не должен одновременно иметь несколько conflicting sources без понятного precedence rule.

---

## 7. Defaults

Defaults допускаются только для безопасных значений.

Critical configuration не должна иметь опасный implicit default.

---

## 8. Fail Safe

Если critical configuration отсутствует или invalid:

application должен отказаться от соответствующей operation.

---

## 9. Configuration Validation

Validation должна проверять:

- required fields;
- types;
- ranges;
- enums;
- formats;
- relationships;
- cross-field constraints.

---

## 10. Type Validation

Каждое configuration value должно иметь explicit type.

Например:

- integer;
- decimal;
- boolean;
- string;
- enum;
- duration;
- list;
- mapping.

---

## 11. Range Validation

Numeric values должны иметь допустимый range.

Например:

- timeout > 0;
- retry count >= 0;
- concurrency > 0.

---

## 12. Enum Validation

Значения с ограниченным набором вариантов должны использовать explicit enum.

---

## 13. Duration

Duration должна иметь единообразное representation.

Не смешивать:

- seconds;
- milliseconds;
- minutes

без explicit units.

---

## 14. Monetary Configuration

Financial configuration должна использовать Decimal/exact representation.

---

## 15. No Float Configuration

Configuration values, влияющие на financial calculations, не должны использовать binary Float.

---

## 16. Amount Configuration

Configured token amounts должны иметь:

- token identifier;
- amount;
- network context, если необходимо.

---

## 17. Scanner Configuration

Scanner configuration должна определять:

- enabled networks;
- enabled providers;
- token universe;
- scan intervals;
- amount combinations;
- concurrency limits;
- candidate limits;
- freshness constraints.

---

## 18. Level 1 Configuration

Level 1 configuration должна контролировать:

- scan interval;
- scan scope;
- provider set;
- network set;
- token set;
- preliminary filtering;
- queue limits.

---

## 19. Level 2 Configuration

Level 2 configuration должна контролировать:

- confirmation concurrency;
- freshness;
- expiration;
- retry policy;
- job limits;
- confirmation requirements.

---

## 20. Profit Configuration

Profit Calculator configuration должна содержать только policy parameters.

Financial formula implementation остаётся в Profit Calculator.

---

## 21. Threshold Configuration

Если используются profitability thresholds:

они должны быть configuration-driven.

Не hard-code thresholds внутри Scanner.

---

## 22. Fee Configuration

Fee System configuration должна определять:

- refresh intervals;
- freshness limits;
- provider fee sources;
- fallback policy.

---

## 23. Gas Configuration

Gas-related configuration должна определять:

- networks;
- freshness;
- provider/source;
- fallback policy.

---

## 24. Resource Manager Configuration

Resource Manager должен иметь configuration для:

- global concurrency;
- provider limits;
- network limits;
- request timeout;
- retries;
- backoff;
- jitter;
- queue size;
- circuit breaker.

---

## 25. Provider Configuration

Каждый provider должен иметь:

- enabled/disabled;
- base URL;
- API credential reference;
- timeout;
- rate limit;
- network support;
- capability settings.

---

## 26. Provider URL

Provider base URL должен быть validated.

---

## 27. Provider Allowlist

Production provider endpoints должны соответствовать approved configuration.

---

## 28. Provider Credentials

Configuration должна содержать reference на credential, а не сам secret, если используется secret manager.

---

## 29. Network Configuration

Каждая network configuration должна иметь:

- stable identifier;
- enabled/disabled;
- supported providers;
- native token;
- relevant network metadata.

---

## 30. Unsupported Network

Unknown network configuration должна быть rejected.

---

## 31. Token Configuration

Token metadata должна поступать из Token Registry.

Configuration может определять:

- enabled tokens;
- scanning universe;
- token groups;
- exclusions.

---

## 32. Canonical Token Data

Configuration не должна создавать duplicate canonical token metadata.

Token Registry является authoritative source.

---

## 33. Capability Configuration

Configuration может задавать:

- enabled capabilities;
- provider/network restrictions;
- operational limits.

---

## 34. Capability vs Configuration

Configuration определяет desired state.

Capability Registry определяет actual supported state.

---

## 35. Scheduler Configuration

Scheduler configuration должна определять:

- task intervals;
- startup tasks;
- maintenance tasks;
- cleanup tasks;
- fee refresh;
- health checks.

---

## 36. Scheduler Safety

Scheduler configuration не должна позволять создавать uncontrolled task frequency.

---

## 37. Minimum Interval

Для high-frequency operations должен существовать minimum allowed interval.

---

## 38. Notification Configuration

Notification configuration должна определять:

- enabled/disabled;
- destinations;
- retry;
- rate limit;
- formatting;
- language;
- duplicate policy.

---

## 39. Notification Destinations

Destinations должны быть explicit configured identifiers.

---

## 40. No Arbitrary Destination

Untrusted input не должен определять Notification destination.

---

## 41. Database Configuration

Database configuration должна определять:

- path;
- timeout;
- journal mode;
- backup policy;
- retention-related settings.

---

## 42. Database Path

Database path не должен быть hard-coded в business logic.

---

## 43. Production Database Protection

Production configuration не должна позволять случайно направить application на test database или наоборот.

---

## 44. Environment

Configuration должна явно знать environment:

- development;
- testing;
- staging;
- production.

---

## 45. Environment Isolation

Production configuration не должна случайно использовать development/test credentials.

---

## 46. Test Configuration

Test configuration должна быть отдельной.

---

## 47. Test Safety

Test environment должен иметь protection от подключения к production infrastructure.

---

## 48. Production Safety Check

Перед startup production должен проверять environment identity и critical configuration.

---

## 49. Development Defaults

Development defaults не должны использоваться в production автоматически.

---

## 50. Configuration Schema

Configuration schema должна быть machine-readable или equivalent strongly validated definition.

---

## 51. Example Configuration

Repository может содержать:

`config/config.example.yaml`

или equivalent example.

Он не должен содержать реальные secrets.

---

## 52. Configuration Documentation

Каждый public configuration parameter должен иметь описание:

- purpose;
- type;
- allowed values;
- default;
- security implications.

---

## 53. Unknown Fields

Unknown configuration fields должны либо:

- приводить к validation error;

либо иметь explicit forward-compatibility policy.

Silent ignore не рекомендуется.

---

## 54. Missing Fields

Missing required fields должны приводить к validation error.

---

## 55. Null Values

Null допускается только если parameter действительно optional.

---

## 56. Cross-Field Validation

Необходимо проверять зависимости между fields.

Например:

если provider enabled:

его required configuration должна существовать.

---

## 57. Provider Dependency

Если provider disabled:

его credentials не должны считаться обязательными для startup.

---

## 58. Network Dependency

Если network disabled:

её provider configuration не должна активировать scanning этой network.

---

## 59. Scanner Dependency

Если Level 1 disabled:

Level 2 не должен получать новые candidates от него.

---

## 60. Notification Dependency

Если Notification disabled:

confirmed opportunities всё равно должны сохраняться.

---

## 61. Configuration Immutability

После startup normalized configuration должна быть immutable или изменяться только через controlled configuration mechanism.

---

## 62. Runtime Reload

Runtime configuration reload допускается только для settings, которые безопасно менять без restart.

---

## 63. Reload Policy

Каждый reloadable parameter должен иметь explicit reload policy.

---

## 64. Non-Reloadable Settings

Следующие изменения могут требовать restart:

- database path;
- provider credentials;
- architecture-critical settings;
- dependency wiring;
- network infrastructure.

---

## 65. Reload Validation

Перед применением новой configuration она должна пройти полную validation.

---

## 66. Atomic Reload

Configuration reload должен быть atomic.

Нельзя применить половину новой configuration.

---

## 67. Failed Reload

Если validation новой configuration failed:

текущая valid configuration должна сохраниться.

---

## 68. Configuration Version

Каждая normalized configuration может иметь version/hash для diagnostics.

---

## 69. Configuration Hash

Configuration fingerprint может использоваться для определения фактической runtime configuration.

Secrets не должны входить в plain-text fingerprint.

---

## 70. Secret Redaction

Configuration diagnostics должны redacted:

- API keys;
- tokens;
- passwords;
- private keys.

---

## 71. Configuration Logging

На startup можно логировать summary configuration.

Нельзя логировать secrets.

---

## 72. No Full Config Dump

Не выводить полную configuration в production logs без redaction.

---

## 73. Configuration Errors

Configuration errors должны использовать normalized Error Handling.

---

## 74. Startup Configuration Failure

При critical configuration error application не должен переходить в HEALTHY.

---

## 75. Partial Configuration Failure

Если отдельный optional provider invalid:

application может запуститься DEGRADED, если architecture допускает его отключение.

---

## 76. Critical Configuration

Configuration, необходимая для безопасного Level 2 confirmation, является critical.

---

## 77. Safe Disable

Если configuration provider/network invalid:

безопаснее отключить соответствующую capability, чем выполнять operation с неизвестными parameters.

---

## 78. No Unsafe Fallback

Invalid configuration не должна автоматически заменяться arbitrary default.

---

## 79. Configuration and Secrets Separation

Configuration system должна различать:

- public configuration;
- sensitive configuration;
- secret values.

---

## 80. Secret References

По возможности использовать:

`secret_ref`

вместо хранения secret value в configuration file.

---

## 81. Secret Availability

Если required secret не может быть resolved:

соответствующий provider должен перейти в unavailable/degraded state.

---

## 82. Secret Rotation

После rotation configuration reload/restart должен получить новый secret без изменения source code.

---

## 83. Environment Variables

Environment variables должны проходить тот же validation pipeline, что и configuration file.

---

## 84. CLI Overrides

CLI overrides допустимы только для approved parameters.

---

## 85. CLI Safety

CLI не должен позволять случайно переопределить critical production safety settings без explicit policy.

---

## 86. Configuration Precedence Tests

CI должен тестировать:

- file value;
- environment override;
- explicit override;
- default.

---

## 87. Configuration Validation Tests

Каждый critical configuration section должен иметь:

- valid case;
- missing case;
- invalid type;
- invalid range;
- invalid enum;
- dependency failure.

---

## 88. Configuration Security Tests

Тестировать:

- secret redaction;
- production/test isolation;
- unsafe URL rejection;
- invalid credentials handling.

---

## 89. Configuration Migration

Если schema configuration меняется:

необходимо иметь migration/compatibility strategy.

---

## 90. Backward Compatibility

Если старый configuration format временно поддерживается:

его conversion должен быть deterministic.

---

## 91. Deprecated Parameters

Deprecated configuration fields должны иметь:

- warning;
- migration path;
- removal policy.

---

## 92. No Silent Deprecation

Не удалять configuration parameter silently.

---

## 93. Operational Limits

Configuration должна ограничивать потенциально опасные values.

Например:

- maximum concurrency;
- maximum queue size;
- maximum request rate;
- maximum response size.

---

## 94. Resource Protection

Нельзя позволять configuration создать unbounded:

- concurrency;
- queues;
- retries;
- memory usage;
- disk growth.

---

## 95. Retention Configuration

Retention settings должны иметь safe bounds.

---

## 96. Backup Configuration

Backup frequency и retention должны иметь safe minimums.

---

## 97. Logging Configuration

Logging configuration должна позволять контролировать:

- level;
- format;
- rotation;
- retention.

---

## 98. Observability Configuration

Metrics/tracing configuration не должна раскрывать secrets.

---

## 99. Final Configuration Validation

Перед production startup необходимо проверить:

- environment;
- database;
- providers;
- networks;
- tokens;
- capabilities;
- resource limits;
- scheduler;
- notifications;
- retention;
- observability;
- security.

---

## 100. Critical Invariants

Configuration никогда не должна позволять:

1. запускать production с invalid critical settings;

2. хранить secrets в Git;

3. silently игнорировать неизвестные critical fields;

4. использовать production credentials в tests;

5. направлять production application на test database;

6. направлять test application на production database;

7. запускать unsupported provider/network;

8. использовать unvalidated provider URL;

9. создавать unlimited concurrency;

10. создавать unlimited queues;

11. создавать unlimited retries;

12. задавать unsafe financial values;

13. изменять configuration частично;

14. применять invalid runtime reload;

15. использовать secret values в logs;

16. позволять untrusted input менять configuration;

17. использовать arbitrary defaults вместо required configuration;

18. обходить Configuration subsystem из business logic.

---

## 101. Главный принцип

Configuration должна обеспечить:

**единый, validated и безопасный источник runtime settings, при котором application получает уже нормализованную configuration и никогда не должен самостоятельно интерпретировать environment variables, configuration files или secrets.**

Поток должен быть:

**sources → parse → validate → normalize → resolve secrets → freeze/apply → observe.**

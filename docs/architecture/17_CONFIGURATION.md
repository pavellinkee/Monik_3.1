# MONIK — CONFIGURATION

## 1. Назначение

Configuration subsystem — единая система управления настройками Monik.

Она отвечает за:

- загрузку configuration;
- validation;
- defaults;
- environment variables;
- secrets references;
- user-configurable parameters;
- runtime configuration access;
- защиту от некорректных значений.

Configuration является единственным authoritative source для пользовательских настроек.

---

## 2. Главный принцип

Все параметры, которые пользователь должен иметь возможность изменять без изменения application code, должны находиться в configuration.

Business logic не должна содержать hard-coded user settings.

---

## 3. Configuration Layers

Configuration должна логически разделяться на:

- application configuration;
- network configuration;
- provider configuration;
- scanner configuration;
- scheduler configuration;
- fee configuration;
- notification configuration;
- database configuration;
- operational limits.

---

## 4. User Configuration

User configuration должна содержать только параметры, которые действительно предназначены для изменения пользователем.

Internal implementation details не должны требовать ручного изменения.

---

## 5. Secrets

Secrets не должны храниться непосредственно в обычном configuration file.

Например:

- API keys;
- Telegram bot token;
- private credentials;
- authentication secrets.

Они должны поступать через безопасный secrets/environment mechanism.

---

## 6. Environment Variables

Configuration должна поддерживать environment variables для secrets и deployment-specific settings.

Environment variables не должны бесконтрольно смешиваться с business configuration.

---

## 7. Configuration File

Основной configuration file должен иметь определённый и стабильный формат.

Формат должен быть удобен для ручного редактирования.

---

## 8. Configuration Path

Путь к configuration file должен быть определён deployment policy.

Не hard-code путь внутри отдельных subsystems.

---

## 9. Loading

При startup Configuration subsystem должна:

1. определить источник configuration;
2. загрузить configuration;
3. применить разрешённые environment overrides;
4. применить defaults;
5. выполнить validation;
6. создать immutable/validated configuration object;
7. передать configuration остальным subsystems.

---

## 10. Validation First

Application не должен запускать critical subsystems до завершения configuration validation.

---

## 11. Invalid Configuration

Если обязательный параметр отсутствует или имеет недопустимое значение:

startup должен завершиться согласно explicit configuration failure policy.

Нельзя молча подставлять опасные значения.

---

## 12. Defaults

Defaults разрешены только для параметров, для которых безопасное default value однозначно определено архитектурой.

---

## 13. Dangerous Defaults

Нельзя использовать опасные defaults для:

- trading execution;
- private keys;
- Telegram destination;
- API credentials;
- неизвестных fees;
- автоматических swaps.

---

## 14. No Automatic Trading

Configuration не должна иметь default configuration, которая активирует автоматическое выполнение swaps.

---

## 15. Type Validation

Каждый configuration parameter должен иметь ожидаемый type.

Например:

- integer;
- decimal;
- boolean;
- string;
- list;
- mapping;
- duration;
- time;
- timezone.

---

## 16. Range Validation

Numeric parameters должны иметь допустимый range.

Например:

- interval > 0;
- amount > 0;
- concurrency >= 1;
- retry limit >= 0.

---

## 17. Enum Validation

Параметры с ограниченным набором значений должны использовать explicit enum validation.

Например:

mode:

- STARTUP;
- DAILY;
- MANUAL.

---

## 18. Time Validation

Time parameters должны использовать формат:

HH:MM

Неверное значение должно приводить к configuration error.

---

## 19. Timezone Validation

Timezone должна быть валидной IANA timezone.

Например:

Europe/Lisbon

---

## 20. Decimal Configuration

Финансовые значения должны загружаться в exact decimal representation.

Не преобразовывать configuration amounts в binary float.

---

## 21. Amounts

Все scanner amounts должны задаваться configuration.

Scanner не должен содержать hard-coded trading amounts.

---

## 22. Amount Validation

Каждая configured amount должна быть:

- положительной;
- валидной;
- совместимой с выбранным token;
- представимой с необходимой precision.

---

## 23. Networks

Enabled networks должны определяться configuration.

Для каждой network могут задаваться:

- chain ID;
- RPC configuration;
- native token;
- enabled status;
- provider availability.

---

## 24. Network Isolation

Configuration одной network не должна автоматически применяться к другой network.

---

## 25. Providers

Каждый aggregator/provider должен иметь отдельный configuration section.

Минимально:

- enabled;
- supported networks;
- credentials reference;
- request limits;
- timeout policy.

---

## 26. Provider Credentials

Credentials должны ссылаться на secrets source.

Не хранить реальные API keys в repository.

---

## 27. Provider Enable/Disable

Disabled provider не должен получать requests.

---

## 28. Tokens

Token configuration должна определять разрешённый token universe.

Но authoritative token metadata должен находиться в Token Registry.

---

## 29. Top 30

На текущем этапе scanner должен использовать:

Top 30 tokens.

Конкретный список должен быть configuration/registry-driven.

---

## 30. Routes

Routes должны быть определены configuration/approved architecture.

Scanner не должен создавать произвольные routes самостоятельно.

---

## 31. Fixed Routes

На текущем этапе routes являются fixed routes.

Изменение route должно происходить через configuration или утверждённую архитектурную процедуру.

---

## 32. Scanner Configuration

Configuration должна позволять задавать:

- enabled;
- scan interval;
- amounts;
- networks;
- tokens;
- providers;
- routes;
- preliminary policy;
- concurrency limits.

---

## 33. Level 1 Interval

Level 1 scan interval должен быть configurable.

Текущий production default:

5 минут.

---

## 34. Level 1 Limits

Configuration должна поддерживать limits для:

- candidates per scan;
- concurrency;
- request batches;
- queue capacity.

---

## 35. Level 2 Configuration

Configuration должна поддерживать:

- queue capacity;
- job lifetime;
- confirmation timeout;
- priority;
- concurrency;
- deduplication window.

---

## 36. Profitability Configuration

Profitability policy должна задаваться централизованно.

Минимально:

- final threshold;
- preliminary threshold;
- precision;
- required cost components.

---

## 37. No Duplicate Profit Rules

Profitability thresholds и formulas не должны дублироваться в Scanner modules.

---

## 38. Fee Configuration

Fee System configuration должна позволять задавать:

- enabled;
- refresh schedule;
- freshness policy;
- provider-specific configuration;
- fallback policy.

---

## 39. Unknown Fee Policy

Configuration должна явно определять поведение при UNKNOWN mandatory fee.

Без explicit policy UNKNOWN fee не должна считаться zero.

---

## 40. Gas Configuration

Gas configuration должна позволять задавать:

- provider/source;
- timeout;
- freshness;
- fallback policy.

---

## 41. Resource Manager Configuration

Resource Manager должен иметь configuration для:

- global concurrency;
- provider concurrency;
- rate limits;
- timeout;
- retry;
- backoff;
- queue limits;
- priorities.

---

## 42. Retry Configuration

Retry policy должна быть ограниченной.

Минимально:

- max attempts;
- initial delay;
- maximum delay;
- backoff policy.

---

## 43. No Infinite Retry

Configuration не должна позволять бесконечный retry для внешних requests.

---

## 44. Scheduler Configuration

Scheduler configuration должна поддерживать:

- startup;
- daily;
- manual;
- interval_days;
- time;
- timezone;
- enabled;
- priority;
- overlap policy.

---

## 45. Notification Configuration

Notification configuration должна поддерживать:

- enabled;
- destinations;
- language;
- template;
- precision;
- retry;
- deduplication;
- queue capacity.

---

## 46. Telegram Configuration

Telegram configuration должна содержать references на:

- bot token;
- destination/chat ID.

Actual secrets должны находиться вне repository.

---

## 47. Database Configuration

Database configuration должна поддерживать:

- database path;
- timeout;
- WAL policy;
- backup policy;
- retention;
- cleanup schedule.

---

## 48. Logging Configuration

Logging configuration должна позволять задавать:

- log level;
- output;
- retention;
- structured logging;
- diagnostics level.

Secrets никогда не должны выводиться независимо от log level.

---

## 49. Metrics Configuration

Metrics configuration может управлять:

- enabled;
- collection level;
- retention;
- export destination.

---

## 50. Configuration Immutability

После успешной загрузки configuration object должен рассматриваться как immutable в рамках текущего runtime.

---

## 51. Runtime Changes

Изменение configuration во время работы допускается только через explicit reload mechanism.

Не менять отдельные поля configuration object напрямую из business modules.

---

## 52. Configuration Reload

Если будет реализован reload:

он должен:

1. загрузить новую configuration;
2. выполнить validation;
3. сравнить изменения;
4. определить безопасные изменения;
5. применить их атомарно.

Некорректная новая configuration не должна заменять рабочую.

---

## 53. Reload Safety

При ошибке reload приложение продолжает использовать последнюю валидную configuration.

---

## 54. Immutable Snapshot

Каждый operation может использовать configuration snapshot.

Snapshot должен оставаться консистентным в течение operation.

---

## 55. No Partial Configuration

Нельзя применять новую configuration частично, если это может привести к несовместимому состоянию subsystems.

---

## 56. Configuration Version

Каждая loaded configuration должна иметь version или deterministic fingerprint.

---

## 57. Diagnostics

Configuration diagnostics должны позволять определить:

- loaded version;
- source;
- active networks;
- active providers;
- active scanners;
- scheduler configuration;
- notification configuration.

Secrets должны быть скрыты.

---

## 58. Secret Redaction

При выводе configuration в logs или diagnostics:

secrets заменяются на redacted values.

Например:

[REDACTED]

---

## 59. Environment Precedence

Если поддерживается несколько источников:

приоритет должен быть явно определён.

Например:

environment override
→ configuration file
→ safe default.

---

## 60. No Hidden Overrides

Не должно существовать скрытых configuration overrides внутри отдельных modules.

---

## 61. Configuration Errors

Ошибки должны содержать:

- parameter path;
- invalid value type/range;
- expected value;
- actionable explanation.

Не раскрывать secrets в error messages.

---

## 62. Cross-Field Validation

Configuration validation должна проверять не только отдельные поля, но и зависимости между ними.

Например:

enabled provider должен поддерживать хотя бы одну enabled network.

---

## 63. Cross-Subsystem Validation

Необходимо проверять совместимость:

- tokens ↔ networks;
- providers ↔ networks;
- routes ↔ tokens;
- routes ↔ providers;
- amounts ↔ token precision;
- scheduler tasks ↔ available subsystems.

---

## 64. Disabled Dependencies

Если subsystem disabled:

зависимые features должны быть обработаны согласно explicit policy.

---

## 65. Startup Validation

Перед запуском Scanner необходимо убедиться, что:

- есть хотя бы одна enabled network;
- есть необходимые tokens;
- есть необходимые providers;
- есть valid routes;
- есть configured amounts.

---

## 66. Provider Availability

Configuration validation не должна считать provider доступным только потому, что он enabled.

Фактическая availability определяется Capability/Health subsystems.

---

## 67. Configuration and Capability

Configuration определяет:

что разрешено.

Capability Registry определяет:

что фактически поддерживается.

---

## 68. Configuration and Resource Manager

Configuration определяет допустимые limits.

Resource Manager обеспечивает их runtime enforcement.

---

## 69. Configuration and Scheduler

Configuration определяет schedule.

Scheduler отвечает за execution.

---

## 70. Configuration and Profit Calculator

Configuration определяет policy parameters.

Profit Calculator выполняет calculations.

---

## 71. Configuration and Notification

Configuration определяет notification preferences.

Notification System выполняет delivery.

---

## 72. Example Structure

Пример логической структуры configuration:

    application:
      environment: production

    networks:
      polygon:
        enabled: true

    providers:
      1inch:
        enabled: true

      0x:
        enabled: true

      velora:
        enabled: true

      uniswap:
        enabled: true

    scanner:
      level1:
        enabled: true
        interval_seconds: 300

      level2:
        enabled: true

---

## 73. Amount Example

    scanner:
      amounts:
        - "100"
        - "500"
        - "1000"

Фактическая структура может быть изменена при реализации, если она сохраняет архитектурные требования.

---

## 74. Scheduler Example

    scheduler:
      fee_refresh:
        enabled: true
        mode: DAILY
        interval_days: 1
        time: "02:00"
        timezone: "Europe/Lisbon"

---

## 75. Notification Example

    notifications:
      telegram:
        enabled: true
        language: "en"

        bot_token:
          env: "MONIK_TELEGRAM_BOT_TOKEN"

        chat_id:
          env: "MONIK_TELEGRAM_CHAT_ID"

---

## 76. Configuration Schema

Configuration должна иметь machine-readable schema или эквивалентный validation mechanism.

---

## 77. Schema Version

Configuration schema должна иметь собственную version.

Она независима от SQLite schema version.

---

## 78. Backward Compatibility

Изменение configuration schema должно учитывать существующие configuration files.

---

## 79. Migration

Если изменение schema несовместимо:

должна существовать explicit migration path или понятная migration error.

---

## 80. Testing

Обязательно тестировать:

- valid configuration;
- missing required fields;
- wrong types;
- invalid ranges;
- invalid enums;
- invalid time;
- invalid timezone;
- invalid decimals;
- invalid provider configuration;
- invalid network configuration;
- cross-field validation;
- cross-subsystem validation;
- environment overrides;
- secret redaction;
- reload;
- rollback to previous valid configuration.

---

## 81. Critical Invariants

Configuration subsystem никогда не должна:

1. хранить реальные secrets в repository;

2. silently принимать invalid configuration;

3. считать UNKNOWN fee равной zero;

4. использовать binary Float для финансовых configuration values;

5. позволять business modules напрямую изменять configuration;

6. иметь скрытые hard-coded overrides;

7. активировать automatic trading по умолчанию;

8. применять частично invalid configuration;

9. раскрывать secrets в logs;

10. становиться источником live market data;

11. заменять Capability Registry;

12. заменять Resource Manager;

13. дублировать profitability formulas;

14. содержать provider-specific business logic.

---

## 82. Главный принцип

Configuration должна обеспечить:

**единый, валидируемый и предсказуемый источник настроек Monik, позволяющий изменять поведение системы без изменения business code и не нарушающий границы между подсистемами.**

Configuration отвечает за:

**что разрешено и как настроено.**

Остальные subsystems отвечают за:

**как это выполняется.**

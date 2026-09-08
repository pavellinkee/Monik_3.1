# MONIK — PROJECT STRUCTURE

## 1. Назначение

Этот документ определяет обязательную структуру исходного кода Monik.

Цель:

- разделить business logic и infrastructure;
- сохранить утверждённые архитектурные boundaries;
- сделать проект понятным для разработки и тестирования;
- предотвратить хаотичное размещение файлов;
- упростить расширение проекта.

---

## 2. Главный принцип

Структура проекта должна отражать архитектуру системы.

Каждая subsystem должна иметь собственную boundary.

Нельзя размещать unrelated business logic в одном модуле только ради удобства.

---

## 3. Root Structure

Рекомендуемая структура:

    monik/
    ├── app/
    ├── config/
    ├── domain/
    ├── infrastructure/
    ├── services/
    ├── repositories/
    ├── tests/
    ├── docs/
    ├── scripts/
    ├── data/
    ├── logs/
    ├── .gitignore
    ├── README.md
    └── pyproject.toml

Фактические директории могут быть адаптированы под выбранный framework, если архитектурные boundaries сохраняются.

---

## 4. app/

`app/` содержит application lifecycle.

Он отвечает за:

- startup;
- shutdown;
- dependency wiring;
- application entrypoint;
- orchestration верхнего уровня.

---

## 5. app/main

Application entrypoint должен находиться в одном определённом месте.

Он не должен содержать business logic.

---

## 6. Startup Boundary

Startup должен только:

- загрузить configuration;
- создать dependencies;
- выполнить initialization;
- запустить application;
- обработать shutdown.

---

## 7. domain/

`domain/` содержит core domain models и правила, не зависящие от конкретных infrastructure implementations.

---

## 8. Domain Independence

Domain layer не должен напрямую зависеть от:

- HTTP clients;
- Telegram API;
- SQLite;
- environment variables;
- конкретных provider SDK.

---

## 9. domain/models/

Здесь размещаются основные domain models.

Например:

- Token;
- Quote;
- Fee;
- Gas;
- Route;
- Candidate;
- Level2Job;
- Opportunity;
- ProfitResult;
- Notification;
- Error;
- Capability;
- HealthState.

---

## 10. domain/enums/

Здесь размещаются стабильные domain enums.

Например:

- statuses;
- operation types;
- error categories;
- health states.

---

## 11. domain/value_objects/

Здесь могут находиться value objects.

Например:

- TokenAmount;
- Percentage;
- NetworkId;
- ProviderId;
- OpportunityFingerprint.

---

## 12. Financial Value Objects

Financial values должны использовать exact representation.

Не использовать binary Float.

---

## 13. services/

`services/` содержит application/business services.

Здесь размещаются:

- scanners;
- profit calculation;
- fee logic;
- scheduler;
- notification orchestration;
- resource management;
- health monitoring;
- capability management.

---

## 14. Scanner Boundary

Scanner modules должны находиться отдельно от provider adapters.

Scanner не должен содержать HTTP implementation.

---

## 15. Level 1

Level 1 Scanner должен иметь отдельную subsystem/module.

Он отвечает за:

- broad scanning;
- preliminary filtering;
- candidate creation.

---

## 16. Level 2

Level 2 Scanner должен иметь отдельную subsystem/module.

Он отвечает за:

- fresh validation;
- confirmation;
- final profitability;
- confirmed opportunity creation.

---

## 17. Profit Calculator

Profit Calculator должен находиться отдельно от Scanner.

Scanner не должен реализовывать собственные profitability formulas.

---

## 18. Fee System

Fee System должна быть отдельной subsystem.

Она не должна быть частью Aggregator Adapter.

---

## 19. Resource Manager

Resource Manager должен быть отдельной subsystem.

Он является централизованной точкой контроля external resource usage.

---

## 20. Scheduler

Scheduler должен быть отдельной subsystem.

Business modules не должны создавать собственные uncontrolled background timers.

---

## 21. Notification System

Notification System должна быть отдельной subsystem.

Она не должна получать quotes или рассчитывать profitability.

---

## 22. Health Monitoring

Health Monitoring должна быть отдельной subsystem.

Она не должна выполнять business operations ради проверки health.

---

## 23. Capability Registry

Capability Registry должна быть отдельной subsystem.

Она не должна становиться вторым Token Registry или Health Monitor.

---

## 24. Token Registry

Token Registry должен быть отдельной subsystem.

Он является authoritative source для canonical token metadata.

---

## 25. infrastructure/

`infrastructure/` содержит конкретные технические implementations.

Например:

- HTTP clients;
- provider adapters;
- Telegram adapter;
- SQLite implementation;
- filesystem;
- clock;
- external service clients.

---

## 26. Aggregator Adapters

Каждый aggregator должен иметь отдельный adapter.

Например:

    infrastructure/
    └── providers/
        ├── oneinch/
        ├── zero_x/
        ├── velora/
        └── uniswap/

Фактические имена могут соответствовать официальным provider identifiers.

---

## 27. Adapter Isolation

Provider-specific code должен находиться внутри соответствующего provider directory.

---

## 28. No Provider Logic Outside Adapter

Provider-specific:

- JSON parsing;
- endpoint paths;
- HTTP headers;
- API-specific errors;
- field mappings

не должны находиться в Scanner.

---

## 29. HTTP Client

Общий HTTP client infrastructure может быть shared.

Но provider-specific configuration остаётся внутри соответствующего Adapter.

---

## 30. Resource Manager Boundary

HTTP requests provider adapters должны проходить через Resource Manager.

Не создавать отдельные uncontrolled HTTP execution paths.

---

## 31. Telegram Adapter

Telegram implementation должна находиться в infrastructure.

Notification System работает с abstraction/interface.

---

## 32. Database Infrastructure

SQLite implementation должна находиться в infrastructure/repositories layer.

---

## 33. repositories/

`repositories/` содержит persistence access abstractions/implementations.

Например:

- opportunity repository;
- job repository;
- notification repository;
- scan repository;
- scheduler repository;
- fee repository.

---

## 34. Repository Boundary

Business services не должны содержать raw SQL.

---

## 35. Database Models

Database-specific models не должны становиться domain models.

Repository выполняет mapping.

---

## 36. config/

`config/` содержит configuration schemas, defaults и example configuration.

---

## 37. Secrets

Реальные secrets не должны находиться в `config/`.

---

## 38. Example Configuration

Можно хранить:

    config/
    ├── config.example.yaml
    └── schema.yaml

или equivalent format.

---

## 39. data/

`data/` может использоваться для runtime local data.

Например:

- SQLite database;
- temporary state;
- local registries.

Production data не должна попадать в Git.

---

## 40. logs/

`logs/` предназначена для runtime logs.

Logs не должны храниться в repository.

---

## 41. scripts/

`scripts/` содержит deployment, maintenance и operational scripts.

---

## 42. Script Boundary

Scripts не должны содержать duplicate business logic.

Они вызывают application/service interfaces.

---

## 43. docs/

`docs/` содержит архитектурную и operational documentation.

---

## 44. Architecture Documents

Утверждённые architecture documents должны находиться в:

    docs/architecture/

---

## 45. Documentation Immutability

Architecture documents являются source of architectural intent.

Claude Code не должен изменять их автоматически без explicit user approval.

---

## 46. tests/

`tests/` должна отражать структуру application.

Например:

    tests/
    ├── unit/
    ├── component/
    ├── contract/
    ├── integration/
    ├── architecture/
    ├── security/
    └── e2e/

---

## 47. Unit Tests

Unit tests должны быть максимально независимыми от infrastructure.

---

## 48. Component Tests

Component tests могут использовать controlled fake dependencies.

---

## 49. Contract Tests

Provider contract tests должны находиться отдельно.

---

## 50. Integration Tests

Integration tests могут использовать test SQLite и fake external services.

---

## 51. Architecture Tests

Architecture tests должны проверять:

- dependency direction;
- forbidden imports;
- subsystem boundaries;
- provider isolation;
- database boundaries.

---

## 52. Security Tests

Security tests должны проверять:

- secrets;
- validation;
- injection;
- unsafe URLs;
- filesystem boundaries;
- sensitive logging.

---

## 53. E2E Tests

E2E tests должны проверять полный workflow.

Они не должны использовать real trading execution.

---

## 54. Dependency Direction

Рекомендуемое направление:

    app
      ↓
    services
      ↓
    domain

Infrastructure и repositories предоставляют implementations через interfaces.

---

## 55. Infrastructure Dependency

Business services могут зависеть от abstractions, но не должны быть tightly coupled к конкретному provider implementation.

---

## 56. Domain Dependency

Domain не должен зависеть от infrastructure.

---

## 57. Repository Dependency

Services используют repository interfaces.

Concrete SQLite repositories находятся ниже boundary.

---

## 58. Provider Interface

Scanner должен работать с normalized provider interface.

Например логически:

    quote(request) -> Quote

Он не должен знать provider-specific HTTP response.

---

## 59. Notification Interface

Notification System должна работать с notification provider abstraction.

---

## 60. Clock Interface

Scheduler и expiration-sensitive services должны использовать injectable clock abstraction.

---

## 61. HTTP Interface

Provider adapters должны использовать controlled HTTP abstraction.

---

## 62. No Direct requests

Business logic не должна импортировать HTTP libraries напрямую.

Например:

    requests
    httpx
    aiohttp

не должны использоваться непосредственно Scanner modules.

---

## 63. No Direct SQLite

Business services не должны напрямую импортировать SQLite driver.

Database access выполняется через repository boundary.

---

## 64. No Direct Environment Access

Business logic не должна напрямую читать `os.environ`.

Configuration subsystem является единственным источником validated configuration.

---

## 65. No Direct Telegram

Business services не должны напрямую импортировать Telegram SDK/client.

---

## 66. No Cross-Subsystem Imports

Subsystems не должны импортировать internal implementation files друг друга без approved interface.

---

## 67. Public Interfaces

Каждая subsystem должна иметь ограниченный public interface.

Internal implementation details не должны использоваться другими modules.

---

## 68. `__init__` Boundary

Public exports subsystem должны быть централизованы.

Не рекомендуется импортировать deep internal modules из других subsystems.

---

## 69. Circular Dependencies

Circular dependencies запрещены.

Если возникает необходимость circular import:

архитектурную boundary необходимо пересмотреть.

---

## 70. Shared Utilities

Shared utilities разрешены только для действительно generic functionality.

---

## 71. No Business Logic in Utils

`utils/` не должен превращаться в место для случайной business logic.

---

## 72. Financial Utilities

Financial utility functions должны находиться в определённом financial/domain module.

Не помещать их в generic `utils`.

---

## 73. Constants

Constants должны находиться рядом с соответствующей subsystem.

Не создавать один глобальный файл с несвязанными constants.

---

## 74. Provider Constants

Provider-specific constants находятся внутри provider adapter.

---

## 75. Network Constants

Network-specific metadata находится в соответствующем registry/configuration layer.

---

## 76. Logging

Logging setup должен быть централизован.

Каждая subsystem использует общий structured logging mechanism.

---

## 77. Error Handling

Error types должны находиться в domain/application error layer.

Provider-specific exceptions остаются внутри Adapter boundary.

---

## 78. Configuration Access

Services получают validated configuration через dependency injection.

---

## 79. Dependency Injection

Dependencies рекомендуется передавать явно.

Не использовать глобальные mutable singletons для business state.

---

## 80. Runtime State

Runtime state должен находиться внутри соответствующей subsystem.

Не хранить весь application state в одном глобальном object.

---

## 81. Database State

Persistent state хранится через repositories.

---

## 82. Queue State

Queue state принадлежит соответствующей subsystem/Resource Manager.

---

## 83. Scheduler State

Scheduler state принадлежит Scheduler.

---

## 84. Notification State

Notification state принадлежит Notification System и её repository.

---

## 85. Capability State

Capability state принадлежит Capability Registry.

---

## 86. Health State

Health state принадлежит Health Monitoring.

---

## 87. Testing Files

Test fixtures и generated artifacts не должны попадать в production source directories.

---

## 88. Generated Files

Generated files должны находиться в определённой generated/build directory и не смешиваться с source code.

---

## 89. Temporary Files

Temporary files должны использовать controlled temporary directory.

---

## 90. Cache

Если runtime cache когда-либо будет добавлен:

он должен иметь explicit subsystem/boundary.

Не создавать произвольные cache files внутри source directories.

---

## 91. No Hidden Files

Не создавать hidden runtime files внутри repository без explicit policy.

---

## 92. README

Root `README.md` должен содержать:

- краткое описание Monik;
- installation;
- configuration overview;
- development setup;
- testing;
- deployment reference.

Он не заменяет architecture documents.

---

## 93. Architecture Documentation

Изменение architecture должно сопровождаться обновлением соответствующего document.

---

## 94. Code vs Documentation

Если implementation противоречит architecture documents:

необходимо сначала определить, является ли изменение архитектуры намеренным.

Не менять architecture silently через code.

---

## 95. Claude Code

Claude Code должен использовать architecture documents как обязательный architectural reference.

---

## 96. Protected Architecture

Claude Code не должен автоматически:

- удалять architecture documents;
- переименовывать их;
- изменять их содержание;
- менять established boundaries

без explicit user approval.

---

## 97. New Files

Перед созданием новой subsystem или major module необходимо определить её место в architecture.

---

## 98. File Naming

Имена файлов должны быть:

- понятными;
- стабильными;
- соответствующими subsystem;
- без случайных сокращений.

---

## 99. Module Size

Если module становится чрезмерно большим:

его следует разделить по responsibility.

Но не дробить код искусственно без architectural reason.

---

## 100. Final Structure Principle

Структура проекта должна позволять новому разработчику определить:

- где находится domain;
- где находится business logic;
- где находятся provider adapters;
- где находится database;
- где находится configuration;
- где находятся tests;
- где находится deployment;
- где находятся architecture documents.

---

## 101. Critical Invariants

Project Structure никогда не должна позволять:

1. business logic напрямую обращаться к HTTP providers;

2. business logic напрямую обращаться к SQLite;

3. business logic напрямую читать environment variables;

4. Scanner напрямую отправлять Telegram messages;

5. Provider-specific JSON попадать в domain layer;

6. Domain зависеть от infrastructure;

7. создавать circular dependencies;

8. хранить secrets в repository;

9. смешивать tests с production source code;

10. хранить runtime database в Git;

11. размещать business logic в generic `utils`;

12. создавать uncontrolled global mutable state;

13. изменять architecture documents автоматически;

14. создавать новую subsystem без определения её architectural boundary.

---

## 102. Главный принцип

Project Structure должна обеспечить:

**понятное физическое отражение архитектуры Monik, при котором domain, business logic, infrastructure, persistence, configuration, testing и deployment имеют чёткие границы и не смешиваются друг с другом.**

Файловая структура должна помогать сохранять архитектуру, а не становиться причиной её разрушения.

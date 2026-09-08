# MONIK — ARCHITECTURE MAP

## 1. Назначение

Этот документ является навигационной картой архитектуры Monik.

Он создан для того, чтобы Claude Code и разработчики понимали:

- какие документы относятся к каким subsystem;
- какие документы являются основными;
- какие документы содержат дополнительные требования;
- какие документы нельзя считать простыми копиями;
- какие документы необходимо читать совместно;
- как разрешать возможные пересечения между документами.

Этот документ не заменяет существующие architecture documents и не изменяет их содержание.

---

## 2. Главный принцип

Все существующие architecture documents являются частью architectural baseline проекта.

Нельзя удалять документ только потому, что его название или тема похожи на другой документ.

Если два документа относятся к одной subsystem, необходимо считать их совместным источником требований, пока их содержание не было официально консолидировано.

---

## 3. Правило приоритета

Для каждого subsystem необходимо сначала определить:

1. какие документы относятся к нему;
2. какие требования содержатся в каждом документе;
3. есть ли между ними противоречия;
4. является ли требование более поздним уточнением или настоящим конфликтом.

Если невозможно однозначно определить intended behavior:

Claude Code должен остановиться и запросить решение.

Нельзя самостоятельно удалять, игнорировать или переписывать requirement.

---

# 4. Architecture Layers

Архитектура Monik условно разделяется на следующие уровни:

PROJECT REQUIREMENTS
        ↓
DOMAIN / DATA MODELS
        ↓
INTERFACES / API CONTRACTS
        ↓
INFRASTRUCTURE
        ↓
RESOURCE / PROVIDER SYSTEMS
        ↓
FINANCIAL CORE
        ↓
LEVEL 1
        ↓
LEVEL 2
        ↓
OPPORTUNITY
        ↓
NOTIFICATION
        ↓
SCHEDULER / HEALTH / OBSERVABILITY
        ↓
TESTING / DEPLOYMENT

Поперечные требования:

SECURITY
ERROR HANDLING
CONFIGURATION
DATABASE
STATE MACHINES
CODE QUALITY
GIT WORKFLOW
DATA RETENTION

---

# 5. Project Requirements

## Primary document

`01_PROJECT_REQUIREMENTS.md`

Определяет:

- назначение Monik;
- scope;
- основные functional requirements;
- основные non-functional requirements;
- ключевые ограничения;
- Level 1;
- Level 2;
- financial rules;
- infrastructure requirements.

Это основной документ для определения что система должна делать.

---

# 6. Level 1 Scanner

## Documents

`02_LEVEL1_SCANNER.md`

`10_LEVEL_1_SCANNER.md`

## Правило

Эти два документа нельзя считать простым duplicate.

Они относятся к одной subsystem, но содержат различные архитектурные детали.

## `02_LEVEL1_SCANNER.md`

Особое внимание:

- scan lifecycle;
- Candidate model;
- Candidate fingerprint;
- deduplication;
- scan status;
- scan metadata;
- ranking;
- batching;
- backpressure;
- Level 1 → Level 2 handoff.

## `10_LEVEL_1_SCANNER.md`

Особое внимание:

- detailed Level 1 workflow;
- quote collection;
- provider combinations;
- opportunity discovery;
- scan filtering;
- output requirements;
- integration boundaries;
- scanner-specific invariants.

## Claude Code должен

читать оба документа перед изменением Level 1.

Нельзя считать `10` автоматически заменой `02`.

---

# 7. Level 2 Scanner

## Documents

`03_LEVEL2_SCANNER.md`

`11_LEVEL_2_SCANNER.md`

## Правило

Оба документа обязательны для Level 2.

## `03_LEVEL2_SCANNER.md`

Особое внимание:

- Level 2 confirmation architecture;
- Job lifecycle;
- fresh data;
- fees;
- gas;
- Profit Calculator integration;
- confirmation rules;
- immutable financial snapshot;
- auditability;
- notification failure isolation;
- recovery;
- critical invariants.

## `11_LEVEL_2_SCANNER.md`

Особое внимание:

- current BUY output;
- SELL verification;
- amount-specific verification;
- verification revision;
- detailed confirmation statuses;
- calculation snapshot;
- Level 2 execution details.

## Claude Code должен

использовать оба документа совместно.

Если требования различаются, нельзя выбирать один документ только по номеру.

---

# 8. Scheduler

## Documents

`04_SCHEDULER.md`

`14_SCHEDULER.md`

## Правило

Оба документа обязательны.

## `04_SCHEDULER.md`

Особое внимание:

- resource ownership;
- resource scope;
- event-driven scheduling;
- task dependencies;
- deduplication;
- deterministic queue ordering;
- Level 1/Level 2 concurrency;
- resource-aware scheduling;
- SAFE_STOP.

## `14_SCHEDULER.md`

Особое внимание:

- startup scheduling;
- interval scheduling;
- daily tasks;
- exact time;
- timezone;
- DST;
- manual trigger;
- task lifecycle;
- startup dependencies.

## Claude Code должен

рассматривать:

`04` = scheduling architecture and resource coordination

`14` = scheduling behavior and timing rules

Оба документа обязательны.

---

# 9. Resource Manager

## Documents

`05_RESOURCE_MANAGER.md`

`12_RESOURCE_MANAGER.md`

## `05_RESOURCE_MANAGER.md`

Особое внимание:

- resource ownership;
- resource scopes;
- leases;
- multi-resource acquisition;
- deadlock prevention;
- locking;
- concurrency;
- provider resource limits.

## `12_RESOURCE_MANAGER.md`

Особое внимание:

- async resource management;
- in-flight deduplication;
- batching;
- acquisition/release lifecycle;
- stale task cancellation;
- recovery;
- request coordination.

## Claude Code должен

использовать оба документа.

Особенно нельзя терять правила deadlock prevention, resource ownership и multi-resource locking.

---

# 10. Aggregator Adapters

## Document

`06_AGGREGATOR_ADAPTERS.md`

Определяет:

- provider adapter architecture;
- common provider interface;
- normalization;
- provider isolation;
- supported aggregator behavior;
- provider-specific error mapping;
- integration boundaries.

Связан с:

- `08_CAPABILITY_REGISTRY.md`;
- `20_CAPABILITY_REGISTRY.md`;
- `21_API_CONTRACTS.md`;
- `34_API_CONTRACTS.md`;
- `05_RESOURCE_MANAGER.md`;
- `12_RESOURCE_MANAGER.md`.

---

# 11. Fee System

## Documents

`07_FEE_SYSTEM.md`

`13_FEE_SYSTEM.md`

## Правило

Оба документа относятся к financial infrastructure.

## `07_FEE_SYSTEM.md`

Особое внимание:

- fee architecture;
- fee types;
- fee calculation;
- gas;
- conversion;
- fee freshness;
- batching;
- snapshots;
- provider/network/token dependencies.

## `13_FEE_SYSTEM.md`

Особое внимание:

- fee policies;
- fee responsibilities;
- dynamic fee behavior;
- route/network/token-dependent fee semantics;
- deterministic Fee Key;
- financial boundaries.

## Claude Code должен

читать оба документа перед изменением Fee/Gas logic.

---

# 12. Capability Registry

## Documents

`08_CAPABILITY_REGISTRY.md`

`20_CAPABILITY_REGISTRY.md`

## Правило

Оба документа обязательны.

Особое внимание:

- Aggregator Registry;
- Network Registry;
- Token Registry;
- Token identity;
- token metadata;
- capability states;
- capability snapshots;
- provider/network/token compatibility;
- capability discovery;
- capability history.

## Важное правило

Не создавать отдельный Token Registry document без explicit approval.

Token Registry уже является частью Capability Registry architecture.

---

# 13. Profit Calculator

## Document

`09_PROFIT_CALCULATOR.md`

Определяет:

- profit calculation;
- fees;
- gas;
- conversions;
- precision;
- rounding;
- thresholds;
- financial inputs;
- deterministic calculation;
- ProfitResult.

Profit Calculator не должен:

- выполнять HTTP;
- искать routes;
- обращаться к Telegram;
- самостоятельно читать database;
- самостоятельно получать provider data.

---

# 14. Notification System

## Document

`15_NOTIFICATION_SYSTEM.md`

Определяет:

- notification creation;
- destinations;
- Telegram integration;
- formatting;
- delivery;
- retry;
- deduplication;
- delivery state;
- notification lifecycle.

Notification System не должен изменять financial snapshot Opportunity.

---

# 15. Database

## Documents

`16_DATABASE.md`

`30_DATABASE_SCHEMA.md`

## Правило

Эти документы не являются duplicate.

## `16_DATABASE.md`

Определяет:

- database architecture;
- persistence boundaries;
- transaction architecture;
- repository interaction;
- database lifecycle;
- database safety.

## `30_DATABASE_SCHEMA.md`

Определяет:

- concrete schema;
- tables;
- fields;
- indexes;
- constraints;
- migrations;
- persistent relationships.

Оба документа обязательны.

---

# 16. Configuration

## Documents

`17_CONFIGURATION.md`

`33_CONFIGURATION.md`

## Правило

Оба документа необходимо учитывать.

## `17_CONFIGURATION.md`

Особое внимание:

- configuration architecture;
- environment;
- validation;
- normalization;
- secrets;
- scanner configuration;
- fixed routes;
- Level 1/Level 2 configuration;
- scan interval;
- profitability settings;
- fee settings.

## `33_CONFIGURATION.md`

Особое внимание:

- configuration contracts;
- concrete configuration behavior;
- validation;
- runtime configuration boundaries;
- component-specific configuration.

---

# 17. Error Handling

## Documents

`18_ERROR_HANDLING.md`

`29_ERROR_HANDLING.md`

## Правило

Оба документа относятся к одному subsystem.

Особое внимание:

### `18_ERROR_HANDLING.md`

- error severity;
- calculation errors;
- database failures;
- subsystem isolation;
- health/circuit recovery;
- normalized error behavior.

### `29_ERROR_HANDLING.md`

- error architecture;
- error categories;
- provider errors;
- retry behavior;
- propagation;
- operational handling.

Нельзя удалять один из документов без explicit consolidation.

---

# 18. Health Monitoring

## Document

`19_HEALTH_MONITORING.md`

Определяет:

- application health;
- subsystem health;
- provider health;
- database health;
- degraded state;
- unavailable state;
- recovery detection.

Связан с:

- Scheduler;
- Error Handling;
- Resource Manager;
- Observability;
- Deployment.

---

# 19. API Contracts

## Documents

`21_API_CONTRACTS.md`

`34_API_CONTRACTS.md`

## Правило

Оба документа обязательны до официальной consolidation.

## `21_API_CONTRACTS.md`

Особое внимание:

- Token Registry Contract;
- Quote Contract;
- Fee Contract;
- Gas Contract;
- Candidate Contract;
- Opportunity Contract;
- normalized provider contracts;
- contract testing.

## `34_API_CONTRACTS.md`

Особое внимание:

- expanded API boundaries;
- request/response contracts;
- service interfaces;
- validation;
- lifecycle contracts;
- integration contracts.

---

# 20. Security

## Documents

`22_SECURITY.md`

`32_SECURITY.md`

## Правило

Оба документа обязательны.

Особое внимание:

### `22_SECURITY.md`

- secret handling;
- secret references;
- credential isolation;
- Git safety;
- backup permissions;
- credential compromise;
- provider credentials.

### `32_SECURITY.md`

- application security;
- input validation;
- SSRF;
- SQL injection;
- path traversal;
- environment isolation;
- network security;
- runtime security.

---

# 21. Testing

## Document

`23_TESTING.md`

Определяет:

- testing architecture;
- unit tests;
- contract tests;
- integration tests;
- E2E;
- mocks/fakes;
- test isolation;
- deterministic testing;
- financial testing;
- state testing.

Не создавать отдельный `TESTING_STRATEGY.md` без explicit approval.

---

# 22. Deployment

## Document

`24_DEPLOYMENT.md`

Определяет:

- deployment;
- production configuration;
- startup;
- shutdown;
- migrations;
- secrets;
- environment;
- recovery;
- operational deployment requirements.

---

# 23. Project Structure

## Document

`25_PROJECT_STRUCTURE.md`

Определяет:

- directory structure;
- module boundaries;
- layer boundaries;
- naming;
- placement of components.

---

# 24. Code Quality

## Document

`26_CODE_QUALITY.md`

Определяет:

- formatting;
- linting;
- typing;
- code style;
- maintainability;
- complexity;
- review requirements.

---

# 25. Git Workflow

## Document

`27_GIT_WORKFLOW.md`

Определяет:

- branches;
- commits;
- pull requests;
- review;
- merge;
- repository safety;
- release workflow.

---

# 26. Observability

## Document

`28_OBSERVABILITY.md`

Определяет:

- structured logging;
- metrics;
- tracing;
- correlation IDs;
- operational diagnostics;
- secret redaction;
- monitoring integration.

---

# 27. Data Retention

## Document

`31_DATA_RETENTION.md`

Определяет:

- retention policies;
- cleanup;
- historical data;
- deletion;
- database growth;
- operational storage lifecycle.

---

# 28. State Machines

## Document

`35_STATE_MACHINES.md`

Определяет lifecycle и valid transitions для critical entities.

Связан с:

- Level 1;
- Level 2;
- Opportunity;
- Notification;
- Scheduler;
- Health;
- Error Handling;
- Database.

Изменение state machine требует синхронного изменения implementation и tests.

---

# 29. Data Models

## Document

`36_DATA_MODELS.md`

Определяет canonical domain models.

Особое внимание:

- Token;
- Network;
- Provider;
- Quote;
- Route;
- Fee;
- Gas;
- Candidate;
- Job;
- Opportunity;
- Notification;
- Capability;
- Health.

Domain models являются canonical representation.

---

# 30. System Workflows

## Document

`37_SYSTEM_WORKFLOWS.md`

Определяет cross-component workflows.

Особое внимание:

Level 1
→ Candidate
→ Level 2
→ Financial Validation
→ Opportunity
→ Notification

Также:

- failure workflows;
- retry workflows;
- recovery;
- restart;
- cancellation;
- degraded operation.

---

# 31. Interfaces

## Document

`38_INTERFACES.md`

Определяет application/domain/infrastructure interfaces.

Особое внимание:

- scanner interfaces;
- provider interfaces;
- repository interfaces;
- notification interfaces;
- fee interfaces;
- resource interfaces;
- scheduler interfaces;
- health interfaces.

Interfaces должны согласовываться с API Contracts.

---

# 32. Implementation Plan

## Document

`39_IMPLEMENTATION_PLAN.md`

Определяет порядок реализации:

foundation
→ configuration
→ models
→ database
→ repositories
→ registries
→ error handling
→ resource manager
→ adapters
→ fees/gas
→ profit calculator
→ Level 1
→ Level 2
→ opportunity
→ notifications
→ scheduler
→ health
→ observability
→ integration
→ recovery
→ security
→ deployment

Claude Code должен использовать Implementation Plan как roadmap, но не как замену subsystem architecture documents.

---

# 33. Acceptance Criteria

## Document

`40_ACCEPTANCE_CRITERIA.md`

Определяет объективные условия готовности.

Особое внимание:

- architecture compliance;
- financial correctness;
- Level 1;
- Level 2;
- Opportunity;
- notifications;
- scheduler;
- recovery;
- security;
- testing;
- production readiness.

Implementation не считается complete только потому, что application запускается.

---

# 34. Development Rules

## Document

`41_DEVELOPMENT_RULES.md`

Определяет обязательные правила изменения кода.

Особое внимание:

- no architecture invention;
- no scope expansion;
- minimal change;
- no duplicate sources of truth;
- resource boundaries;
- database boundaries;
- financial safety;
- state machine safety;
- testing requirements;
- stop conditions for Claude Code.

---

# 35. Architecture Map

## Document

`42_ARCHITECTURE_MAP.md`

Этот документ является navigation/index document.

Он не должен содержать новую business logic.

Его задача:

- показать связи между документами;
- предотвращать случайное удаление документов;
- объяснять дубли;
- указывать обязательные document combinations;
- направлять Claude Code к нужным документам.

---

# 36. Duplicate Document Policy

Следующие пары относятся к одной subsystem:

02 ↔ 10    Level 1 Scanner
03 ↔ 11    Level 2 Scanner
04 ↔ 14    Scheduler
05 ↔ 12    Resource Manager
07 ↔ 13    Fee System
08 ↔ 20    Capability Registry
17 ↔ 33    Configuration
18 ↔ 29    Error Handling
21 ↔ 34    API Contracts
22 ↔ 32    Security

Эти документы нельзя считать простыми копиями.

До официальной consolidation:

**оба документа считаются частью architecture baseline.**

---

# 37. No Automatic Deletion

Claude Code не должен удалять один из duplicate documents только потому, что:

- номер меньше;
- номер больше;
- документ создан раньше;
- название похоже;
- один документ выглядит короче;
- один документ выглядит более новым.

Удаление architecture document требует explicit approval.

---

# 38. No Automatic Consolidation

Claude Code не должен самостоятельно объединять duplicate documents.

Consolidation требует:

1. сравнения требований;
2. выявления уникальных requirements;
3. проверки конфликтов;
4. определения authoritative wording;
5. обновления references;
6. удаления duplicate только после approval.

---

# 39. No New Documents for Existing Responsibilities

Не создавать отдельный document, если его responsibility уже покрывается существующими documents.

Особенно не создавать без approval:

- Token Registry document;
- Network Registry document;
- Provider Registry document;
- Gas System document;
- Route System document;
- Testing Strategy document.

---

# 40. Cross-Document Dependencies

Критические связи:

01 PROJECT REQUIREMENTS
    ↓
02 / 10 LEVEL 1
    ↓
03 / 11 LEVEL 2

06 AGGREGATOR ADAPTERS
    ↓
08 / 20 CAPABILITY REGISTRY
    ↓
02 / 10 LEVEL 1

05 / 12 RESOURCE MANAGER
    ↓
06 AGGREGATOR ADAPTERS
    ↓
02 / 10 LEVEL 1
    ↓
03 / 11 LEVEL 2

07 / 13 FEE SYSTEM
    ↓
09 PROFIT CALCULATOR
    ↓
03 / 11 LEVEL 2

16 DATABASE
    ↓
30 DATABASE SCHEMA
    ↓
REPOSITORIES / STATE

17 / 33 CONFIGURATION
    ↓
ALL CONFIGURED SERVICES

35 STATE MACHINES
    ↓
LEVEL 1 / LEVEL 2 / OPPORTUNITY / NOTIFICATION / SCHEDULER

36 DATA MODELS
    ↓
ALL DOMAIN CONTRACTS

38 INTERFACES
    ↓
APPLICATION / INFRASTRUCTURE

21 / 34 API CONTRACTS
    ↓
38 INTERFACES
    ↓
IMPLEMENTATION

37 SYSTEM WORKFLOWS
    ↓
INTEGRATION

23 TESTING
    ↓
40 ACCEPTANCE CRITERIA

39 IMPLEMENTATION PLAN
    ↓
IMPLEMENTATION ORDER

41 DEVELOPMENT RULES
    ↓
ALL CODE CHANGES

---

# 41. Reading Order for Claude Code

Перед началом implementation рекомендуется читать документы в следующем порядке:

1. `CLAUDE.md`
2. `README.md`
3. `01_PROJECT_REQUIREMENTS.md`
4. `42_ARCHITECTURE_MAP.md`
5. `36_DATA_MODELS.md`
6. `38_INTERFACES.md`
7. `21_API_CONTRACTS.md`
8. `34_API_CONTRACTS.md`
9. `35_STATE_MACHINES.md`
10. `37_SYSTEM_WORKFLOWS.md`
11. subsystem-specific documents
12. `39_IMPLEMENTATION_PLAN.md`
13. `40_ACCEPTANCE_CRITERIA.md`
14. `41_DEVELOPMENT_RULES.md`

---

# 42. Subsystem Reading Rules

## Level 1

Read:

01
02
10
36
38
21
34
05
12
08
20
09
23
35
37

## Level 2

Read:

01
03
11
36
38
21
34
05
12
07
13
09
35
37
23

## Scheduler

Read:

04
14
05
12
17
33
19
28
35
37

## Resource Manager

Read:

05
12
18
29
28
23
38

## Aggregator Adapters

Read:

06
08
20
21
34
05
12
18
29
36
38

## Fee/Gas

Read:

07
13
09
17
33
21
34
36
23

## Database

Read:

16
30
31
35
36
38
23
24

## Notifications

Read:

15
35
37
38
21
34
18
29
23

## Security-sensitive changes

Read:

22
32
17
33
24
26
27
28
41

---

# 43. Conflict Resolution

Если два documents содержат потенциально conflicting requirements:

### Step 1

Определить, действительно ли это conflict.

Разные детали не являются автоматически conflict.

### Step 2

Проверить, является ли одно правило:

- уточнением;
- дополнением;
- implementation detail;
- operational requirement.

### Step 3

Если conflict остаётся:

**остановить implementation.**

### Step 4

Запросить explicit architectural decision.

### Step 5

После принятия решения обновить affected documents только с explicit approval.

---

# 44. Financial Conflict Rule

Любой conflict, который может изменить:

- amount;
- output;
- fee;
- gas;
- conversion;
- profit;
- threshold;
- route;

считается critical.

Claude Code не должен самостоятельно разрешать такой conflict.

---

# 45. State Conflict Rule

Любой conflict, который может изменить:

- state;
- transition;
- retry;
- expiration;
- terminal state;
- recovery;

считается critical.

Claude Code не должен самостоятельно разрешать такой conflict.

---

# 46. Security Conflict Rule

Любой conflict, который может ослабить:

- secret protection;
- validation;
- SSRF protection;
- authentication;
- authorization;
- environment isolation;
- credential security;

должен разрешаться в пользу безопасного поведения до получения explicit decision.

---

# 47. Implementation Rule

Когда Claude Code начинает implementation конкретного subsystem, он должен:

1. определить все связанные документы через эту map;
2. прочитать их;
3. проверить interfaces;
4. проверить data models;
5. проверить state machine;
6. проверить API contracts;
7. проверить testing requirements;
8. проверить acceptance criteria;
9. только после этого изменять код.

---

# 48. Documentation Baseline

Все документы из:

`docs/architecture/`

считаются частью архитектурного baseline, пока явно не утверждено их удаление или замена.

---

# 49. Current Document Set

Текущий архитектурный набор:

01_PROJECT_REQUIREMENTS.md
02_LEVEL1_SCANNER.md
03_LEVEL2_SCANNER.md
04_SCHEDULER.md
05_RESOURCE_MANAGER.md
06_AGGREGATOR_ADAPTERS.md
07_FEE_SYSTEM.md
08_CAPABILITY_REGISTRY.md
09_PROFIT_CALCULATOR.md
10_LEVEL_1_SCANNER.md
11_LEVEL_2_SCANNER.md
12_RESOURCE_MANAGER.md
13_FEE_SYSTEM.md
14_SCHEDULER.md
15_NOTIFICATION_SYSTEM.md
16_DATABASE.md
17_CONFIGURATION.md
18_ERROR_HANDLING.md
19_HEALTH_MONITORING.md
20_CAPABILITY_REGISTRY.md
21_API_CONTRACTS.md
22_SECURITY.md
23_TESTING.md
24_DEPLOYMENT.md
25_PROJECT_STRUCTURE.md
26_CODE_QUALITY.md
27_GIT_WORKFLOW.md
28_OBSERVABILITY.md
29_ERROR_HANDLING.md
30_DATABASE_SCHEMA.md
31_DATA_RETENTION.md
32_SECURITY.md
33_CONFIGURATION.md
34_API_CONTRACTS.md
35_STATE_MACHINES.md
36_DATA_MODELS.md
37_SYSTEM_WORKFLOWS.md
38_INTERFACES.md
39_IMPLEMENTATION_PLAN.md
40_ACCEPTANCE_CRITERIA.md
41_DEVELOPMENT_RULES.md
42_ARCHITECTURE_MAP.md

---

# 50. Root-Level Documents

Помимо architecture documents, обязательными являются:

CLAUDE.md
README.md

`CLAUDE.md` содержит operational instructions для Claude Code.

`README.md` является entry point для проекта.

`docs/architecture/` является detailed architecture baseline.

---

# 51. What Claude Code Must Not Assume

Claude Code не должен предполагать:

- что больший номер автоматически означает replacement;
- что более новый commit автоматически отменяет старый document;
- что похожие filenames означают duplicate;
- что более короткий документ менее важен;
- что один document имеет право отменять другой без explicit rule.

---

# 52. What Claude Code Should Do

Claude Code должен:

- использовать эту карту для навигации;
- читать связанные documents;
- сохранять requirements;
- выявлять conflicts;
- останавливать implementation при unresolved critical ambiguity;
- не удалять architecture documents без approval;
- не создавать duplicate documentation.

---

# 53. Final Principle

Architecture documents Monik образуют не линейный список, а **связанную систему требований**.

Поэтому:

**номер документа ≠ приоритет документа**

и

**более поздний документ ≠ автоматическая замена более раннего документа**.

До официальной consolidation все существующие documents должны рассматриваться как совместный architectural baseline.

Главное правило для Claude Code:

**если документ существует и относится к текущему subsystem — его требования нельзя игнорировать без explicit architectural decision.**

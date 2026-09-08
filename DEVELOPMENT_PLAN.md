# MONIK 3.0 — DEVELOPMENT PLAN

> Рабочий документ разработки. Составлен на основе полного аудита репозитория,
> `CLAUDE.md` и всех 42 документов в `docs/architecture/`.
>
> **Этот файл — основной рабочий документ.** В последующих сессиях читать в порядке:
> 1. `git log` / `git status`
> 2. `DEVELOPMENT_STATUS.md`
> 3. `DEVELOPMENT_PLAN.md` (этот файл)
> 4. только те architecture documents, которые нужны текущему этапу (см. §4 «Карта чтения»).
>
> Полное перечитывание документации перед каждым этапом **запрещено** (экономия лимитов).
>
> Этот файл **не является** architecture document. Он не изменяет и не заменяет
> `docs/architecture/`. При конфликте приоритет: `CLAUDE.md` → `docs/architecture/` → этот план.

---

## 1. РЕЗУЛЬТАТ АУДИТА ТЕКУЩЕГО СОСТОЯНИЯ

### 1.1. Что есть в репозитории

Ветка: `claude/monik-implementation` (чистая, синхронизирована с origin).

| Файл / каталог | Состояние |
|---|---|
| `CLAUDE.md` | 55 разделов операционных правил. Источник истины №1. **Защищён CODEOWNERS.** |
| `README.md` | 27 разделов обзора системы. |
| `docs/architecture/*.md` | 42 документа, ~917 КБ. Архитектурный baseline. **Защищён CODEOWNERS. Изменять запрещено.** |
| `pyproject.toml` | hatchling, `requires-python >=3.12`, dev-deps: pytest 8, pytest-asyncio, ruff 0.9+, mypy 1.13+ (strict). `asyncio_mode=auto`, ruff line-length 100, mypy strict с исключением `tests/`. |
| `.gitignore` | Полный, покрывает `data/`, `logs/`, `.env`, `*.db`, кэши. |
| `.github/CODEOWNERS` | Защищает `CLAUDE.md` и `docs/architecture/`. |

### 1.2. Чего НЕТ (объём работы)

**Исходного кода в репозитории нет вообще — 0 строк Python.**

Отсутствуют полностью:
- пакет приложения (`monik/` или `src/monik/`), `app/`, `domain/`, `services/`,
  `infrastructure/`, `repositories/`, `config/`;
- `tests/` (ни одного теста);
- ни одного из четырёх Aggregator Adapters;
- Resource Manager, Scheduler, Fee System, Profit Calculator, Level 1, Level 2,
  Capability Registry, Token Registry, Notification System, Health Monitoring;
- SQLite схема, migrations, repositories;
- configuration loader, `config/config.example.yaml`;
- CI workflow (`.github/workflows/`);
- runtime-каталоги `data/`, `logs/`, `scripts/`.

### 1.3. Вывод

Проект находится в состоянии **«полная архитектура + нулевая реализация»**.
Дорабатывать нечего — всё создаётся с нуля, строго по утверждённой архитектуре.
Правило CLAUDE.md §51 («не удалять рабочую функциональность») тривиально выполняется:
удалять нечего.

### 1.4. Проверка среды (выполнена фактически)

| Проверка | Результат |
|---|---|
| Python 3.12 | ✅ `/usr/bin/python3.12` (3.12.3), плюс `uv`-managed 3.12.11 |
| `uv`, `git`, `pip3` | ✅ доступны |
| PyPI (`pypi.org`, `files.pythonhosted.org`) | ✅ доступен; установка `httpx/pydantic/pydantic-settings/PyYAML/aiosqlite/pytest/pytest-asyncio/ruff/mypy` проверена и **прошла успешно** (нужен `UV_HTTP_TIMEOUT=180`, при коротком таймауте бывают обрывы) |
| GitHub | ✅ доступен |
| `api.1inch.dev`, `api.0x.org`, `api.uniswap.org`, `api.telegram.org` | ❌ **403 от egress-proxy — заблокированы** |
| `portal.1inch.dev`, `docs.uniswap.org`, `docs.velora.xyz`, `developers.paraswap.network` | ❌ **заблокированы** (и для `curl`, и для `WebFetch`) |
| `WebSearch` | ✅ работает (возвращает вторичные источники, не официальные страницы) |
| Provider API keys / Telegram bot token в окружении | ❌ отсутствуют |

**Следствие (критично, см. §8 Р-1):** в этой среде **невозможно** выполнить требование
`CLAUDE.md §9` / `06_AGGREGATOR_ADAPTERS §54,§62,§64` — проверку production Adapters
против реальных официальных API. Адаптеры будут реализованы против документированных
контрактов, собранных через `WebSearch`, и **явно помечены как непроверенные вживую**.

---

## 2. АРХИТЕКТУРНЫЕ ВЫВОДЫ, ЗАФИКСИРОВАННЫЕ ПРИ АУДИТЕ

Эти выводы используются при разработке, чтобы не перечитывать документы.

### 2.1. Доменная модель и терминология

- Canonical модели — `36_DATA_MODELS.md`. Domain не зависит от SQLite/HTTP/Telegram/env.
- `Network`, `Token` (identity = `network_id + normalized_address`, decimals явно),
  `TokenAmount`, `Provider`, `Route` + `RouteStep` + `route_fingerprint`, `Quote`,
  `Fee`, `Gas`, `ProfitCalculationInput`, `ProfitResult`,
  **`Opportunity`** (сущность Level 1, `#V`), **`Level2Job`** (`#K`),
  `Candidate` (промежуточный внутренний результат Level 1 до прохождения проверок),
  `ConfirmationResult`, `Notification`, `Scan`, `ResourceRequest/Result`,
  `SchedulerTask`, `Capability`, `HealthState`, `Error`.
- Финансы: `int` для raw base units, `Decimal` для денег/процентов. `float` запрещён везде.
- Все timestamps — timezone-aware UTC.

### 2.2. Потоки

```
Scheduler → Level 1 scan
  → per token: BUY_STARTED → BUY_RESULT_RECEIVED → BUY_COMPLETE → MAX_BUY_READY
  → SELL_QUEUED → SELL_RUNNING → SELL_COMPLETE → EVALUATION_READY
  → Opportunity(#V, CREATED) + Level2Job(#K)  [атомарно]
  → Level 2: fresh BUY quote (тот же route) → SELL на ТЕКУЩЕМ BUY output
             → fresh fees + gas → ProfitCalculator → per-amount status
  → Opportunity → CONFIRMED (immutable financial snapshot) → persist → Notification → Telegram
```

- SELL одного токена **не ждёт** BUY других токенов (CLAUDE.md §16, `04_SCHEDULER §15,16`).
- SELL запускается только когда MAX BUY окончательно определён (`04 §18,20`).

### 2.3. Жёсткие инварианты (нарушение = дефект)

1. Level 2 проверяет **тот же route**; замена route запрещена; невозможность
   воспроизвести → `ROUTE_UNAVAILABLE` (≠ `UNPROFITABLE`).
2. Все amounts одной Opportunity используют **один route snapshot**, но каждый
   amount получает собственный financial result.
3. Level 2 SELL считается от **текущего** BUY output, а не от Level 1.
4. UNKNOWN fee / UNKNOWN gas / отсутствующая conversion **никогда не 0**;
   при таком UNKNOWN подтверждение не выдаётся (`09 §16,27`).
5. Двойной учёт запрещён: у каждого cost есть `included_in_quote ∈ {yes,no,unknown}`.
6. Все внешние запросы — только через Resource Manager. Никакого прямого HTTP.
7. Вся persistence — только через Repository. Никакого raw SQL в services.
8. Транзакция БД **никогда** не удерживается во время внешнего запроса.
9. Opportunity сохраняется **до** начала notification delivery.
10. Notification никогда не пересчитывает profit и не меняет snapshot.
11. `UNKNOWN capability ≠ SUPPORTED`. Circuit Breaker **не меняет** Capability Registry.
12. Terminal states неизменяемы; `RUNNING` после краха ≠ успех.
13. Секреты не попадают в git, логи, БД, тесты, сообщения об ошибках.

### 2.4. Числовые дефолты (все configurable)

| Параметр | Default | Источник |
|---|---|---|
| Level 1 scan interval | 300 с (5 мин) | `02 §64`, `17 §33` |
| Level 1 overlap policy | SKIP | `02 §65` |
| Threshold | 1.00 % **net ROI**, сравнение `>=` (граница проходит) | `09 §24,26`, `10 §48,49`, `11 §43,44` |
| Token universe | Top 30 | `01 §7`, `10 §5` |
| `level2.max_parallel` | 20 | CLAUDE.md §18, `04 §21` |
| Retry `max_attempts` | 3, exponential backoff + jitter, honor `Retry-After` | CLAUDE.md §32, `12 §24-27` |
| Circuit Breaker | CLOSED / OPEN / HALF_OPEN | CLAUDE.md §33, `12 §31-35` |
| Maintenance | startup + daily (`interval_days`, `time`, `timezone`) | CLAUDE.md §22, `14 §4-10` |
| Приоритеты | Level 2 > Level 1 (готовый SELL > незавершённый BUY) > Maintenance | CLAUDE.md §15, `05 §16-20` |

### 2.5. Состояния (из `35_STATE_MACHINES.md`)

- `Level2Job`: QUEUED → RUNNING → {CONFIRMED, REJECTED, FAILED, EXPIRED, CANCELLED};
  requeue `FAILED → QUEUED` только через explicit recovery-операцию; expiration > retry.
- `Opportunity` (единый lifecycle, решение D-1):
  CREATED → VERIFYING → {CONFIRMED, PARTIAL, UNPROFITABLE, ROUTE_UNAVAILABLE, EXPIRED,
  FAILED, CANCELLED}; далее {CONFIRMED, PARTIAL} → {NOTIFIED, NOTIFIED_PARTIAL,
  NOTIFIED_FAILED}. Статусы `11 §47` — verification-часть, статусы `35 §59` / `30 §27` —
  notification-часть одного и того же жизненного цикла.
- Per-amount статусы (`11 §48`): VERIFIED_PROFITABLE / VERIFIED_UNPROFITABLE / UNKNOWN /
  FAILED / EXPIRED / ROUTE_UNAVAILABLE → отображаются на CONFIRMED / UNCONFIRMED /
  PARTIAL (CLAUDE.md §26).
- `Candidate` — **не** persistent сущность: промежуточный value object внутри Level 1
  (сопряжённая BUY/SELL комбинация до применения threshold и валидации).
- `Notification`: QUEUED → SENDING → {SENT, RETRY_WAIT, FAILED, CANCELLED}; RETRY_WAIT → SENDING.
- `SchedulerTaskExecution`: SCHEDULED → RUNNING → {SUCCESS, FAILED, SKIPPED, CANCELLED}.
- `ProviderHealth`: UNKNOWN / HEALTHY / DEGRADED / UNAVAILABLE / RECOVERING (+ гистерезис).
- `ApplicationHealth`: STARTING / HEALTHY / DEGRADED / UNAVAILABLE / STOPPING.

### 2.6. Confirmation (CLAUDE.md §26, §27)

- Статусы суммы: `CONFIRMED` / `UNCONFIRMED` / `PARTIAL`. `PARTIAL` ≠ `CONFIRMED`.
- `confirmation_rate = CONFIRMED / (CONFIRMED + UNCONFIRMED) × 100`; `PARTIAL` исключён;
  при отсутствии CONFIRMED и UNCONFIRMED → `N/A`.

### 2.7. Telegram (CLAUDE.md §35–38)

- В каждом Opportunity notification: Level 2 ID (`#K….`) сверху + кнопка `об`.
- Кнопка `об` **не делает новый API request** → все данные для неё берутся из
  сохранённого snapshot в SQLite.
- Команды: `/details K1234`, `/level2`, `/status`, `/stats`.
- Порядок отправки — строго `created_at` + внутренний sequence number; сортировка по
  profit/priority/amount/aggregator запрещена.
- Notification modes `A` / `B` — влияют **только** на правила отправки, не на алгоритмы.

### 2.8. Структура проекта (из `25_PROJECT_STRUCTURE.md`)

```
monik/
├── app/                     # entrypoint, wiring, startup/shutdown, supervisor
├── config/                  # схемы + config.example.yaml (без секретов)
├── domain/
│   ├── models/  enums/  value_objects/  errors/
├── services/
│   ├── level1/  level2/  opportunity/  calculator/  fees/  gas/
│   ├── resources/  scheduler/  notifications/  registries/  health/  observability/
├── repositories/            # интерфейсы + SQLite реализации
├── infrastructure/
│   ├── http/  db/  telegram/
│   └── providers/{oneinch,zero_x,velora,uniswap}/
├── tests/{unit,component,contract,integration,architecture,security,e2e}/
├── scripts/    data/    logs/    docs/
```

Направление зависимостей: `app → services → domain`; infrastructure/repositories
подключаются через интерфейсы. Circular imports запрещены. Проверяется
architecture tests (`25 §51`, `23 §53-57`).

---

## 3. ТЕХНОЛОГИЧЕСКИЕ РЕШЕНИЯ

Выбраны по правилу CLAUDE.md §5/§54 — «простейшее надёжное решение, совместимое с архитектурой».

| Область | Решение | Обоснование |
|---|---|---|
| Python | 3.12 | зафиксировано в `pyproject.toml` |
| Async | `asyncio` (stdlib) | Resource Manager, scanners, scheduler — все async |
| HTTP | `httpx` (async) | только внутри `infrastructure/http`, TLS verify, timeouts, size limits |
| Валидация моделей / конфига | `pydantic` v2 | strict types, `Decimal`, frozen models для snapshot |
| Конфиг-файл | YAML (`PyYAML`) + env-overrides | `17 §72-75` даёт примеры в YAML |
| Секреты | только env (`{env: "MONIK_..."}` refs), `.env` вне git | `17 §5,46`, CLAUDE.md §49 |
| SQLite | `aiosqlite`, WAL, `foreign_keys=ON`, busy_timeout | `30 §21,79,80` |
| Migrations | собственный простой раннер + `schema_migrations` | `30 §13-19`; без внешнего ORM (нет требования) |
| ORM | **нет** — raw SQL строго внутри `repositories/sqlite/*` | `16 §12-13`, `25 §63` |
| Telegram | прямой HTTP через `infrastructure/telegram` + Resource Manager | `25 §65` запрещает SDK в business logic |
| Логи | stdlib `logging` + собственный JSON-formatter + redaction filter | `28`, `48` CLAUDE.md |
| Метрики | in-process registry (counter/gauge/histogram), экспорт в `/status` и логи | `38 §88` |
| Тесты | `pytest` + `pytest-asyncio`, fake clock, fake HTTP transport, tmp SQLite | `23` |
| Lint/format/types | `ruff` + `ruff format` + `mypy --strict` | `26`, `pyproject.toml` |

**Новых зависимостей сверх перечисленных не добавлять без необходимости.**

---

## 4. КАРТА ЧТЕНИЯ ДОКУМЕНТАЦИИ ПО ЭТАПАМ

Чтобы не перечитывать всё. Основано на `42_ARCHITECTURE_MAP §42`.

| Этап | Читать перед началом (если нужно уточнение) |
|---|---|
| S0 Foundation | `25`, `26`, `27` |
| S1 Domain models | `36`, `21`, `34`, `35` |
| S2 Errors/Clock/Logging | `18`, `29`, `28` |
| S3 Configuration | `17`, `33`, `22`, `32` |
| S4 Database | `16`, `30`, `31` |
| S5 Repositories | `30`, `38`, `35` |
| S6 Registries | `08`, `20`, `36` |
| S7 HTTP | `38`, `32`, `06` |
| S8 Resource Manager | `05`, `12`, `18`, `29` |
| S9 Adapters | `06`, `21`, `34`, `08`, `20` |
| S10 Fees/Gas | `07`, `13`, `09` |
| S11 Profit Calculator | `09` |
| S12 Level 1 | `02`, `10`, `04` |
| S13 Level 2 | `03`, `11`, `04` |
| S14 Opportunity | `36`, `35`, `30` |
| S15/S16 Notifications/Telegram | `15`, CLAUDE.md §35-38 |
| S17 Scheduler | `04`, `14` |
| S18 Health/Supervisor | `19`, CLAUDE.md §34 |
| S19 Observability | `28` |
| S20 App wiring/Recovery | `24`, `37`, CLAUDE.md §30 |
| S21-S24 Тестирование | `23`, `40`, `31` |
| S25 Deployment/Отчёт | `24`, `40`, CLAUDE.md §53 |

---

## 5. ЭТАПЫ РАЗРАБОТКИ

Порядок соответствует `39_IMPLEMENTATION_PLAN §3` (снизу вверх по dependency graph).
Каждый этап **самодостаточен**: реализация → интеграция → тесты → исправление →
обновление `DEVELOPMENT_STATUS.md` → **git commit** → следующий этап.

Обозначения: **DoD** = Definition of Done (критерий завершения этапа).

---

### S0 — Project Foundation
**Зависимости:** нет.
**Реализовать:**
- каталоги пакета `monik/` со всеми слоями (`app`, `config`, `domain`, `services`,
  `repositories`, `infrastructure`), `tests/` с 7 подкаталогами, `scripts/`,
  `data/.gitkeep`, `logs/.gitkeep`;
- `pyproject.toml`: добавить runtime-зависимости (`httpx`, `pydantic`,
  `pydantic-settings`, `PyYAML`, `aiosqlite`), `[tool.hatch.build]` targets,
  `[project.scripts] monik = "monik.app.main:run"`;
- `Makefile` / `scripts/dev.sh`: `install`, `lint`, `format`, `typecheck`, `test`, `ci`;
- `.github/workflows/ci.yml`: ruff → ruff format --check → mypy → pytest (fast tier);
- `conftest.py` с базовыми fixtures.

**Тесты:** smoke-тест импорта пакета; тест, что `pytest` собирается.
**DoD:** `make ci` проходит локально на пустом проекте; CI-файл валиден.
**Commit:** `chore: bootstrap project structure, tooling and CI`

---

### S1 — Domain: enums, value objects, models
**Зависимости:** S0.
**Реализовать (`monik/domain/`):**
- `enums/`: `ProviderId`, `OperationType(BUY|SELL)`, `RoutingMode`, `QuoteStatus`,
  `FeeType`, `FeeStatus`, `CalculationStatus`, `OpportunityStatus`, `JobStatus`,
  `OpportunityStatus`, `AmountConfirmationStatus`, `NotificationStatus`,
  `CapabilityStatus`, `HealthStatus`, `ProviderHealthStatus`, `ErrorCategory`,
  `ErrorSeverity`, `ScanStatus`, `TaskExecutionStatus`, `ResourceResultStatus`,
  `Priority`, `NotificationMode(A|B)`. Значения — стабильные строки (`36 §76`).
- `value_objects/`: `NetworkId`, `TokenAddress` (нормализация lowercase + checksum-safe),
  `TokenAmount` (raw `int` + `decimals` → `Decimal`), `Percentage`, `Money`,
  `RouteFingerprint`, `OpportunityFingerprint`, `CorrelationId`, `VId`/`KId` (форматы
  `#V1234` / `#K1234`).
- `models/`: все canonical модели из §2.1, frozen там, где требуется immutability
  (`Quote`, `Opportunity`, `ProfitResult`, `Route`, fee/gas snapshots).
- `models/ids.py`: генерация и парсинг V/K-идентификаторов; отдельные пространства (CLAUDE.md §20).

**Тесты (`tests/unit/domain/`):** валидация required полей; identity токена
(`network+address`, symbol ≠ identity); `TokenAmount` конверсии без потери точности;
детерминизм fingerprint (независимость от порядка полей/ключей JSON);
запрет `float` в финансовых полях; immutability frozen-моделей; стабильность enum values;
корректность форматов `#V`/`#K`.
**DoD:** 100 % покрытие валидации моделей; mypy strict чист.
**Commit:** `feat: add canonical domain models, enums and value objects`

---

### S2 — Errors, Clock, базовое логирование
**Зависимости:** S1.
**Реализовать:**
- `domain/errors/`: `MonikError` + иерархия по категориям
  (`ConfigurationError`, `ValidationError`, `NetworkError`, `TimeoutError`,
  `RateLimitError`, `AuthenticationError`, `ProviderError`, `DatabaseError`,
  `ResourceError`, `CalculationError`, `InternalError`, `CancellationError`);
  поля: `code`, `category`, `severity`, `retryable`, `subsystem`, `operation`,
  `timestamp`, `correlation_id`, `provider_code`, `http_status`, `retry_after`.
- Классификация retryable / non-retryable / conditionally-retryable (`18 §33-36`).
- `services/observability/clock.py`: `Clock` protocol + `SystemClock` + `FakeClock`.
- `services/observability/logging.py`: structured JSON logger, correlation context,
  **redaction filter** (bot token, API keys, `Authorization`, приватные ключи).

**Тесты:** нормализация исключений в `MonikError`; классификация retryability;
FakeClock детерминизм; **redaction-тест: секрет никогда не появляется в выводе логгера**.
**DoD:** ни один тестовый лог не содержит секрет.
**Commit:** `feat: add normalized error model, clock abstraction and redacting structured logger`

---

### S3 — Configuration subsystem
**Зависимости:** S1, S2.
**Реализовать (`monik/config/`):**
- pydantic-схемы всех секций: `application`, `networks`, `providers`, `tokens`,
  `routes`, `scanner.level1`, `scanner.level2`, `profitability`, `fees`, `gas`,
  `resources`, `scheduler`, `notifications.telegram`, `database`, `logging`, `metrics`;
- loader: YAML → env overrides → defaults → validation → normalization →
  immutable `Configuration` + `config_version` (детерминированный fingerprint);
- разрешение секрет-ссылок `{env: "MONIK_..."}`; `SecretRef`, никогда не логируется;
- cross-field и cross-subsystem валидация (`17 §62-65`): enabled provider ↔ enabled
  network, tokens ↔ networks, routes ↔ tokens/providers, amounts ↔ token precision,
  ≥1 enabled network / provider / token / amount;
- валидация `HH:MM`, IANA timezone, Decimal-сумм, диапазонов, enum;
- diagnostics-представление с `[REDACTED]`;
- `config/config.example.yaml` (без секретов) + `.env.example`.

**Тесты (`tests/unit/config/`, `tests/security/`):** валидный конфиг; отсутствующие
обязательные поля; неверные типы/диапазоны/enum/время/timezone; Decimal без float;
env override и приоритет источников; cross-field конфликты; **редакция секретов
в diagnostics и в текстах ошибок**; reload с откатом к последней валидной конфигурации.
**DoD:** приложение не стартует при невалидном конфиге; ни одного hard-coded user setting.
**Commit:** `feat: implement configuration loading, validation and secret references`

---

### S4 — Database: соединение, схема, migrations, транзакции
**Зависимости:** S3.
**Реализовать (`monik/infrastructure/db/`):**
- connection manager (`aiosqlite`): WAL, `foreign_keys=ON`, busy timeout,
  ограниченный retry на `SQLITE_BUSY`, integrity check при старте;
- `TransactionManager` (begin/commit/rollback) + защита: транзакция не должна
  оборачивать внешний вызов (проверяется architecture-тестом);
- migration runner + таблица `schema_migrations`; миграции нумерованные, последовательные,
  атомарные; при ошибке миграции — старт прерывается;
- migration `0001_initial`: таблицы
  `schema_migrations`, `app_metadata`, `scans`,
  `opportunities`, `opportunity_amounts`,
  `level2_jobs`, `level2_attempts`, `level2_amount_results`,
  `notifications`, `notification_attempts`,
  `fee_snapshots`, `fee_records`, `gas_snapshots`, `capabilities`,
  `scheduler_tasks`, `scheduler_executions`, `state_transitions`;
  индексы и UNIQUE-ограничения по `30 §60-65`, включая
  `UNIQUE(opportunity_id, destination_id)` для notifications и индекс на
  `opportunities.fingerprint`.

**Тесты (`tests/integration/db/`):** создание БД с нуля; применение всех migrations;
идемпотентность повторного запуска; проверка наличия индексов/constraints/FK;
откат транзакции; поведение при busy; отказ при повреждённой БД; **тест, что тесты
никогда не используют production-путь БД**.
**DoD:** свежая БД создаётся и проходит integrity check; все constraints присутствуют.
**Commit:** `feat: add sqlite infrastructure, schema migrations and transaction manager`

---

### S5 — Repositories
**Зависимости:** S4.
**Реализовать:**
- интерфейсы (Protocol) в `repositories/interfaces/`, SQLite-реализации в
  `repositories/sqlite/`: `ScanRepository`, `OpportunityRepository`, `JobRepository`,
  `NotificationRepository`, `FeeRepository`,
  `GasRepository`, `CapabilityRepository`, `SchedulerRepository`,
  `StateTransitionRepository`;
- mapping domain ↔ database (raw amounts как TEXT/INTEGER, Decimal как TEXT —
  без float ни на одном участке);
- атомарная операция `create_opportunity_with_job()` — Opportunity + amount-контексты
  + Level2Job в одной транзакции (CLAUDE.md §29);
- запросы recovery: активные/зависшие jobs, pending notifications, expired opportunities.

**Тесты (`tests/integration/repositories/`):** CRUD каждого репозитория; фильтрация;
pagination; dedup по fingerprint; enforcement UNIQUE; rollback; сохранение точности
Decimal при round-trip; атомарность `opportunity+amounts+job`; recovery-запросы.
**DoD:** ни одного SQL вне `repositories/sqlite/`; architecture-тест это подтверждает.
**Commit:** `feat: implement repository layer over sqlite`

---

### S6 — Registries: Network, Token, Provider, Capability
**Зависимости:** S5.
**Реализовать (`services/registries/`):**
- `NetworkRegistry` (enabled networks, chain_id, native token);
- `TokenRegistry` — authoritative token metadata (symbol, address, decimals,
  network, enabled), нормализация адресов, Top-N выбор; **источник — configuration/
  seed-файл, не hard-code в коде**;
- `ProviderRegistry` — регистрация Adapter'ов;
- `CapabilityRegistry` — состояния `SUPPORTED/UNSUPPORTED/UNKNOWN/DEGRADED/
  UNAVAILABLE/STALE/CHECKING/FAILED`, freshness, persistence, failure/recovery
  thresholds, change detection; discovery **только на startup и по расписанию**
  (не перед каждым scan); `UNKNOWN ≠ SUPPORTED`; runtime-ошибки не переводят
  capability в UNSUPPORTED мгновенно; Circuit Breaker **не меняет** Registry.

**Тесты:** identity токена; нормализация адресов; фильтрация disabled;
capability lookup и freshness; STALE handling; пороги деградации/восстановления;
запрет мгновенного permanent disable; отсутствие сетевых вызовов при статических запросах.
**DoD:** Level 1 сможет отфильтровать заведомо неподдерживаемые комбинации без запросов.
**Commit:** `feat: add token, network, provider and capability registries`

---

### S7 — HTTP infrastructure
**Зависимости:** S2, S3.
**Реализовать (`infrastructure/http/`):**
- `HttpClient` protocol + `HttpxClient`: timeouts, TLS verification (нельзя отключать),
  лимит размера ответа, redirect policy, connection pooling, request ID,
  нормализация transport-ошибок в `MonikError`;
- **SSRF-защита**: allowlist хостов из configuration; запрет запросов по произвольным
  URL из ответов провайдеров (`06 §80`, `32`);
- `FakeHttpClient` для тестов (детерминированные ответы, инъекция ошибок/таймаутов).

**Тесты (`tests/unit/http/`, `tests/security/`):** timeout; 4xx/5xx/429;
превышение размера ответа; запрет redirect на неразрешённый host; SSRF-блокировка;
TLS verify включён; заголовок `Authorization` не попадает в логи.
**DoD:** ни один business-модуль не импортирует `httpx` (architecture-тест).
**Commit:** `feat: add controlled async http client with ssrf and tls safeguards`

---

### S8 — Resource Manager
**Зависимости:** S7.
**Реализовать (`services/resources/`):**
- resource identity/key (provider × network × operation, иерархические лимиты);
- состояния ресурса: `AVAILABLE/BUSY/RATE_LIMITED/COOLDOWN/CIRCUIT_OPEN`;
- acquisition/lease с таймаутом lease и гарантированным release (никаких утечек локов);
- **priority queue**: Level 2 > Level 1 (готовый SELL > незавершённый BUY) > Maintenance;
  FIFO внутри приоритета; ordering по `(priority, created_at, sequence)`;
- concurrency limits (глобальный, per-provider, per-network) и **отдельно** rate limits
  (sliding window / token bucket) — это разные ограничения;
- retry: `max_attempts=3`, exponential backoff + jitter, `Retry-After` для 429,
  запрет бесконечных retry и retry-storm;
- circuit breaker CLOSED/OPEN/HALF_OPEN с восстановлением;
- in-flight deduplication (одинаковые одновременные запросы объединяются — важно для
  fee/capability/metadata), при этом семантика запроса не меняется;
- batch support + корректный rate-limit accounting батча (`05 §55-56`, `12 §47-48`);
- backpressure, queue limits, queue expiration, отмена устаревших задач;
- multi-resource acquisition с детерминированным порядком (deadlock prevention);
- cancellation; graceful shutdown; метрики (queue wait, execution latency, total).

**Тесты (`tests/unit/resources/`, `tests/component/`):** конкурентность; переполнение
очереди; таймаут; retry и backoff; jitter в границах; `Retry-After`; rate limit;
circuit breaker переходы и восстановление; приоритеты (L2 обгоняет L1);
запрет starvation; отмена; отсутствие утечки lease при исключении; дедупликация;
batch accounting; **тест: параллельные операции на разных ресурсах не блокируют друг друга**.
**DoD:** после этого этапа любой внешний запрос идёт только через RM.
**Commit:** `feat: implement resource manager with priorities, rate limits, retry and circuit breaker`

---

### S9 — Aggregator Adapters
**Зависимости:** S6, S7, S8.

#### S9.0 — Общий контракт + Fake adapter
- `AggregatorAdapter` protocol: `get_quote(request)`, `validate_fixed_route(...)`,
  `discover_capabilities()`, `discover_fees()`, `health_check()`, lifecycle
  (`initialize/ready/degraded/shutdown`), `supported_networks`, `routing_modes`;
- нормализация: `Quote`, `Route`/`RouteStep`, `route_fingerprint`, fee extraction
  (`UNKNOWN`, не 0), gas extraction, error translation в категории
  `Temporary/Permanent/Data/Authentication/RateLimit/Unsupported`;
- **общий contract test suite**, который обязан пройти каждый adapter (`06 §59`);
- `FakeAdapter` (детерминированный, для integration/E2E) — явно помечен как test impl.
- **Commit:** `feat: add aggregator adapter contract and shared contract test suite`

#### S9.1 — 1inch, S9.2 — 0x, S9.3 — Velora (ParaSwap), S9.4 — Uniswap
Для каждого — отдельный подэтап и отдельный commit:
- endpoints/параметры/auth/network ids вынести в один `endpoints.py` внутри адаптера,
  чтобы правка при изменении API была локальной;
- request building, response parsing, validation (token/network/amount mismatch → Data Error),
  route extraction + fingerprint, fee extraction, gas, price impact, slippage,
  fixed-route поддержка → иначе `FIXED_ROUTE_UNSUPPORTED`; несовпадение → `ROUTE_MISMATCH`;
- capability reporting; health check; **никакого прямого HTTP мимо RM**.
- **Uniswap:** сохранять различие routing modes (Classic vs UniswapX Dutch/Priority),
  не объединять их молча.
- Тесты: unit (парсинг, ошибки, malformed, отсутствующие поля, auth failure,
  unsupported network/token, rate limit) + общий contract suite.
- **Commits:** `feat: implement 1inch adapter` … `feat: implement uniswap adapter`

**⚠ Ограничение (Р-1):** live-верификация невозможна в этой среде. Каждый adapter
получает в docstring и в финальном отчёте пометку
`API contract NOT verified against live endpoint`. Дополнительно создаётся
`scripts/verify_provider_api.py` — скрипт, который пользователь запускает
в среде с сетью и ключами, чтобы подтвердить контракт.

---

### S10 — Fee System, Gas System, Prices/Conversion
**Зависимости:** S8, S9.0.
**Реализовать (`services/fees/`, `services/gas/`, `services/prices/`) — см. решение D-4:**
- `FeeProvider` interface, `FeePolicy` per-provider (изолированно от Scanner —
  никаких `if aggregator == ...` вне policy);
- `FeeKey` (провайдер × сеть × операция × токен/route-контекст — без чрезмерного обобщения);
- статусы `KNOWN/UNKNOWN/UNSUPPORTED/EXPIRED/ERROR`; freshness + expiration;
- fee discovery: startup + scheduled; grouping/batching; дедупликация запросов;
- fee snapshots с версией и persistence; `included_in_quote` флаг;
- rebate как отдельный компонент (не отрицательная fee);
- `GasPriceProvider` protocol + реализации `RpcGasPriceProvider` (eth_gasPrice /
  eth_feeHistory, EIP-1559), `AdapterGasEstimateProvider` (gas estimate из quote),
  `StaticGasPriceProvider` (test impl);
- `GasEstimator`: gas_units × gas_price → стоимость в native token; freshness;
  **UNKNOWN gas ≠ 0**;
- `TokenPriceProvider` protocol + `AggregatorQuotePriceProvider`, `HttpPriceProvider`
  (CoinGecko/DeFiLlama, подключается конфигом), `StaticPriceProvider` (test impl);
- `ConversionService`: native gas token → базовая валюта расчёта (USDT/USD) с
  source/timestamp/pair/rate/precision, явным направлением и freshness-политикой;
  при stale/недоступности → `PARTIAL`/`UNKNOWN`;
- выбор реализаций только через configuration; все внешние вызовы — через Resource Manager.

**Тесты:** нормализация fee; UNKNOWN не превращается в 0; expired fee;
percentage vs fixed vs multi-leg; base выбирается по policy, не угадывается;
дедупликация одновременных fee-запросов; batching; refresh failure; rebate;
gas: EIP-1559 расчёт, gas из route estimate, отсутствие gas → UNKNOWN;
price provider: подстановка любой реализации без изменения Calculator;
conversion и stale conversion; `included_in_quote` предотвращает двойной учёт.
**DoD:** Level 1/Level 2 получают нормализованные fee/gas без provider-specific логики.
**Commit:** `feat: implement fee system, gas providers and price conversion`

---

### S11 — Profit Calculator
**Зависимости:** S1, S10.
**Реализовать (`services/calculator/`):**
- `ProfitCalculator.calculate(ProfitCalculationInput) -> ProfitResult`, чистая функция,
  без HTTP/БД/Telegram/Scheduler;
- формулы (`09 §9-14`):
  `gross_profit = final_output − input_amount`;
  `gross_roi = gross_profit / input_amount × 100`;
  `total_costs = total_fees + gas_cost + other_costs − rebates`;
  `net_profit = gross_profit − total_costs`; `net_roi = net_profit / input × 100`;
- статусы `COMPLETE / PARTIAL / INVALID / UNKNOWN`;
- threshold: метрика `net_roi`, сравнение `>=`; если неизвестный cost способен
  изменить результат относительно threshold — **threshold не считается пройденным**;
- предотвращение двойного учёта через `included_in_quote`;
- компонентный breakdown, `profit_formula_version = 1`, детерминизм, отсутствие
  «тихих исправлений»; округление только на presentation layer.

**Тесты (`tests/unit/calculator/`):** profitable / unprofitable / zero / negative;
граница threshold ровно 1.00 %; unknown fee; unknown gas; unknown conversion;
двойной учёт; rebate; multi-leg fees; точность и отсутствие float;
разные decimals токенов; несколько сумм без смешивания; **property-based тесты**
(рост costs не увеличивает net profit; детерминизм при одинаковом входе);
golden test cases (фиксированные входы → фиксированные выходы).
**DoD:** ни одной финансовой формулы вне этого модуля (architecture-тест по grep).
**Commit:** `feat: implement deterministic profit calculator with decimal arithmetic`

---

### S12 — Level 1 Scanner
**Зависимости:** S6, S8, S9, S10, S11.
**Реализовать (`services/level1/`):**
- `Level1Scanner.scan(scope) -> ScanResult`; scan_id, метаданные, статусы
  `RUNNING/COMPLETE/PARTIAL/FAILED/CANCELLED`;
- определение scope из configuration (networks × tokens × amounts × providers × routes);
- capability-фильтрация до отправки запросов (`UNKNOWN` может проверяться в runtime);
- **пер-токенный независимый цикл:** BUY quotes по всем провайдерам → определение
  `MAX BUY` (только после получения необходимого набора результатов) → немедленный
  запуск SELL для этого токена, **не дожидаясь других токенов**;
- SELL quotes по разрешённым provider pairs; сопряжение BUY/SELL по intermediate token,
  сети и amount context; round-trip `input == output token`;
- preliminary profitability через `ProfitCalculator`; preliminary threshold;
- `Opportunity` (status `CREATED`) с route snapshot (BUY route + SELL route +
  fingerprints), N amount-контекстов, `#V`-идентификатором, `detected_at`, `scan_id`,
  expiration; промежуточные `Candidate` value objects не персистятся;
- deterministic fingerprint + deduplication window; ranking при нехватке capacity;
- лимит opportunities за цикл, backpressure по Level 2 queue;
- **атомарное** создание `Opportunity` + amount-контекстов + `Level2Job` (`#K`) и немедленная передача;
- изоляция ошибок (token/provider/network), partial scan, cancellation, shutdown.

**Тесты (`tests/component/level1/`):** фильтрация по token/network/provider/capability;
несколько сумм; нормализация и валидация quote; freshness; invalid/zero output;
интеграция fee/gas; preliminary threshold; создание Opportunity; fingerprint;
дедупликация; expiration; backpressure; ranking; partial scan; таймаут провайдера;
rate limit; отмена; overlap SKIP; **тест «SELL токена A не ждёт BUY токена B»**;
**тест «Level 1 не отправляет Telegram»**; **тест «Level 1 не обходит RM»**;
**тест «один route на все amounts»**.
**Commit:** `feat: implement level 1 scanner with independent per-token buy/sell cycles`

---

### S13 — Level 2 Scanner
**Зависимости:** S12.
**Реализовать (`services/level2/`):**
- `Level2Scanner.confirm(job) -> ConfirmationResult`; state machine Job'а;
- проверка expiration Opportunity/Job **до** любых запросов; проверка capability;
- fresh BUY quote по **зафиксированному** route (fixed-route параметры адаптера);
- сравнение route fingerprint; несоответствие → `ROUTE_UNAVAILABLE` / `ROUTE_MISMATCH`,
  **без подбора альтернативы**;
- SELL на **текущем** BUY output (не на Level 1 значении);
- fresh fees + gas через Fee System; `ProfitCalculator` на каждую сумму отдельно;
- per-amount статусы `VERIFIED_PROFITABLE / VERIFIED_UNPROFITABLE / UNKNOWN /
  FAILED / EXPIRED / ROUTE_UNAVAILABLE` → маппинг на `CONFIRMED/UNCONFIRMED/PARTIAL`;
- итоговый статус job: CONFIRMED / REJECTED / FAILED / EXPIRED / CANCELLED;
- `verification_revision`, идемпотентность по `job_id`, дедупликация одинаковых
  активных workflows (объединение, а не запуск второго), `max_parallel = 20`;
- retry как новый attempt внутри существующего `#K` (не новый Job);
- полные snapshots: quote refs, fee snapshot, gas snapshot, calculation snapshot,
  формула-версия, threshold, причина решения — достаточно для восстановления «почему».

**Тесты (`tests/component/level2/`):** same-route verification; route mismatch;
fixed-route unsupported; несколько сумм; SELL от текущего BUY output;
fee update / unknown fee / unknown gas; threshold и его граница; expiration;
retry внутри K-ID; отмена; rate limit ≠ unprofitable; temporary vs permanent error;
идемпотентность; partial результаты; **тест «Level 2 никогда не меняет route»**;
**тест «UNKNOWN cost не даёт CONFIRMED»**.
**Commit:** `feat: implement level 2 scanner with fixed-route confirmation`

---

### S14 — Opportunity Service (confirmation snapshot)
**Зависимости:** S13.
**Реализовать (`services/opportunity/`):**
- перевод `Opportunity` в `CONFIRMED`/`PARTIAL` только после успешного Level 2 confirmation;
- фиксация immutable confirmation snapshot;
- immutable financial snapshot; попытка обычного изменения → ошибка;
- идемпотентность и защита от дублей (один подтверждённый Job → максимум одна Opportunity);
- persistence **до** постановки notification в очередь (в одной транзакции с
  созданием notification-записей, но **без** внешних вызовов внутри транзакции);
- переходы `CONFIRMED → NOTIFIED / NOTIFIED_PARTIAL / NOTIFIED_FAILED`;
- расчёт и хранение confirmation-статистики (для `confirmation_rate`).

**Тесты:** создание при успехе; отказ при неуспехе; immutability; идемпотентность;
отсутствие дублей при повторной доставке события; **тест «Opportunity сохранена
до начала delivery»**; переходы статусов.
**Commit:** `feat: add opportunity service with immutable financial snapshot`

---

### S15 — Notification System + Telegram (исходящие)
**Зависимости:** S14, S8.
**Реализовать (`services/notifications/`, `infrastructure/telegram/`):**
- `NotificationService.notify(opportunity, destination)`; очередь с ordering по
  `created_at` + sequence (**никакой сортировки по profit/priority/amount/aggregator**);
- fingerprint/идемпотентность `opportunity + destination`; UNIQUE в БД;
- state machine notification; retry с backoff и лимитом; permanent vs temporary ошибки;
- fan-out по нескольким destinations с изоляцией сбоев → `NOTIFIED_PARTIAL`;
- `MessageFormatter`: сеть, пара токенов, суммы, провайдеры BUY/SELL, route,
  fees, gas, profit, ROI, calculation version, **`#K` сверху**, precision из конфига;
  **никакого пересчёта**;
- inline-кнопка **`об`** в каждом Opportunity notification; данные для неё берутся
  из сохранённого snapshot — **без новых API-запросов**;
- notification modes `A` / `B` — только правила отправки;
- `TelegramNotificationAdapter` — HTTP через Resource Manager; обработка 429;
  сохранение `telegram_message_id`; recovery после краха во время SENDING.

**Тесты:** формат сообщения (snapshot-тесты); ordering; идемпотентность; дедупликация;
retry и лимит; permanent failure; partial fan-out; recovery «крах во время SENDING»;
**тест «notification не пересчитывает profit»**; **тест «кнопка `об` присутствует
в каждом opportunity-уведомлении»**; **тест «обработка нажатия `об` не делает
внешних API-запросов»**; тесты режимов A/B.
**Commit:** `feat: implement notification system with telegram delivery and 'об' button`

---

### S16 — Telegram commands (входящие)
**Зависимости:** S15.
**Реализовать:**
- long-polling `getUpdates` через Resource Manager (низкий приоритет, не блокирует Scanner);
- обработчики: `/details K1234`, `/level2`, `/status`, `/stats`;
- callback handler кнопки `об` → рендер сохранённого snapshot;
- все данные — из репозиториев; **ни один handler не инициирует provider-запрос**;
- `/stats` включает `confirmation_rate` по формуле CLAUDE.md §27 (с `N/A`).

**Тесты:** парсинг команд; неизвестный K-ID; `/level2` со списком активных job;
`/status` с health-снимком; `/stats` включая случай `N/A`;
**тест «Telegram не блокирует Scanner»** (обработчик медленный → scan не задерживается);
**тест «команды не вызывают provider API»**.
**Commit:** `feat: add telegram command handlers and 'об' callback`

---

### S17 — Scheduler
**Зависимости:** S12–S16.
**Реализовать (`services/scheduler/`):**
- режимы задач `STARTUP / DAILY / INTERVAL / MANUAL`; `interval_days`, `time`,
  timezone (IANA) + корректная обработка DST; расчёт `next_run`;
- задачи: Level 1 scan (interval 5 мин), fee refresh, capability refresh,
  gas refresh, notification retry, cleanup/retention, health check, maintenance;
- overlap policy (Level 1 → SKIP), missed schedule policy, manual trigger,
  дедупликация одинаковых запусков;
- execution records, состояния `SCHEDULED/RUNNING/SUCCESS/FAILED/SKIPPED/CANCELLED`;
- зависимости задач и startup ordering: Resource Manager → Registries →
  Fee System → Capability → Scanners;
- изоляция сбоя одной задачи; graceful shutdown; **никакой бизнес-логики внутри**.

**Тесты:** расчёт времени (в т.ч. переход DST); interval; daily в заданное время;
overlap SKIP; missed schedule; manual во время scheduled; отмена; таймаут ≠ retry;
изоляция сбоя задачи; порядок startup; отсутствие дублирующего startup после рестарта.
**Commit:** `feat: implement scheduler with startup, interval and daily tasks`

---

### S18 — Health Monitoring и Supervisor
**Зависимости:** S17.
**Реализовать (`services/health/`, `app/supervisor.py`):**
- `HealthMonitor`: состояния приложения и подсистем, provider health с
  failure/recovery thresholds и гистерезисом (защита от flapping);
- health не меняет business state; health ≠ capability; health ≠ profitability;
- Supervisor контролирует Level 1, Level 2, Resource Manager, Telegram, Maintenance,
  Scheduler; перезапуск некритического worker'а; при критическом сбое persistence →
  **SAFE_STOP** (CLAUDE.md §34);
- degraded mode: работа с доступными провайдерами.

**Тесты:** переходы health; гистерезис/flapping; изоляция провайдеров;
«все провайдеры недоступны» → DEGRADED/UNAVAILABLE по policy;
критический сбой БД → SAFE_STOP; восстановление worker'а; health не меняет данные.
**Commit:** `feat: add health monitoring and supervisor with safe stop`

---

### S19 — Observability
**Зависимости:** S18.
**Реализовать:** correlation IDs сквозь весь workflow (scan_id, V-ID, K-ID,
request_id, provider, resource, duration, error category); метрики Level 1/Level 2/
Resource Manager/Fee/Notification/Scheduler/DB; события state transitions;
проверка отсутствия секретов в любом выводе.
**Тесты:** наличие обязательных полей в логах; распространение correlation id;
корректность счётчиков; **security-regression: секреты не логируются ни на одном уровне**.
**Commit:** `feat: add structured observability, metrics and correlation context`

---

### S20 — Application wiring, startup, shutdown, recovery
**Зависимости:** S19.
**Реализовать (`app/`):** `main.py`, composition root (явный DI, без глобальных
mutable singletons), порядок запуска по CLAUDE.md §30:
configuration → SQLite → integrity → migrations → **recovery незавершённого состояния** →
adapters → Resource Manager → Scheduler → Telegram → workers.
Recovery: `RUNNING` Job → `INTERRUPTED`-путь (requeue/failed/expired по policy),
новый attempt начинает проверку заново, **старые quotes не считаются свежими**,
runtime-локи не восстанавливаются; pending notifications возобновляются без дублей;
graceful shutdown с таймаутом.
**Тесты:** полный старт на чистой БД; старт с существующей БД; recovery каждого
критического состояния; двойной старт не создаёт дублей; graceful shutdown.
**Commit:** `feat: wire application lifecycle with startup, recovery and graceful shutdown`

---

### S21 — Integration tests (сквозные сценарии)
**Зависимости:** S20.
Сценарии (`tests/integration/`, `tests/e2e/`) на `FakeAdapter` + tmp SQLite + FakeClock:
успешная opportunity end-to-end; неприбыльная opportunity; stale quote; missing fee;
missing gas; timeout провайдера; rate limit; retry; expiration; отмена;
route unavailable; partial confirmation; notification failure; несколько destinations.
**Commit:** `test: add end-to-end integration scenarios`

---

### S22 — Recovery / crash tests
Крах в контрольных точках (`39 §55`): после создания Opportunity; после создания Job;
во время выполнения Job; после сохранения confirmation snapshot; во время notification;
во время retry.
Проверка: нет дублей Opportunity/Job/Notification; `RUNNING` не становится успехом.
**Commit:** `test: add crash and recovery scenarios`

---

### S23 — Architecture + Security tests
Architecture: направление зависимостей; запрещённые импорты (`httpx`/`sqlite3`/
`os.environ`/telegram вне разрешённых слоёв); изоляция провайдеров; отсутствие
финансовых формул вне Calculator; отсутствие `if aggregator ==` в core; отсутствие
`float` в финансовых путях; отсутствие циклических импортов; транзакция не оборачивает
внешний вызов.
Security: редакция секретов; SSRF; path traversal; параметризованный SQL;
изоляция test/production БД; отсутствие секретов в репозитории.
**Commit:** `test: add architecture boundary and security regression tests`

---

### S24 — Performance / нагрузочная проверка (лёгкая)
Пропускная способность Level 1; поведение очереди Level 2 при переполнении;
соблюдение лимитов RM под нагрузкой; отсутствие неограниченного роста БД и памяти;
retention/cleanup работают.
**Commit:** `test: add performance and resource-limit checks`

---

### S25 — Deployment prep, документация, финальный отчёт
`scripts/` (init db, run, backup, restore, verify_provider_api);
`config/config.example.yaml` финализирован; README-раздел про запуск/конфиг/тесты
(**не изменяя** `docs/architecture/`); прогон всего test suite; проверка
`40_ACCEPTANCE_CRITERIA` по пунктам; **финальный отчёт по CLAUDE.md §53** с явным
разделением: production implementation / mock implementation / нереализованное.
**Commit:** `docs: add deployment scripts, operating guide and final implementation report`

---

## 6. ГРАФ ЗАВИСИМОСТЕЙ ЭТАПОВ

```
S0 → S1 → S2 → S3 → S4 → S5 → S6
                         ↘  S7 → S8 → S9(.0→.1→.2→.3→.4)
                                          ↘ S10 → S11
S6 + S8 + S9 + S10 + S11 → S12 → S13 → S14 → S15 → S16
                                                    ↘ S17 → S18 → S19 → S20
                                                                          ↘ S21 → S22 → S23 → S24 → S25
```

Параллелизации нет — работа строго последовательная, чтобы каждый этап оставлял
проект в стабильном состоянии.

---

## 7. ПРАВИЛА РАБОТЫ В КАЖДОМ ЭТАПЕ

1. Прочитать `DEVELOPMENT_STATUS.md` → определить текущий этап.
2. При необходимости прочитать **только** документы из §4 для этого этапа.
3. Реализовать модуль.
4. Интегрировать с уже готовыми модулями (не оставлять «висящий» код).
5. Написать и запустить тесты этапа + прогнать все предыдущие тесты (регрессия).
6. Исправить найденные ошибки. **Тесты не ослаблять** (CLAUDE.md §40).
7. Проверить `git diff -- docs/architecture/` — должно быть **пусто** (CLAUDE.md §42).
   Также проверить, что не изменён `CLAUDE.md`.
8. Запустить `ruff`, `ruff format --check`, `mypy --strict`.
9. Обновить `DEVELOPMENT_STATUS.md`.
10. `git add` → `git commit` → `git push -u origin claude/monik-implementation`.

**Правило безопасности сессии:** если лимит/время заканчиваются — доделать текущий
подэтап до компилируемого и протестированного состояния, обновить
`DEVELOPMENT_STATUS.md`, закоммитить и запушить. Незакоммиченной работы не оставлять.

---

## 8. РИСКИ И СПОСОБЫ ИХ ОБРАБОТКИ

| # | Риск | Влияние | Обработка |
|---|---|---|---|
| **Р-1** | **Провайдерские API и их официальные доки заблокированы egress-политикой; API-ключей нет** | Требование CLAUDE.md §9 и `06 §54,62,64` (верификация против реального API) **невыполнимо в этой среде** | Реализовать адаптеры по контрактам, собранным через `WebSearch`; вынести endpoints/params в один файл на адаптер; пометить каждый adapter как `NOT live-verified`; поставить `scripts/verify_provider_api.py`; **явно указать это ограничение в финальном отчёте** (CLAUDE.md §46, §53) |
| **Р-2** | Терминологический конфликт `Candidate` vs `Opportunity` между документами | Затрагивает модели, схему БД и state machines | ✅ **ЗАКРЫТ** решением пользователя D-1 (см. §9) |
| **Р-3** | RPC и price-API недоступны в этой среде | Нельзя получить реальный gas/цену | Решение D-4: `GasPriceProvider` / `TokenPriceProvider` как независимые абстракции, реальные реализации + mocks; при отсутствии данных → `UNKNOWN` (архитектурно корректно: не подтверждать). Источник заменяется конфигом без правки Calculator |
| **Р-4** | Telegram API недоступен | Нельзя проверить реальную доставку | Полное покрытие тестами через `FakeHttpClient`; реальная доставка помечается как непроверенная |
| **Р-5** | Объём: ~26 этапов, большая кодовая база | Может не уместиться в одну сессию | Каждый этап — отдельный commit и отдельная запись в `DEVELOPMENT_STATUS.md`; возобновление с любого места |
| **Р-6** | Два документа на подсистему могут дать расхождения при реализации | Остановка работы | Оба документа читаются совместно; при реальном конфликте — STOP + REPORT (CLAUDE.md §44), работа продолжается по другим этапам |
| **Р-7** | `mypy --strict` на async + pydantic v2 даёт много шума | Замедление | Строгость сохраняем; узкие `# type: ignore[code]` только с обоснованием |
| **Р-8** | Обрывы загрузок с PyPI | Ломает установку | `UV_HTTP_TIMEOUT=180` + повтор (проверено, работает) |
| **Р-9** | SQLite + высокая конкурентность (20 параллельных Level 2) | Блокировки | WAL, короткие транзакции, busy timeout, ограниченный retry, запись через ограниченный пул |
| **Р-10** | Дедупликация Level 2 + retry внутри одного `#K` — сложная логика | Дубли/потери | Отдельные тесты дедупликации, идемпотентности и конкурентных переходов состояний |

---

## 9. ЗАФИКСИРОВАННЫЕ АРХИТЕКТУРНЫЕ РЕШЕНИЯ

Все решения **приняты пользователем 2026-09-04** и обязательны к исполнению.
Переспрашивать по ним не требуется.

### D-1 — Наименование сущности Level 1 ✅ ЗАФИКСИРОВАНО

**Решение пользователя:**
- **`Opportunity` — официальное название сущности Level 1.**
- **`Candidate` — промежуточный результат до прохождения необходимых проверок**
  (внутренний value object Level 1, не persistent entity).
- Разработку из-за расхождения документов не останавливать.

**Реализация:**
- Level 1 создаёт `Opportunity` в статусе `CREATED` с идентификатором `#V1234`,
  route snapshot (BUY + SELL) и N amount-контекстами.
- `Level2Job` — `#K1234`, отдельное пространство идентификаторов (CLAUDE.md §20).
- Единый lifecycle `Opportunity`:
  `CREATED → VERIFYING → {CONFIRMED, PARTIAL, UNPROFITABLE, ROUTE_UNAVAILABLE,
  EXPIRED, FAILED, CANCELLED}`, далее `{CONFIRMED, PARTIAL} → {NOTIFIED,
  NOTIFIED_PARTIAL, NOTIFIED_FAILED}`.
  Так объединяются статусы `11 §47` (verification) и `35 §59` / `30 §27` (notification).
- Per-amount статусы `11 §48` → `CONFIRMED / UNCONFIRMED / PARTIAL` (CLAUDE.md §26).
- После достижения `CONFIRMED`/`PARTIAL` financial snapshot **immutable**
  (`36 §45`, `35 §66`); коррекция — только через explicit correction/audit mechanism.
- Таблицы: `opportunities`, `opportunity_amounts`, `level2_jobs`, `level2_attempts`,
  `level2_amount_results`. Отдельной таблицы `candidates` нет
  (`30 §28` допускает, но не требует её).

### D-2 — Telegram-команды и кнопка `об` ✅ ЗАФИКСИРОВАНО

Реализуются согласно `CLAUDE.md §35-36` как входящий канал Notification-подсистемы
(long-polling через Resource Manager, низкий приоритет). Handlers читают только
сохранённые snapshots из репозиториев, **не инициируют provider-запросы** и
не блокируют Scanner.

### D-3 — Адаптеры без live-верификации API ✅ ЗАФИКСИРОВАНО

**Решение пользователя:** реализовать полноценные адаптеры для 1inch, 0x,
Velora/ParaSwap и Uniswap согласно документации и архитектурным требованиям;
добавить mocks, contract- и integration-тесты и `scripts/verify_provider_api.py`.
Live-проверка переносится на последующий этап.

**Реализация:**
- каждый adapter — полноценный production-модуль с реальным построением запросов,
  парсингом, нормализацией, error mapping, route extraction, fee extraction,
  fixed-route поддержкой;
- endpoints/params/network ids/auth локализованы в одном `endpoints.py` внутри адаптера,
  чтобы корректировка после live-проверки была минимальной;
- каждый adapter проходит общий contract test suite;
- в docstring адаптера и в финальном отчёте — пометка
  `API contract NOT verified against live endpoint`;
- `scripts/verify_provider_api.py` выполняет реальные запросы и сверяет схему ответа
  с ожиданиями адаптера (запускается пользователем в среде с сетью и ключами).

### D-4 — Gas и conversion rate ✅ ЗАФИКСИРОВАНО

**Решение пользователя:** `GasPriceProvider` и `TokenPriceProvider` — независимые
абстракции; gas определяется динамически для каждой сети через доступный RPC и/или
gas estimate маршрута от адаптера; conversion переводит стоимость native gas token
в базовую валюту расчёта (предпочтительно USDT/USD); бизнес-логика не привязана
к конкретному внешнему провайдеру цен; конкретные источники (RPC, Chainlink,
CoinGecko, DeFiLlama и др.) подключаются реализациями Provider; на этапе разработки
используются mocks и тестовые данные.

**Реализация (`services/gas/`, `services/prices/`):**
- `GasPriceProvider` protocol → `RpcGasPriceProvider` (eth_gasPrice / eth_feeHistory,
  EIP-1559 baseFee+priorityFee), `AdapterGasEstimateProvider` (gas estimate из quote),
  `StaticGasPriceProvider` (тестовый/fallback, помечен как test impl);
- `GasEstimator` = gas_units (из route/adapter) × gas_price (из `GasPriceProvider`)
  → стоимость в native token; при недостатке данных → `UNKNOWN`, **не 0**;
- `TokenPriceProvider` protocol → `AggregatorQuotePriceProvider` (цена native token
  через quote к USDT у уже подключённого агрегатора), `HttpPriceProvider`
  (CoinGecko / DeFiLlama — подключается конфигом), `StaticPriceProvider` (тестовый);
- `ConversionService`: native gas token → базовая валюта расчёта (по умолчанию USDT
  на соответствующей сети); хранит `source`, `timestamp`, `pair`, `rate`, `precision`,
  направление конверсии; при stale/недоступности → `PARTIAL`/`UNKNOWN`;
- выбор реализаций — только через configuration; `ProfitCalculator` получает уже
  нормализованные `Gas` и conversion data и **не знает** об источниках;
- все внешние вызовы (RPC, price API) идут через Resource Manager.

### D-5 — Идентичность Velora ✅ ЗАФИКСИРОВАНО

`provider_id = "velora"`; Velora — ребрендинг ParaSwap, используются актуальные
endpoints Velora/ParaSwap, вынесенные в `endpoints.py` адаптера.

### D-6 — Секреты и ключи ✅ ЗАФИКСИРОВАНО

Реальные API-ключи и Telegram bot token **не предоставляются**. Разработка ведётся
полностью без них:
- все credentials — только через environment variables, объявленные в конфиге как
  ссылки `{env: "MONIK_..."}`; в YAML реальных значений нет никогда;
- `config/config.example.yaml` + `.env.example` описывают все требуемые переменные;
- при отсутствии переменной provider помечается как `disabled`/`unconfigured` с
  внятной ошибкой конфигурации — приложение не падает молча и не подставляет заглушку;
- тесты используют только фиктивные значения; secret redaction покрыта тестами;
- после завершения разработки достаточно задать env-переменные — изменения кода
  не потребуются.

---

## 10. КРИТЕРИИ ЗАВЕРШЕНИЯ ПРОЕКТА

Из `CLAUDE.md §52` и `40_ACCEPTANCE_CRITERIA`. Проект считается завершённым, когда:

- [ ] приложение запускается и корректно останавливается;
- [ ] невалидная конфигурация останавливает старт с внятной ошибкой;
- [ ] SQLite инициализируется, migrations применяются, integrity check проходит;
- [ ] recovery после краха работает и не создаёт дублей;
- [ ] Resource Manager обеспечивает лимиты, приоритеты, retry, circuit breaker;
- [ ] Level 1 и Level 2 работают по утверждённым правилам (fixed route, свежие данные);
- [ ] Scheduler запускает startup/interval/daily задачи;
- [ ] реализованы 4 adapter'а (1inch, 0x, Velora, Uniswap), Polygon поддерживается;
- [ ] Fee System и Gas работают, UNKNOWN ≠ 0;
- [ ] Profit Calculator детерминирован и точен (Decimal);
- [ ] Telegram: уведомления, кнопка `об`, команды `/details`, `/level2`, `/status`, `/stats`;
- [ ] fixed-route validation, concurrency, deduplication работают;
- [ ] весь test suite зелёный; ruff + mypy strict чисты;
- [ ] `docs/architecture/` и `CLAUDE.md` не изменены;
- [ ] секретов в репозитории нет;
- [ ] финальный отчёт составлен с честным разделением production / mock / нереализованное.

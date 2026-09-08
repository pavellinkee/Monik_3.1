# MONIK 3.0 — ФИНАЛЬНЫЙ ОТЧЁТ О РЕАЛИЗАЦИИ

> Отчёт по `CLAUDE.md` §53. Архитектурные документы в `docs/architecture/`
> не изменялись (`CLAUDE.md` §3, §42) — проверяется перед каждым commit.
>
> Дата: 2026-09-04 · Ветка: `claude/monik-implementation`

---

## 1. Итоговая структура проекта

```
monik/
├── app/               composition root, lifecycle, recovery, supervisor, entrypoint
├── config/            секции конфигурации, loader, секрет-ссылки, диагностика
├── domain/            enums, value objects, models, ошибки — без внешних зависимостей
├── infrastructure/
│   ├── db/            соединение, миграции, транзакции, типы хранения
│   ├── http/          SSRF-политика, контролируемый клиент, классификация ответов
│   ├── providers/     контракт адаптеров + 1inch, 0x, Velora, Uniswap
│   └── telegram/      адаптер доставки и входящий канал Bot API
├── repositories/      интерфейсы (Protocol) и реализации поверх SQLite
└── services/
    ├── calculator/    единственный владелец финансовых формул
    ├── level1/        поиск возможностей
    ├── level2/        подтверждение на зафиксированном маршруте
    ├── opportunity/   снимок подтверждения и постановка доставки
    ├── notifications/ формат, очередь, retry, режимы A/B
    ├── commands/      входящие Telegram-команды
    ├── scheduler/     расписания, startup-порядок, overlap
    ├── health/        health monitoring
    ├── resources/     Resource Manager
    ├── registries/    networks, tokens, providers, capabilities
    ├── fees/ gas/ prices/  стоимость, газ и конверсия
    └── observability/ clock, correlation, structured logging, метрики, редакция
```

**218 модулей** исходного кода, **73 тестовых модуля**.

---

## 2. Реализованные компоненты

| Подсистема | Состояние | Ключевые гарантии |
|---|---|---|
| Configuration | production | env > файл > безопасный default; секреты только по ссылке на окружение; невалидная конфигурация не подменяется значениями «по умолчанию» |
| Domain model | production | `float` отклоняется на входе; UNKNOWN ≠ 0; frozen-модели |
| SQLite + migrations | production | WAL, `foreign_keys=ON`, integrity check, последовательные миграции |
| Repositories | production | атомарное создание Opportunity + Level 2 Job; параметризованный SQL |
| Registries | production | UNKNOWN capability ≠ SUPPORTED; lookup без ввода-вывода |
| HTTP infrastructure | production | https-only, allowlist, блокировка loopback/приватных/link-local, TLS не отключается |
| Resource Manager | production | приоритеты, rate limit, retry с backoff и `Retry-After`, circuit breaker, дедупликация |
| Aggregator Adapters | production (контракт не проверен вживую) | 1inch, 0x, Velora, Uniswap; общий contract suite |
| Fee System | production | UNKNOWN без суммы; снимки с версией правил; дедупликация запросов |
| Gas / Prices | production | EIP-1559 через RPC, конверсия с явным направлением; при недостатке данных — UNKNOWN |
| Profit Calculator | production | единственный владелец формул; детерминированная точная арифметика; неизвестный расход блокирует порог |
| Level 1 Scanner | production | независимые циклы токенов, MAX BUY → немедленный SELL, один маршрут на все суммы, дедупликация, backpressure |
| Level 2 Scanner | production | проверка **того же** маршрута, SELL от текущего BUY output, ROUTE_UNAVAILABLE ≠ UNPROFITABLE, идемпотентность по revision |
| Opportunity Service | production | immutable снимок подтверждения; сохранение до постановки доставки одной транзакцией |
| Notification System | production | порядок по `created_at` + sequence, retry с лимитом, изоляция назначений, кнопка `об` |
| Telegram | production (контракт не проверен вживую) | доставка и входящий канал через Resource Manager; токен не попадает в логи |
| Telegram commands | production | `/details`, `/level2`, `/status`, `/stats`, кнопка `об` — только из сохранённых данных |
| Scheduler | production | STARTUP/INTERVAL/DAILY/MANUAL, IANA timezone и DST, overlap SKIP, порядок зависимостей |
| Health + Supervisor | production | гистерезис провайдеров, изоляция, перезапуск некритического воркера, `SAFE_STOP` |
| Observability | production | correlation context, structured logs с редакцией, метрики с контролем cardinality |
| Application lifecycle | production | порядок `CLAUDE.md` §30, recovery, graceful shutdown |

### Mock / test implementations

Явно помечены как **test implementation** и не используются в production-пути:

- `monik/infrastructure/providers/fake.py` — `FakeAdapter`;
- `monik/infrastructure/http/fake.py` — `FakeHttpClient`;
- `monik/infrastructure/telegram/fake.py` — `FakeTransport`;
- `monik/services/gas/providers.py` — `StaticGasPriceProvider`;
- `monik/services/prices/providers.py` — `StaticPriceProvider`;
- `monik/services/observability/clock.py` — `FakeClock`.

`gas.static_wei_per_gas` — явно настраиваемый fallback цены газа; в
production предполагается источник `rpc`.

### Нереализованное

- автоматическое исполнение свопов — вне рамок (`01_PROJECT_REQUIREMENTS.md` §55);
- maintenance-задачи полного capability discovery и fee discovery по
  расписанию зарегистрированы как точки расширения Scheduler, но
  discovery-обработчики провайдеров вызываются только вручную;
- horizontal scaling и внешние системы мониторинга (Prometheus и т. п.):
  метрики собираются в памяти и отдаются через `/stats`, экспортер не
  реализован;
- reload конфигурации без рестарта.

---

## 3. Aggregator Adapters

| Провайдер | Модуль | API | Статус контракта |
|---|---|---|---|
| 1inch | `infrastructure/providers/oneinch` | Swap API v6 (`/quote`) | ⚠️ не проверен вживую |
| 0x | `infrastructure/providers/zero_x` | Swap API v2 allowance-holder (`/price`) | ⚠️ не проверен вживую |
| Velora (ParaSwap) | `infrastructure/providers/velora` | Market API (`/prices`) | ⚠️ не проверен вживую |
| Uniswap | `infrastructure/providers/uniswap` | Trading API (`POST /v1/quote`) | ⚠️ не проверен вживую |

Все четыре проходят общий contract suite (`tests/contract/`): нормализация,
детерминированный отпечаток маршрута, честный отказ при невозможности
подтвердить fixed route, отсутствие выдуманных нулей в комиссиях,
нормализация ошибок.

Uniswap: Classic и семейство UniswapX сохраняются как **разные** routing
modes и не объединяются — смена режима даёт другой отпечаток и
распознаётся Level 2 как `MISMATCH`.

---

## 4. Поддерживаемые сети

Polygon (`chain_id 137`) — базовая сеть текущей конфигурации.
Архитектура сетевого-агностична: сети, токены и суммы задаются
конфигурацией, добавление сети не требует изменения кода сканеров.

---

## 5. Telegram commands

| Команда | Ответ |
|---|---|
| `/details K1234` | сохранённый результат проверки: итог, счётчики сумм, причины |
| `/level2` | активные Level 2 задачи |
| `/status` | состояние подсистем и провайдеров |
| `/stats` | циклы, возможности, уведомления, confirmation rate (`N/A` при отсутствии решений) |
| кнопка `об` | подготовленный текст деталей из сохранённого снимка |

Ни один обработчик не выполняет запрос к провайдеру котировок — проверено
component- и architecture-тестами.

---

## 6. Configuration options

Секции: `application`, `networks`, `providers`, `tokens`, `routes`,
`scanner` (`level1`, `level2`), `profitability`, `capabilities`, `fees`,
`gas`, `prices`, `http`, `resources`, `health`, `scheduler`,
`notifications` (`telegram`, `mode_a`, `mode_b`), `database`
(`retention`), `logging`, `metrics`.

Полный шаблон — `config/config.example.yaml`, переменные окружения —
`.env.example`, руководство — `docs/OPERATING.md`.

Инварианты, которые **нельзя** отключить конфигурацией: unknown fee/gas
≠ 0; обязательная проверка зафиксированного маршрута Level 2; учёт
`Retry-After`; `foreign_keys=ON`; проверка TLS.

---

## 7. Результаты тестов

```
pytest -m "not external"   →  5122 passed
ruff check                 →  passed
ruff format --check        →  passed
mypy --strict monik        →  passed (218 модулей)
git diff docs/architecture →  пусто
```

| Набор | Тестов |
|---|---|
| unit | 780 |
| component | 198 |
| integration | 148 |
| contract (адаптеры) | 84 |
| e2e (сценарии, lifecycle, crash-recovery) | 30 |
| architecture | 2929 |
| security | 944 |
| performance | 9 |

---

## 8. Результаты проверки реальных API

**Проверка вживую не выполнялась.**

Среда разработки не имеет сетевого доступа к `api.1inch.dev`, `api.0x.org`,
`api.paraswap.io`, `trade-api.gateway.uniswap.org` и `api.telegram.org`
(egress-политика), а ключи и Telegram bot token не предоставлялись
(решения D-3 и D-6 `DEVELOPMENT_PLAN.md` §9).

Контракты API реализованы по официальной документации, каждый адаптер
помечен `⚠️ API contract NOT verified against live endpoint`.

Закрывается запуском в среде с сетью и ключами:

```bash
uv run python scripts/verify_provider_api.py --config config/config.yaml
```

---

## 9. Известные ограничения

1. **Контракты провайдерских API и Telegram Bot API не подтверждены
   вживую.** До запуска `verify_provider_api.py` считать адаптеры
   непроверенными.
2. **Fee policy по умолчанию — `QuoteInclusiveFeePolicy`** для всех
   включённых провайдеров: агрегатор возвращает итоговую сумму маршрута.
   Если у конкретного провайдера появится комиссия сверх котировки, для
   него потребуется отдельная policy — Scanner при этом не меняется.
3. **Метрики хранятся в памяти процесса** и не экспортируются наружу.
4. **Maintenance по расписанию** (полный capability discovery, fee
   discovery) не зарегистрирован как отдельная задача Scheduler.
5. **Конверсия газа** по умолчанию берётся из котировки уже подключённого
   агрегатора; отдельный market-data провайдер настраивается через
   `prices.sources`.
6. **Один процесс.** Горизонтальное масштабирование и распределённые
   блокировки не реализованы.

---

## 10. Нерешённые проблемы

Архитектурных конфликтов, требующих решения пользователя, **не осталось**.
Ранее зафиксированные вопросы закрыты решениями D-1…D-6
(`DEVELOPMENT_PLAN.md` §9).

Остаётся один внешний шаг, который невозможно выполнить в текущей среде:

- **проверка провайдерских API и Telegram вживую** — требует сетевого
  доступа и реальных ключей. До неё утверждать, что production API
  работает, нельзя (`CLAUDE.md` §10, §46).

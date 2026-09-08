# MONIK — РУКОВОДСТВО ПО ЗАПУСКУ

> Техническая документация по эксплуатации. Архитектурные документы в
> `docs/architecture/` этим файлом **не изменяются** (`CLAUDE.md` §43).

---

## 1. Требования

- Python 3.12;
- [`uv`](https://docs.astral.sh/uv/) для установки зависимостей;
- доступ к API агрегаторов и Telegram Bot API (для production-запуска).

```bash
uv sync --group dev
```

---

## 2. Конфигурация

Конфигурация задаётся YAML-файлом; шаблон — `config/config.example.yaml`.

```bash
cp config/config.example.yaml config/config.yaml
```

Приоритет источников: переменная окружения `MONIK__SECTION__FIELD` >
значение из файла > безопасный default.

### Секреты

Секреты **никогда** не хранятся в файле конфигурации: указывается только
ссылка на переменную окружения.

```yaml
providers:
  - provider_id: oneinch
    api_key: { env: "MONIK_ONEINCH_API_KEY" }
```

Полный список переменных — в `.env.example`. Значения задаются в окружении
процесса, а не в репозитории (`CLAUDE.md` §49).

### Проверка конфигурации

```bash
uv run monik --config config/config.yaml --check-config
```

Команда валидирует конфигурацию, разрешает секрет-ссылки и завершается,
не запуская воркеры. Код возврата `1` означает, что конфигурация
некорректна: значения «по умолчанию» вместо неё не подставляются.

---

## 3. Первый запуск

```bash
uv run python scripts/init_db.py --config config/config.yaml
uv run monik --config config/config.yaml
```

Порядок запуска приложения фиксирован (`CLAUDE.md` §30):

1. загрузка конфигурации;
2. открытие SQLite;
3. проверка целостности;
4. применение migrations;
5. восстановление незавершённого состояния;
6. инициализация адаптеров;
7. Resource Manager;
8. Scheduler;
9. Telegram;
10. запуск воркеров.

Коды возврата: `0` — штатная остановка, `1` — ошибка конфигурации или
запуска, `2` — остановка в состоянии `SAFE_STOP`.

---

## 4. Остановка

`SIGINT` и `SIGTERM` инициируют graceful shutdown: новые циклы не
создаются, активные задачи получают отмену, состояние сохраняется. Таймаут
задаётся `application.shutdown_timeout_seconds`.

---

## 5. Резервное копирование

```bash
uv run python scripts/backup_db.py  --config config/config.yaml --output backups/
uv run python scripts/restore_db.py --config config/config.yaml --backup backups/monik-<ts>.db
```

Копия делается online-backup'ом SQLite и проверяется на целостность.
Восстановление не перезаписывает существующую базу без `--force`.

---

## 6. Проверка провайдерских API

Контракты провайдерских API не проверялись вживую (решение D-3
`DEVELOPMENT_PLAN.md` §9). В среде с сетевым доступом и ключами:

```bash
uv run python scripts/verify_provider_api.py --config config/config.yaml
```

Скрипт вызывает те же адаптеры, что и приложение, и не выполняет свопов.

---

## 7. Тесты и проверки

```bash
make lint          # ruff check
make format-check  # ruff format --check
make typecheck     # mypy --strict
make test          # pytest (без маркера external)
make ci            # всё вместе + проверка неизменности docs/architecture
```

Тесты с маркером `external` требуют сети и ключей и по умолчанию не
запускаются.

---

## 8. Telegram

Уведомления и команды включаются секцией `notifications`:

```yaml
notifications:
  enabled: true
  telegram:
    enabled: true
    bot_token: { env: "MONIK_TELEGRAM_BOT_TOKEN" }
    chat_id: { env: "MONIK_TELEGRAM_CHAT_ID" }
    commands_enabled: true
```

Поддерживаемые команды: `/details K1234`, `/level2`, `/status`, `/stats`.
Каждое уведомление о возможности содержит кнопку `об`; её текст готовится
заранее, поэтому нажатие не выполняет новых запросов к провайдерам.

---

## 9. Эксплуатационные заметки

- Уровень логирования задаётся `logging.level`; вывод — структурированный
  JSON с редакцией секретов;
- `/status` показывает состояние подсистем и провайдеров, `/stats` —
  накопленную статистику и confirmation rate;
- при критической ошибке persistence приложение переходит в `SAFE_STOP`
  и не продолжает работу на недостоверном состоянии;
- retention и cleanup удаляют завершённые циклы и старые снимки согласно
  секции `database.retention`.

# scripts/

Операционные и вспомогательные скрипты.

Скрипты не содержат дублирующей business logic — они вызывают интерфейсы приложения
(`25_PROJECT_STRUCTURE.md` §41-42).

| Скрипт | Назначение |
|---|---|
| `verify_provider_api.py` | Реальная проверка контрактов провайдерских API (запускается в среде с сетевым доступом и ключами) |
| `init_db.py` | Создание БД, применение migrations и проверка целостности |
| `backup_db.py` | Online-backup SQLite с проверкой полученной копии |
| `restore_db.py` | Восстановление из резервной копии (существующая БД не перезаписывается без `--force`) |

## Запуск

```bash
uv run python scripts/init_db.py    --config config/config.yaml
uv run python scripts/backup_db.py  --config config/config.yaml --output backups/
uv run python scripts/restore_db.py --config config/config.yaml --backup backups/monik-<ts>.db
uv run python scripts/verify_provider_api.py --config config/config.yaml
```

Само приложение запускается собственной командой:

```bash
uv run monik --config config/config.yaml
uv run monik --config config/config.yaml --check-config   # только валидация
```

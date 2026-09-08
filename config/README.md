# config/

Пример конфигурации и (со этапа S3) machine-readable схема.

- Реальные секреты здесь не хранятся никогда (`17_CONFIGURATION.md` §5, §37).
- Credentials задаются ссылками `{ env: "MONIK_..." }` и разрешаются
  Configuration subsystem из environment variables.
- Python-реализация подсистемы конфигурации находится в `monik/config/`.

"""Управление соединением SQLite.

Соединение настраивается один раз при старте: WAL, включённые foreign keys,
busy timeout и проверка целостности (``30_DATABASE_SCHEMA.md`` §21, §79-83).

Записи сериализуются одним asyncio-локом. SQLite допускает единственного
писателя, поэтому явная сериализация даёт предсказуемое поведение вместо
случайных ``database is locked`` при 20 параллельных Level 2 workflow
(``30_DATABASE_SCHEMA.md`` §78).
"""

from __future__ import annotations

import asyncio
import pathlib
from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from monik.config.sections.database import DatabaseConfig
from monik.domain.errors import DatabaseError
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["Database", "Transaction"]

_LOGGER = get_logger("infrastructure.db")

#: Сколько раз повторить операцию, заблокированную другим писателем.
#: Повтор ограничен: бесконечных повторов к БД не существует
#: (``16_DATABASE.md`` §40).
_MAX_LOCK_RETRIES = 3

#: Пауза между повторами при блокировке.
_LOCK_RETRY_DELAY_SECONDS = 0.05


class Transaction:
    """Активная транзакция.

    Оборачивает соединение, чтобы исключения драйвера не выходили за
    пределы infrastructure (``38_INTERFACES.md`` §82) и репозиториям не
    требовался доступ к объекту ``aiosqlite.Connection``.
    """

    __slots__ = ("_connection",)

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def execute(self, sql: str, parameters: Sequence[Any] = ()) -> None:
        """Выполнить изменяющий запрос внутри транзакции."""
        try:
            await self._connection.execute(sql, parameters)
        except aiosqlite.Error as exc:
            raise Database._translate(exc, sql) from exc

    async def execute_many(self, sql: str, parameters: Iterable[Sequence[Any]]) -> None:
        """Выполнить изменяющий запрос для набора параметров."""
        try:
            await self._connection.executemany(sql, list(parameters))
        except aiosqlite.Error as exc:
            raise Database._translate(exc, sql) from exc

    async def fetch_one(self, sql: str, parameters: Sequence[Any] = ()) -> aiosqlite.Row | None:
        """Прочитать первую строку внутри транзакции."""
        try:
            async with self._connection.execute(sql, parameters) as cursor:
                return await cursor.fetchone()
        except aiosqlite.Error as exc:
            raise Database._translate(exc, sql) from exc

    async def fetch_all(self, sql: str, parameters: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        """Прочитать все строки внутри транзакции."""
        try:
            async with self._connection.execute(sql, parameters) as cursor:
                return list(await cursor.fetchall())
        except aiosqlite.Error as exc:
            raise Database._translate(exc, sql) from exc


class Database:
    """Соединение с SQLite и низкоуровневые операции.

    Класс не знает о доменных сущностях: маппинг выполняют репозитории
    (``30_DATABASE_SCHEMA.md`` §5).
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._connection: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    @property
    def path(self) -> pathlib.Path:
        """Путь к файлу базы данных."""
        return pathlib.Path(self._config.path)

    @property
    def is_connected(self) -> bool:
        """Открыто ли соединение."""
        return self._connection is not None

    async def connect(self) -> None:
        """Открыть соединение и применить обязательные PRAGMA."""
        if self._connection is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            connection = await aiosqlite.connect(
                self.path,
                timeout=self._config.busy_timeout_seconds,
                isolation_level=None,
            )
        except (aiosqlite.Error, OSError) as exc:
            raise DatabaseError(
                f"cannot open database at {self.path}: {exc}",
                code="database_open_failed",
            ) from exc

        connection.row_factory = aiosqlite.Row
        self._connection = connection
        await self._apply_pragmas()
        _LOGGER.info(
            "database connected",
            extra=log_fields(path=str(self.path), wal=self._config.wal_enabled),
        )

    async def _apply_pragmas(self) -> None:
        connection = self._require_connection()
        timeout_ms = int(self._config.busy_timeout_seconds * 1000)
        await connection.execute(f"PRAGMA busy_timeout = {timeout_ms}")
        # Foreign keys включаются на каждое соединение: SQLite не хранит
        # это состояние в файле (``30_DATABASE_SCHEMA.md`` §21).
        await connection.execute("PRAGMA foreign_keys = ON")
        if self._config.wal_enabled:
            await connection.execute("PRAGMA journal_mode = WAL")
        await connection.execute("PRAGMA synchronous = FULL")

    async def close(self) -> None:
        """Закрыть соединение."""
        if self._connection is None:
            return
        await self._connection.close()
        self._connection = None
        _LOGGER.info("database closed", extra=log_fields(path=str(self.path)))

    def _require_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise DatabaseError("database is not connected", code="database_not_connected")
        return self._connection

    async def check_integrity(self) -> None:
        """Проверить целостность базы.

        При обнаружении повреждения приложение обязано перейти в безопасное
        состояние и не продолжать запись вслепую
        (``30_DATABASE_SCHEMA.md`` §83).
        """
        row = await self.fetch_one("PRAGMA integrity_check")
        if row is None:
            raise DatabaseError("integrity check returned no result", code="database_corrupted")
        result = str(row[0])
        if result.lower() != "ok":
            raise DatabaseError(
                f"database integrity check failed: {result}",
                code="database_corrupted",
            )

    async def foreign_keys_enabled(self) -> bool:
        """Включены ли foreign keys на текущем соединении."""
        row = await self.fetch_one("PRAGMA foreign_keys")
        return bool(row and row[0])

    async def journal_mode(self) -> str:
        """Текущий journal mode."""
        row = await self.fetch_one("PRAGMA journal_mode")
        return str(row[0]) if row else ""

    async def execute(self, sql: str, parameters: Sequence[Any] = ()) -> None:
        """Выполнить изменяющий запрос."""
        async with self._write_lock:
            await self._execute_with_retry(sql, parameters)

    async def execute_many(self, sql: str, parameters: Iterable[Sequence[Any]]) -> None:
        """Выполнить изменяющий запрос для набора параметров."""
        connection = self._require_connection()
        async with self._write_lock:
            try:
                await connection.executemany(sql, list(parameters))
            except aiosqlite.Error as exc:
                raise self._translate(exc, sql) from exc

    async def execute_script(self, statements: Iterable[str]) -> None:
        """Выполнить последовательность DDL-инструкций."""
        connection = self._require_connection()
        async with self._write_lock:
            for statement in statements:
                try:
                    await connection.execute(statement)
                except aiosqlite.Error as exc:
                    raise self._translate(exc, statement) from exc

    async def fetch_one(self, sql: str, parameters: Sequence[Any] = ()) -> aiosqlite.Row | None:
        """Выполнить запрос и вернуть первую строку."""
        connection = self._require_connection()
        try:
            async with connection.execute(sql, parameters) as cursor:
                return await cursor.fetchone()
        except aiosqlite.Error as exc:
            raise self._translate(exc, sql) from exc

    async def fetch_all(self, sql: str, parameters: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        """Выполнить запрос и вернуть все строки."""
        connection = self._require_connection()
        try:
            async with connection.execute(sql, parameters) as cursor:
                return list(await cursor.fetchall())
        except aiosqlite.Error as exc:
            raise self._translate(exc, sql) from exc

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        """Выполнить набор операций атомарно.

        Транзакция должна быть короткой и никогда не удерживаться во время
        внешнего запроса (``30_DATABASE_SCHEMA.md`` §76-77). Это правило
        проверяется architecture-тестом.
        """
        connection = self._require_connection()
        async with self._write_lock:
            await self._execute_with_retry("BEGIN IMMEDIATE", ())
            try:
                yield Transaction(connection)
            except BaseException:
                await connection.execute("ROLLBACK")
                raise
            else:
                await connection.execute("COMMIT")

    async def _execute_with_retry(self, sql: str, parameters: Sequence[Any]) -> None:
        """Выполнить запрос, повторив ограниченное число раз при блокировке."""
        connection = self._require_connection()
        last_error: aiosqlite.Error | None = None
        for attempt in range(_MAX_LOCK_RETRIES):
            try:
                await connection.execute(sql, parameters)
                return
            except aiosqlite.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise self._translate(exc, sql) from exc
                last_error = exc
                if attempt + 1 < _MAX_LOCK_RETRIES:
                    await asyncio.sleep(_LOCK_RETRY_DELAY_SECONDS * (attempt + 1))
            except aiosqlite.Error as exc:
                raise self._translate(exc, sql) from exc
        raise DatabaseError(
            f"database is locked after {_MAX_LOCK_RETRIES} attempts: {last_error}",
            code="database_locked",
        )

    @staticmethod
    def _translate(error: aiosqlite.Error, sql: str) -> DatabaseError:
        """Перевести исключение драйвера в нормализованную ошибку.

        Драйверные исключения не распространяются выше infrastructure
        (``38_INTERFACES.md`` §82). Текст SQL сокращается, чтобы сообщение
        оставалось читаемым.
        """
        statement = " ".join(sql.split())[:120]
        if isinstance(error, aiosqlite.IntegrityError):
            return DatabaseError(
                f"integrity constraint violated: {error} (statement: {statement})",
                code="database_constraint_violated",
            )
        return DatabaseError(
            f"database operation failed: {error} (statement: {statement})",
            code="database_error",
        )

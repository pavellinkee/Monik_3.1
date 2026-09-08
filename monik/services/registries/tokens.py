"""Token Registry."""

from __future__ import annotations

from monik.config.root import Configuration
from monik.domain.errors import ConfigurationError
from monik.domain.models.token import Token, TokenKey
from monik.domain.value_objects.identity import NetworkId, TokenAddress, TokenSymbol

__all__ = ["TokenRegistry"]


class TokenRegistry:
    """Authoritative источник canonical token metadata (``38_INTERFACES.md`` §23-25).

    Registry не получает котировки и не считает прибыль
    (``38_INTERFACES.md`` §25). Собственного hard-coded списка токенов у него
    нет: набор приходит из конфигурации (``10_LEVEL_1_SCANNER.md`` §4).
    """

    def __init__(self, configuration: Configuration) -> None:
        self._tokens: dict[TokenKey, Token] = {}
        self._ranks: dict[TokenKey, int | None] = {}
        for token in configuration.tokens:
            model = Token(
                network_id=token.network_id,
                address=token.address,
                symbol=token.symbol,
                decimals=token.decimals,
                enabled=token.enabled,
            )
            self._tokens[model.key] = model
            self._ranks[model.key] = token.rank
        self._base_key = TokenKey(
            network_id=configuration.scanner.base_network,
            address=configuration.scanner.base_token_address,
        )
        self._top_n = configuration.scanner.level1.top_tokens

    def get(self, key: TokenKey) -> Token | None:
        """Найти токен по canonical identity."""
        return self._tokens.get(key)

    def get_by_address(self, network_id: NetworkId, address: str) -> Token | None:
        """Найти токен по сети и адресу.

        Адрес нормализуется, поэтому регистр записи не влияет на результат
        (``08_CAPABILITY_REGISTRY.md`` §30).
        """
        return self.get(TokenKey(network_id=network_id, address=TokenAddress(address)))

    def require(self, key: TokenKey) -> Token:
        """Найти токен или сообщить об ошибке конфигурации."""
        token = self.get(key)
        if token is None:
            raise ConfigurationError(f"token {key} is not configured", code="token_unknown")
        return token

    def exists(self, key: TokenKey) -> bool:
        """Известен ли токен реестру."""
        return key in self._tokens

    def is_enabled(self, key: TokenKey) -> bool:
        """Включён ли токен.

        Disabled токен не сканируется (``02_LEVEL1_SCANNER.md`` §70).
        """
        token = self.get(key)
        return token is not None and token.enabled

    def decimals(self, key: TokenKey) -> int:
        """Decimals токена.

        Финансовые расчёты обязаны брать decimals отсюда, а не выводить их
        из символа (``09_PROFIT_CALCULATOR.md`` §5).
        """
        return self.require(key).decimals

    def find_by_symbol(self, network_id: NetworkId, symbol: str) -> tuple[Token, ...]:
        """Все токены сети с указанным символом.

        Возвращается кортеж: символ не является идентичностью и может
        совпадать у разных токенов (``36_DATA_MODELS.md`` §10).
        """
        normalized = TokenSymbol(symbol)
        return tuple(
            token
            for token in self._tokens.values()
            if token.network_id == network_id and token.symbol == normalized
        )

    def list_enabled(self, network_id: NetworkId | None = None) -> tuple[Token, ...]:
        """Включённые токены, при необходимости — только указанной сети."""
        return tuple(
            token
            for token in self._tokens.values()
            if token.enabled and (network_id is None or token.network_id == network_id)
        )

    @property
    def base_token(self) -> Token:
        """Базовый токен цикла: вход и выход round-trip."""
        return self.require(self._base_key)

    def scan_tokens(self) -> tuple[Token, ...]:
        """Промежуточные токены для сканирования в порядке ранга.

        Набор ограничен Top-N (``01_PROJECT_REQUIREMENTS.md`` §7): бессмысленно
        сканировать огромное количество токенов. Базовый токен исключён —
        он является входом и выходом цикла.
        """
        candidates = [
            token
            for token in self._tokens.values()
            if token.enabled
            and token.network_id == self._base_key.network_id
            and token.key != self._base_key
        ]
        candidates.sort(
            key=lambda token: (
                self._ranks[token.key] is None,
                self._ranks[token.key] or 0,
                token.symbol,
            )
        )
        return tuple(candidates[: self._top_n])

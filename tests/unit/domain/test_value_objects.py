"""Тесты доменных value objects."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from monik.domain.value_objects import (
    KId,
    NetworkId,
    Percentage,
    TokenAddress,
    TokenAmount,
    TokenSymbol,
    VId,
    compute_fingerprint,
    ensure_utc,
    to_decimal,
)
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.numeric import (
    BaseUnits,
    FloatNotAllowedError,
    NonNegativeDecimal,
    PositiveDecimal,
    SignedDecimal,
)
from monik.domain.value_objects.timestamps import UtcDatetime


class _NumericProbe(BaseModel):
    """Вспомогательная модель для проверки числовых типов."""

    signed: SignedDecimal
    non_negative: NonNegativeDecimal
    positive: PositiveDecimal
    units: BaseUnits


class _TimeProbe(BaseModel):
    moment: UtcDatetime


class TestNetworkId:
    def test_normalizes_case_and_whitespace(self) -> None:
        assert NetworkId("  Polygon ") == "polygon"

    @pytest.mark.parametrize("value", ["", "Polygon Network", "-bad", "x" * 33, "поли"])
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            NetworkId(value)


class TestTokenAddress:
    def test_normalizes_to_lowercase(self) -> None:
        checksum = "0xC2132D05D31c914a87C6611C10748AEb04B58e8F"
        assert TokenAddress(checksum) == checksum.lower()

    def test_same_address_in_different_case_is_equal(self) -> None:
        upper = TokenAddress("0xC2132D05D31C914A87C6611C10748AEB04B58E8F")
        lower = TokenAddress("0xc2132d05d31c914a87c6611c10748aeb04b58e8f")
        assert upper == lower
        assert hash(upper) == hash(lower)

    @pytest.mark.parametrize(
        "value",
        ["0x123", "c2132d05d31c914a87c6611c10748aeb04b58e8f", "0x" + "z" * 40, ""],
    )
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            TokenAddress(value)


class TestTokenSymbol:
    def test_uppercases(self) -> None:
        assert TokenSymbol("usdt") == "USDT"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            TokenSymbol("")


class TestIdentifiers:
    def test_v_and_k_are_separate_spaces(self) -> None:
        """``#V1234`` и ``#K1234`` — разные пространства (CLAUDE.md §20)."""
        assert VId.from_sequence(1234) != KId.from_sequence(1234)
        assert VId.from_sequence(1234).sequence == KId.from_sequence(1234).sequence

    def test_accepts_value_without_hash(self) -> None:
        assert KId("K1234") == "#K1234"
        assert KId("k1234") == "#K1234"

    @pytest.mark.parametrize("value", ["#X1234", "#V", "#Vabc", "#K-1"])
    def test_rejects_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            KId(value)

    def test_v_id_rejects_k_id(self) -> None:
        with pytest.raises(ValueError):
            VId("#K1234")

    def test_sequence_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            VId.from_sequence(0)

    def test_generated_uuid_ids_are_valid_and_unique(self) -> None:
        first = OpportunityId.generate()
        second = OpportunityId.generate()
        assert first != second
        assert OpportunityId(str(first)) == first


class TestNumericTypes:
    def test_accepts_decimal_int_and_string(self) -> None:
        probe = _NumericProbe(signed="-1.5", non_negative=Decimal("0"), positive="0.1", units=10)
        assert probe.signed == Decimal("-1.5")
        assert probe.positive == Decimal("0.1")

    @pytest.mark.parametrize("field", ["signed", "non_negative", "positive"])
    def test_rejects_float_for_financial_fields(self, field: str) -> None:
        """Binary float запрещён для финансовых значений (CLAUDE.md §11)."""
        values = {
            "signed": Decimal("1"),
            "non_negative": Decimal("1"),
            "positive": Decimal("1"),
            "units": 1,
        }
        values[field] = 1.5  # type: ignore[assignment]
        with pytest.raises(ValidationError):
            _NumericProbe(**values)

    def test_rejects_float_for_base_units(self) -> None:
        with pytest.raises(ValidationError):
            _NumericProbe(
                signed=Decimal(1),
                non_negative=Decimal(1),
                positive=Decimal(1),
                units=1.0,  # type: ignore[arg-type]
            )

    def test_rejects_bool_for_base_units(self) -> None:
        with pytest.raises(ValidationError):
            _NumericProbe(
                signed=Decimal(1),
                non_negative=Decimal(1),
                positive=Decimal(1),
                units=True,  # type: ignore[arg-type]
            )

    def test_enforces_ranges(self) -> None:
        with pytest.raises(ValidationError):
            _NumericProbe(signed=Decimal(1), non_negative=Decimal(-1), positive=Decimal(1), units=1)
        with pytest.raises(ValidationError):
            _NumericProbe(signed=Decimal(1), non_negative=Decimal(1), positive=Decimal(0), units=1)
        with pytest.raises(ValidationError):
            _NumericProbe(signed=Decimal(1), non_negative=Decimal(1), positive=Decimal(1), units=-1)

    def test_to_decimal_rejects_float(self) -> None:
        with pytest.raises(FloatNotAllowedError):
            to_decimal(1.5)  # type: ignore[arg-type]

    def test_to_decimal_preserves_precision(self) -> None:
        assert to_decimal("0.100000000000000000001") == Decimal("0.100000000000000000001")


class TestTokenAmount:
    def test_converts_base_units_to_decimal(self) -> None:
        amount = TokenAmount(raw=100_500_000, decimals=6)
        assert amount.as_decimal == Decimal("100.500000")

    def test_round_trip_preserves_value(self) -> None:
        amount = TokenAmount.from_decimal("1234.567891", 6)
        assert amount.raw == 1_234_567_891
        assert amount.as_decimal == Decimal("1234.567891")

    def test_rejects_value_not_representable_with_decimals(self) -> None:
        """Молчаливое округление запрещено (17_CONFIGURATION.md §22)."""
        with pytest.raises(ValueError, match="not representable"):
            TokenAmount.from_decimal("0.1234567", 6)

    def test_high_precision_token_is_exact(self) -> None:
        amount = TokenAmount.from_decimal("1.000000000000000001", 18)
        assert amount.raw == 1_000_000_000_000_000_001

    def test_rejects_negative_raw(self) -> None:
        with pytest.raises(ValidationError):
            TokenAmount(raw=-1, decimals=6)

    def test_is_immutable(self) -> None:
        amount = TokenAmount(raw=1, decimals=6)
        with pytest.raises(ValidationError):
            amount.raw = 2  # type: ignore[misc]

    def test_equality_accounts_for_decimals(self) -> None:
        assert TokenAmount(raw=1, decimals=6) != TokenAmount(raw=1, decimals=18)


class TestPercentage:
    def test_from_ratio(self) -> None:
        assert Percentage.from_ratio(Decimal("0.015")).value == Decimal("1.500")

    def test_as_ratio(self) -> None:
        assert Percentage(value=Decimal("1.00")).as_ratio == Decimal("0.01")

    def test_allows_negative_roi(self) -> None:
        """Отрицательный ROI не превращается в ноль (09 §22)."""
        assert Percentage(value=Decimal("-3.5")).value < 0


class TestTimestamps:
    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ensure_utc(datetime(2026, 1, 1, 12, 0, 0))

    def test_converts_to_utc(self) -> None:
        moment = datetime.fromisoformat("2026-01-01T13:00:00+01:00")
        assert ensure_utc(moment) == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_model_field_normalizes(self) -> None:
        probe = _TimeProbe(moment=datetime.fromisoformat("2026-01-01T13:00:00+01:00"))
        assert probe.moment.tzinfo == UTC

    def test_model_field_rejects_naive(self) -> None:
        with pytest.raises(ValidationError):
            _TimeProbe(moment=datetime(2026, 1, 1))


class TestFingerprint:
    def test_is_independent_of_key_order(self) -> None:
        assert compute_fingerprint({"a": 1, "b": 2}) == compute_fingerprint({"b": 2, "a": 1})

    def test_nested_key_order_does_not_matter(self) -> None:
        left = compute_fingerprint({"outer": {"a": 1, "b": [{"x": 1, "y": 2}]}})
        right = compute_fingerprint({"outer": {"b": [{"y": 2, "x": 1}], "a": 1}})
        assert left == right

    def test_list_order_matters(self) -> None:
        assert compute_fingerprint({"a": [1, 2]}) != compute_fingerprint({"a": [2, 1]})

    def test_different_values_give_different_fingerprints(self) -> None:
        assert compute_fingerprint({"a": 1}) != compute_fingerprint({"a": 2})

    def test_rejects_float(self) -> None:
        with pytest.raises(ValueError, match="float"):
            compute_fingerprint({"a": 1.5})

    def test_is_deterministic_across_calls(self) -> None:
        payload = {"provider": "oneinch", "amount": "100.5"}
        assert compute_fingerprint(payload) == compute_fingerprint(payload)

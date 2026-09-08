"""Uniswap adapter.

⚠️ API contract NOT verified against live endpoint (решение D-3).
Classic и UniswapX сохраняются как разные routing modes.
"""

from monik.infrastructure.providers.uniswap.adapter import UniswapAdapter

__all__ = ["UniswapAdapter"]

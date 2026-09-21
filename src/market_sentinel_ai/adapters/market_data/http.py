from __future__ import annotations

import os
from collections.abc import Callable
from urllib.request import Request, urlopen

HttpTransport = Callable[[str], bytes]


class MarketDataProviderError(RuntimeError):
    pass


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "market-sentinel-ai/1.1"})
    timeout = _timeout_seconds()
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("MARKET_DATA_HTTP_TIMEOUT_SECONDS", "8")))
    except ValueError:
        return 8.0

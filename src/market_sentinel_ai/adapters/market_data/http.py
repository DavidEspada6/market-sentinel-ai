from __future__ import annotations

from collections.abc import Callable
from urllib.request import Request, urlopen

HttpTransport = Callable[[str], bytes]


class MarketDataProviderError(RuntimeError):
    pass


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "market-sentinel-ai/1.1"})
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()

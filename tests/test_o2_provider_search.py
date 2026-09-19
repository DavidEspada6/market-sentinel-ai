from __future__ import annotations

import json
import unittest

from market_sentinel_ai.adapters.market_data import YahooInstrumentSearchProvider
from market_sentinel_ai.domain.instruments import AssetClass


class O2ProviderSearchTests(unittest.TestCase):
    def test_yahoo_search_maps_provider_metadata(self) -> None:
        requested: list[str] = []
        payload = {
            "quotes": [
                {
                    "symbol": "XYZ",
                    "longname": "Example Holdings",
                    "quoteType": "EQUITY",
                    "fullExchangeName": "NASDAQ",
                    "currency": "USD",
                },
                {
                    "symbol": "XYZ-USD",
                    "shortname": "Example Coin",
                    "quoteType": "CRYPTOCURRENCY",
                    "exchange": "CCC",
                },
            ]
        }
        provider = YahooInstrumentSearchProvider(
            base_url="https://search.test",
            transport=lambda url: requested.append(url) or json.dumps(payload).encode(),
        )

        instruments = provider.search("example", limit=2)

        self.assertEqual([item.symbol for item in instruments], ["XYZ", "XYZ-USD"])
        self.assertEqual(instruments[0].name, "Example Holdings")
        self.assertEqual(instruments[1].asset_class, AssetClass.CRYPTO)
        self.assertIn("q=example", requested[0])

    def test_empty_query_is_rejected_without_network(self) -> None:
        provider = YahooInstrumentSearchProvider(transport=lambda _: b"{}")

        with self.assertRaisesRegex(ValueError, "query"):
            provider.search(" ")


if __name__ == "__main__":
    unittest.main()

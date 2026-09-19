# Order Flow And Regime-Aware Modeling

C4 keeps order-book access behind \`OrderBookProvider\`. The demo provider is deterministic for
tests; \`BinanceOrderBookProvider\` reads the public depth endpoint and requires no account key.
The endpoint and depth are configurable with:

\`\`\`powershell
MARKET_ORDER_BOOK_PROVIDER=binance
MARKET_ORDER_BOOK_BASE_URL=https://api.binance.com/api/v3/depth
MARKET_ORDER_BOOK_DEPTH=20
\`\`\`

The normalized features include bid/ask depth, spread, imbalance, imbalance delta, midprice,
microprice and microprice distance. These are inputs for research and alerts; they do not imply
that a level will remain available when an order would be placed.

\`AlignedMultiTimeframeFeatureEngine\` joins OHLCV features from larger timeframes only after the
last base candle in the larger bucket has closed. The joined feature names are prefixed with
the timeframe, for example \`15m_rolling_volatility_bps\`.

\`RegimeAwareEnsembleModel\` selects a weighted model set for low, normal or high volatility and
stores the selected regime in prediction metadata. It does not override risk gates or create
live orders.

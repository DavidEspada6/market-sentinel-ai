# News Context

C5 adds an RSS/Atom adapter without vendor credentials. The operational monitor now uses a
credential-free Google News RSS search by default, caches each symbol's headlines for five minutes,
and adds a small bounded headline sentiment score to the quantitative context. Set
`MARKET_NEWS_PROVIDER=none` to disable it, or use `MARKET_NEWS_PROVIDER=rss` with
`MARKET_NEWS_FEED_URLS` for explicit feeds:

```powershell
python -m market_sentinel_ai news-demo --provider rss --symbol SPY --feed-url https://example.com/feed.xml
```

The adapter normalizes title, source, publication time, link and summary. NewsContextBuilder adds
`sentiment_score` and `sentiment_label` from transparent headline keywords. The result is passed to
the local prediction context as a confidence adjustment and shown in the product explanation; it
cannot flip a signal by itself, bypass costs, or override hard risk limits. Astra remains an
optional second-stage explanation layer.

News is a confirmation input, not a promise of predictive power. Provider outages leave the model
running on market data and are marked as unavailable in the explanation.

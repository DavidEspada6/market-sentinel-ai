# News Context

C5 adds an RSS/Atom adapter without vendor credentials. Configure one or more feed URLs in code
or use the news command with an explicit feed URL:

```powershell
python -m market_sentinel_ai news-demo --provider rss --symbol SPY --feed-url https://example.com/feed.xml
```

The adapter normalizes title, source, publication time, link and summary. NewsContextBuilder then
keeps only symbol-matching items and produces a compact context with source labels. The result is
passed to Astra only after the quantitative signal gate; news never overrides hard risk limits.

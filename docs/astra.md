# GPT-6 Astra Context Layer

C5 adds news context and persistent cost auditing. Astra remains a gated reasoning layer, not the
continuous predictor.

## When Astra May Be Called

A signal must pass all gates:

- direction is LONG or SHORT,
- confidence is above `ASTRA_MIN_SIGNAL_CONFIDENCE`,
- daily request budget is not exhausted,
- equivalent reasoning is not already cached.
- the compact context fits the configured input-token limit,
- the estimated request cost fits the daily USD budget.

## Structured Output

The target schema contains:

- `thesis`,
- `invalidation`,
- `risk_notes`,
- `context_sources`.

This keeps the output auditable and prevents the reasoning layer from becoming free-form trading
advice. Responses are validated before they are returned to the application.

## Cost Control

The market loop stays local. Astra receives compact context only for selected signals. Cached input
and previous responses should be reused wherever possible. The usage ledger records request count,
cache hits, estimated input/output tokens and estimated cost in ASTRA_USAGE_PATH. The default C5
demo returns a deterministic local explanation when no OPENAI_API_KEY is set.

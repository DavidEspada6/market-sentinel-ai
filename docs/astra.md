# GPT-6 Astra Context Layer

R6 adds Astra as a gated reasoning layer, not as the continuous predictor.

## When Astra May Be Called

A signal must pass all gates:

- direction is LONG or SHORT,
- confidence is above `ASTRA_MIN_SIGNAL_CONFIDENCE`,
- daily request budget is not exhausted,
- equivalent reasoning is not already cached.

## Structured Output

The target schema contains:

- `thesis`,
- `invalidation`,
- `risk_notes`,
- `context_sources`.

This keeps the output auditable and prevents the reasoning layer from becoming free-form trading advice.

## Cost Control

The market loop stays local. Astra receives compact context only for selected signals. Cached input and previous responses should be reused wherever possible. The default R6 demo returns a deterministic local explanation when no `OPENAI_API_KEY` is set.


from __future__ import annotations


ASTRA_REASONING_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["thesis", "invalidation", "risk_notes", "context_sources"],
    "properties": {
        "thesis": {"type": "string"},
        "invalidation": {"type": "string"},
        "risk_notes": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
        },
        "context_sources": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
    },
}


# One-Shot Research

Use the main CLI for ad hoc research in the OpenClaw variant.

## Commands

| User intent | Command |
| --- | --- |
| `last30 "topic"` | `python3 "${SKILL_ROOT}/scripts/last30days.py" "topic" --emit=compact` |
| `last30 "topic" --quick` | `python3 "${SKILL_ROOT}/scripts/last30days.py" "topic" --quick --emit=compact` |
| `last30 "topic" --deep` | `python3 "${SKILL_ROOT}/scripts/last30days.py" "topic" --deep --emit=compact` |
| `last30 "topic" --json` | `python3 "${SKILL_ROOT}/scripts/last30days.py" "topic" --emit=json` |
| `last30 "topic" --store` | `python3 "${SKILL_ROOT}/scripts/last30days.py" "topic" --store --emit=compact` |

## Rules

- Use `--quick` for first-pass exploration.
- Use default depth unless the user explicitly wants maximum recall.
- Use `--emit=json` only when another tool or script needs structured output.
- Use `--store` only when the user wants the findings persisted into the OpenClaw history/watchlist flow.
- If the user restricts sources, pass `--search=` through exactly as requested.

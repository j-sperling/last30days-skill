# Briefing

Use the briefing CLI to synthesize accumulated watchlist findings.

## Commands

| User intent | Command |
| --- | --- |
| `briefing` | `python3 "${SKILL_ROOT}/scripts/briefing.py" generate` |
| `briefing weekly` or `briefing --weekly` | `python3 "${SKILL_ROOT}/scripts/briefing.py" generate --weekly` |
| `briefing show` | `python3 "${SKILL_ROOT}/scripts/briefing.py" show` |
| `briefing show --date YYYY-MM-DD` | `python3 "${SKILL_ROOT}/scripts/briefing.py" show --date YYYY-MM-DD` |

## Rules

- Read the JSON output and turn it into a concise human briefing.
- Lead with the highest-signal topic, not the oldest topic.
- Call out stale or failed topics explicitly.
- If there is no data yet, tell the user to add a watch topic or run the watchlist first.

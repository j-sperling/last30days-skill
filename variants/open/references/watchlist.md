# Watchlist

Use the watchlist CLI for persistent monitoring.

## Commands

| User intent | Command |
| --- | --- |
| `watch add "topic"` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" add "topic"` |
| `watch add "topic" --weekly` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" add "topic" --weekly` |
| `watch remove "topic"` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" remove "topic"` |
| `watch list` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" list` |
| `watch run-one "topic"` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" run-one "topic"` |
| `watch run-all` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" run-all` |
| `watch config budget 10.00` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" config budget 10.00` |
| `watch config delivery telegram` | `python3 "${SKILL_ROOT}/scripts/watchlist.py" config delivery telegram` |

## Rules

- If the user writes `watch "topic"` without `add`, treat it as `watch add`.
- After `add`, confirm the topic and schedule.
- After `run-one` or `run-all`, summarize new findings, updated findings, and any failures.
- If the user wants automation, explain that scheduling is external. In OpenClaw this is usually a cron, launchd job, or another always-on runner calling `watchlist.py run-all`.

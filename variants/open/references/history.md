# History

Use the SQLite history layer for stored findings.

## Commands

| User intent | Command |
| --- | --- |
| `history "topic"` | `python3 "${SKILL_ROOT}/scripts/store.py" query "topic"` |
| `history "topic" --since=7d` | `python3 "${SKILL_ROOT}/scripts/store.py" query "topic" --since 7d` |
| `history search "query"` | `python3 "${SKILL_ROOT}/scripts/store.py" search "query"` |
| `history trending` | `python3 "${SKILL_ROOT}/scripts/store.py" trending` |
| `history stats` | `python3 "${SKILL_ROOT}/scripts/store.py" stats` |

## Rules

- Prefer `search` when the user is looking for a phrase or concept across topics.
- Prefer `query` when the user is asking about one watched topic.
- Prefer `trending` for activity ranking and `stats` for system health.
- Summarize the structured output instead of dumping raw JSON unless the user asks for raw data.

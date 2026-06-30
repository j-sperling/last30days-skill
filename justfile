set shell := ["bash", "-euo", "pipefail", "-c"]

default:
  @just --list

sync:
  uv sync --locked

sync-check:
  uv sync --locked --check

python-version:
  uv run python -V

test:
  uv run pytest

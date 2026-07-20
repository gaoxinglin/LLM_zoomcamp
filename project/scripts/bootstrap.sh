#!/usr/bin/env sh
set -eu

uv sync --extra dev
uv run nz-ingest --seed-only --replace
uv run pytest
printf '%s\n' "Ready. Start the API with 'make api' and the UI with 'make ui'."

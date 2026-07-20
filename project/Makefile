.PHONY: install ingest seed api ui test lint evaluate compose-up compose-down

install:
	uv sync --extra dev

seed:
	uv run nz-ingest --seed-only --replace

ingest:
	uv run nz-ingest --max-per-topic 200 --replace

api:
	uv run uvicorn nz_open_data_assistant.api:app --reload

ui:
	uv run streamlit run app/streamlit_app.py

test:
	uv run pytest --cov=nz_open_data_assistant --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

evaluate:
	uv run nz-evaluate
	uv run nz-evaluate-answers

compose-up:
	docker compose up --build

compose-down:
	docker compose down

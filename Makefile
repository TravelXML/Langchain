.PHONY: install dev test lint format typecheck check clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .

format:
	black .
	ruff check --fix .

typecheck:
	mypy app

check: lint typecheck test

clean:
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache

.PHONY: install dev migrate seed test lint docker-build docker-up

install:
	uv sync

dev:
	uv run uvicorn src.restaurant_bot.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m scripts.seed_demo

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

docker-build:
	docker build -t restaurant-bot .

docker-up:
	docker compose up -d

FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "restaurant_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]

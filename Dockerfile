# Stage 1: Build
FROM python:3.12-slim AS builder

RUN pip install uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv pip install --system -r <(uv pip compile pyproject.toml)

# Stage 2: Runtime
FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "src.restaurant_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]

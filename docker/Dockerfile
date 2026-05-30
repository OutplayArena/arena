FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY nash_arena/ nash_arena/
COPY legacy_blotto/ legacy_blotto/
COPY games/ games/
COPY static/ static/
COPY migrations/ migrations/
COPY alembic.ini ./

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "nash_arena.main:app", "--host", "0.0.0.0", "--port", "8000"]

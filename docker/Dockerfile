FROM node:20-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY nash_arena/ nash_arena/
COPY legacy_blotto/ legacy_blotto/
COPY games/ games/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY frontend/site.yaml site.yaml
COPY --from=frontend /static/ static/
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "nash_arena.main:app", "--host", "0.0.0.0", "--port", "8000"]

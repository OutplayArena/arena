FROM node:20-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY games/ ../games/
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml pyproject.toml
COPY README.md ../README.md
COPY backend/nash_arena/ nash_arena/
COPY games/ games/
COPY backend/migrations/ migrations/
COPY backend/alembic.ini ./
COPY frontend/site.yaml site.yaml
COPY --from=frontend /backend/static/ static/
RUN pip install --no-cache-dir ./games && pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "nash_arena.main:app", "--host", "0.0.0.0", "--port", "8000"]

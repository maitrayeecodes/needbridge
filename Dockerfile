# Stage 1: build the website
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python server (it also serves the built website)
FROM python:3.13-slim
WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY backend ./backend
COPY data ./data
COPY --from=web /web/dist ./frontend/dist
ENV APP_ENV=production
ENV NEEDBRIDGE_HTTPS=1
CMD sh -c "alembic upgrade head && python -m backend.init_postgres && uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000}"
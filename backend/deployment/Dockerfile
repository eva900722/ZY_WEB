FROM node:24-alpine AS frontend_build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS web
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev fonts-wqy-zenhei && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend_build /frontend/dist /app/frontend/dist
RUN useradd --create-home app && mkdir -p /app/private_media /app/staticfiles && chown -R app:app /app
USER app
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]

FROM nginx:stable AS proxy
COPY --from=frontend_build /frontend/dist /srv/frontend
COPY backend/deployment/nginx.conf /etc/nginx/conf.d/default.conf

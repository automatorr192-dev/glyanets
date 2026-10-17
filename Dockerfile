# Мини-апп собирается на Node, в образ попадает только готовая статика: FastAPI отдаёт
# dist/, API записи и держит ботов в том же процессе. VITE_API=1 включает живой режим:
# мини-апп ходит в этот же сервер, а не держит записи в браузере.
FROM node:22-slim AS web
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts catalog.json ./
COPY src/ ./src/
COPY public/ ./public/
RUN VITE_API=1 npm run build

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py catalog.json alembic.ini ./
COPY migrations/ ./migrations/
COPY certs/ ./certs/
COPY --from=web /web/dist ./dist

RUN useradd --create-home app && mkdir -p /data && chown -R app /app /data
USER app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]

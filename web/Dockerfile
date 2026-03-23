# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY web/frontend/package.json web/frontend/package-lock.json* ./
RUN npm install
COPY web/frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.12-slim
WORKDIR /app

# Install git (needed for cloning repos).
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install anchormd from parent project.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir fastapi uvicorn aiosqlite httpx

# Copy web backend.
COPY web/ ./web/

# Copy built frontend into web/frontend/dist.
COPY --from=frontend-build /app/frontend/dist ./web/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]

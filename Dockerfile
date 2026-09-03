# ==========================================
# Stage 1: Build the React Frontend
# ==========================================
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

# Copy frontend dependency definitions
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source files and build static production assets
COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Setup Python Backend + Serve Both
# ==========================================
FROM python:3.12-slim AS final

WORKDIR /app

# Install system build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium headless browser & OS dependencies
RUN python -m playwright install --with-deps chromium

# Copy backend application source
COPY backend/app ./app

# Copy compiled frontend static files from Stage 1 into /app/static
COPY --from=frontend-builder /frontend/dist ./static

# Ensure persistent data directory exists
RUN mkdir -p /app/data

# Expose backend port
EXPOSE 8000

# Start Uvicorn web server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

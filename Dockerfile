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
# Use python:3.12-slim-bookworm (Debian 12 Stable) for official Playwright OS dependency support
FROM python:3.12-slim-bookworm AS final

WORKDIR /app

# Install system build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt .

# Install CPU-only PyTorch first (much smaller download size ~150MB vs ~900MB GPU version)
# and increase pip timeout to prevent network ReadTimeoutError
RUN pip install --no-cache-dir --default-timeout=1000 torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

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

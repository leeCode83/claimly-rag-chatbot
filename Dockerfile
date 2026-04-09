# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /install

# Install build dependencies if needed (e.g., for some python packages)
# RUN apt-get update && apt-get install -y build-essential

# Copy only requirements to leverage Docker cache
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Final Runtime Image
FROM python:3.12-slim

# Install runtime dependencies (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user for security
RUN addgroup --system --gid 1001 claimly && \
    adduser --system --uid 1001 --group claimly

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source code
# Note: we use --chown to ensure the non-root user can access these files
COPY --chown=claimly:claimly . .

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Expose the API port
EXPOSE 8000

# Switch to the non-root user
USER claimly

# Healthcheck for the FastAPI app
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default command (overridden in docker-compose for worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

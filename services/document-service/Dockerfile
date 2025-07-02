# Document Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY ../shared-libs/ ./shared-libs/

# Copy service source code
COPY src/ ./src/
COPY config/ ./config/

# Set Python path
ENV PYTHONPATH="/app:/app/src:/app/shared-libs"

# Create non-root user and temp directory
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /app/temp_downloads && chown -R appuser:appuser /app
USER appuser

# Health check (no HTTP endpoint, check process)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import psutil; exit(0 if any('main.py' in p.cmdline() for p in psutil.process_iter()) else 1)" || exit 1

# Run document service
CMD ["python", "src/main.py"]

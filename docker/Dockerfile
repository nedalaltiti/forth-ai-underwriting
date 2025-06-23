# Dockerfile for Forth AI Underwriting System

# Use a lightweight Python base image
FROM python:3.11-slim-buster

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy pyproject.toml and uv.lock (if you use uv lock)
COPY pyproject.toml ./pyproject.toml
# COPY uv.lock ./uv.lock

# Install dependencies using uv
RUN uv sync --system

# Copy the rest of the application code
COPY . .

# Set environment variables (consider using Docker secrets for sensitive info)
ENV PYTHONPATH=/app/src

# Expose the port the API runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "forth_ai_underwriting.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


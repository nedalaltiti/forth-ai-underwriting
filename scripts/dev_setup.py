#!/usr/bin/env python3
"""
Development environment setup script.
Sets up pre-commit hooks, environment files, and development tools.
"""

import os
import sys
import subprocess
from pathlib import Path
from loguru import logger


def setup_pre_commit():
    """Setup pre-commit hooks for code quality."""
    logger.info("Setting up pre-commit hooks...")
    
    pre_commit_config = """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements
      - id: check-docstring-first

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.287
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        always_run: true
        stages: [commit]
"""
    
    try:
        with open(".pre-commit-config.yaml", "w") as f:
            f.write(pre_commit_config.strip())
        
        # Install pre-commit hooks
        subprocess.run(["pre-commit", "install"], check=True)
        logger.info("Pre-commit hooks installed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to setup pre-commit: {e}")
        return False


def create_env_files():
    """Create environment configuration files."""
    logger.info("Creating environment files...")
    
    # Development .env file
    dev_env = """
# Forth AI Underwriting - Development Environment

# Application Configuration
FORTH_ENVIRONMENT=development
FORTH_DEBUG=true
FORTH_LOG_LEVEL=DEBUG
FORTH_SECRET_KEY=dev-secret-key-change-in-production

# Database Configuration
FORTH_DATABASE_URL=sqlite:///./dev_forth_underwriting.db

# Redis Configuration (optional for development)
# FORTH_REDIS_URL=redis://localhost:6379/0

# Forth API Configuration
FORTH_API_BASE_URL=https://your-forth-instance.com/api
FORTH_API_KEY=your-forth-api-key-here
# FORTH_WEBHOOK_SECRET=your-webhook-secret

# AI/ML Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=4000
OPENAI_TEMPERATURE=0.1

# Azure Form Recognizer (optional)
# AZURE_FORM_RECOGNIZER_ENDPOINT=https://your-instance.cognitiveservices.azure.com/
# AZURE_FORM_RECOGNIZER_KEY=your-azure-form-recognizer-key

# Microsoft Teams Bot Configuration
MICROSOFT_APP_ID=your-teams-app-id
MICROSOFT_APP_PASSWORD=your-teams-app-password

# Rate Limiting
FORTH_RATE_LIMIT_ENABLED=false

# Feature Flags
FORTH_ENABLE_CACHING=true
FORTH_ENABLE_AI_PARSING=true
FORTH_ENABLE_AZURE_FORM_RECOGNIZER=false
FORTH_ENABLE_AUDIT_LOGGING=true
FORTH_ENABLE_FEEDBACK_COLLECTION=true

# Development Settings
FORTH_CORS_ORIGINS=*
FORTH_VALIDATION_CACHE_TTL_HOURS=1
FORTH_CACHE_TTL_SECONDS=60
"""
    
    # Production .env.example file
    prod_env_example = """
# Forth AI Underwriting - Production Environment Example
# Copy this file to .env and fill in your actual values

# Application Configuration
FORTH_ENVIRONMENT=production
FORTH_DEBUG=false
FORTH_LOG_LEVEL=INFO
FORTH_SECRET_KEY=your-strong-secret-key-here

# Database Configuration
FORTH_DATABASE_URL=postgresql://user:password@localhost:5432/forth_underwriting
FORTH_DATABASE_POOL_SIZE=20
FORTH_DATABASE_MAX_OVERFLOW=30

# Redis Configuration
FORTH_REDIS_URL=redis://localhost:6379/0
FORTH_REDIS_PASSWORD=your-redis-password

# Forth API Configuration
FORTH_API_BASE_URL=https://your-forth-instance.com/api
FORTH_API_KEY=your-production-forth-api-key
FORTH_WEBHOOK_SECRET=your-webhook-secret
FORTH_API_TIMEOUT=30
FORTH_API_RETRIES=3

# AI/ML Configuration
OPENAI_API_KEY=your-production-openai-api-key
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=4000
OPENAI_TEMPERATURE=0.1
OPENAI_TIMEOUT=60

# Azure Form Recognizer
AZURE_FORM_RECOGNIZER_ENDPOINT=https://your-instance.cognitiveservices.azure.com/
AZURE_FORM_RECOGNIZER_KEY=your-azure-form-recognizer-key
AZURE_FORM_RECOGNIZER_MODEL_ID=prebuilt-document

# Microsoft Teams Bot Configuration
MICROSOFT_APP_ID=your-production-teams-app-id
MICROSOFT_APP_PASSWORD=your-production-teams-app-password

# Security & CORS
FORTH_CORS_ORIGINS=https://your-domain.com,https://teams.microsoft.com

# Rate Limiting
FORTH_RATE_LIMIT_ENABLED=true
FORTH_RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Monitoring
FORTH_METRICS_ENABLED=true
SENTRY_DSN=your-sentry-dsn

# Performance
FORTH_MAX_FILE_SIZE_MB=50
FORTH_DOCUMENT_PROCESSING_TIMEOUT=300
FORTH_VALIDATION_TIMEOUT_SECONDS=120

# Background Tasks
FORTH_CELERY_BROKER_URL=redis://localhost:6379/1
FORTH_CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Feature Flags
FORTH_ENABLE_CACHING=true
FORTH_ENABLE_AI_PARSING=true
FORTH_ENABLE_AZURE_FORM_RECOGNIZER=true
FORTH_ENABLE_AUDIT_LOGGING=true
FORTH_ENABLE_FEEDBACK_COLLECTION=true
"""
    
    try:
        # Create configs directory if it doesn't exist
        configs_dir = Path("configs")
        configs_dir.mkdir(exist_ok=True)
        
        # Write development .env file
        dev_env_path = configs_dir / ".env"
        if not dev_env_path.exists():
            with open(dev_env_path, "w") as f:
                f.write(dev_env.strip())
            logger.info(f"Created development environment file: {dev_env_path}")
        else:
            logger.info("Development .env file already exists")
        
        # Write production .env.example file
        prod_env_path = configs_dir / ".env.example"
        with open(prod_env_path, "w") as f:
            f.write(prod_env_example.strip())
        logger.info(f"Created production environment example: {prod_env_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create environment files: {e}")
        return False


def setup_vscode_settings():
    """Setup VS Code settings for the project."""
    logger.info("Setting up VS Code configuration...")
    
    vscode_settings = {
        "python.defaultInterpreterPath": ".venv/bin/python",
        "python.testing.pytestEnabled": True,
        "python.testing.pytestArgs": ["tests"],
        "python.linting.enabled": True,
        "python.linting.ruffEnabled": True,
        "python.formatting.provider": "black",
        "python.formatting.blackArgs": ["--line-length=88"],
        "editor.formatOnSave": True,
        "editor.codeActionsOnSave": {
            "source.organizeImports": True
        },
        "files.exclude": {
            "**/__pycache__": True,
            "**/*.pyc": True,
            ".mypy_cache": True,
            ".pytest_cache": True,
            "htmlcov": True,
            ".coverage": True
        }
    }
    
    vscode_launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "FastAPI Development Server",
                "type": "python",
                "request": "launch",
                "module": "uvicorn",
                "args": [
                    "forth_ai_underwriting.api.main:app",
                    "--host", "0.0.0.0",
                    "--port", "8000",
                    "--reload"
                ],
                "console": "integratedTerminal",
                "envFile": "${workspaceFolder}/configs/.env"
            },
            {
                "name": "Run Tests",
                "type": "python",
                "request": "launch",
                "module": "pytest",
                "args": ["tests/", "-v"],
                "console": "integratedTerminal"
            }
        ]
    }
    
    try:
        import json
        
        # Create .vscode directory
        vscode_dir = Path(".vscode")
        vscode_dir.mkdir(exist_ok=True)
        
        # Write settings.json
        with open(vscode_dir / "settings.json", "w") as f:
            json.dump(vscode_settings, f, indent=2)
        
        # Write launch.json
        with open(vscode_dir / "launch.json", "w") as f:
            json.dump(vscode_launch, f, indent=2)
        
        logger.info("VS Code configuration created")
        return True
    except Exception as e:
        logger.error(f"Failed to setup VS Code settings: {e}")
        return False


def create_makefile():
    """Create a comprehensive Makefile for development tasks."""
    logger.info("Creating Makefile...")
    
    makefile_content = """
# Forth AI Underwriting System - Development Makefile

.PHONY: help install dev-install test lint format clean build run docker-build docker-run

# Default target
help:
\t@echo "Available commands:"
\t@echo "  install       Install production dependencies"
\t@echo "  dev-install   Install development dependencies"
\t@echo "  test          Run tests"
\t@echo "  test-cov      Run tests with coverage"
\t@echo "  lint          Run linting"
\t@echo "  format        Format code"
\t@echo "  type-check    Run type checking"
\t@echo "  clean         Clean build artifacts"
\t@echo "  build         Build the application"
\t@echo "  run           Run the development server"
\t@echo "  run-prod      Run the production server"
\t@echo "  db-init       Initialize database"
\t@echo "  db-reset      Reset database"
\t@echo "  docker-build  Build Docker image"
\t@echo "  docker-run    Run Docker container"
\t@echo "  setup-dev     Setup development environment"

# Installation
install:
\tuv sync --no-dev

dev-install:
\tuv sync
\tpre-commit install

# Testing
test:
\tuv run pytest

test-cov:
\tuv run pytest --cov=forth_ai_underwriting --cov-report=html --cov-report=term

test-watch:
\tuv run pytest --watch

# Code quality
lint:
\tuv run ruff check src tests
\tuv run mypy src

format:
\tuv run black src tests
\tuv run ruff check --fix src tests

type-check:
\tuv run mypy src

# Cleaning
clean:
\tfind . -type f -name "*.pyc" -delete
\tfind . -type d -name "__pycache__" -delete
\trm -rf htmlcov
\trm -rf .coverage
\trm -rf .pytest_cache
\trm -rf .mypy_cache
\trm -rf dist
\trm -rf build
\trm -rf *.egg-info

# Building
build:
\tuv build

# Running
run:
\tuv run python -m uvicorn forth_ai_underwriting.api.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
\tuv run python -m uvicorn forth_ai_underwriting.api.main:app --host 0.0.0.0 --port 8000

# Database
db-init:
\tuv run python scripts/init_db.py

db-reset:
\trm -f *.db
\tuv run python scripts/init_db.py

# Docker
docker-build:
\tdocker build -t forth-ai-underwriting:latest -f docker/Dockerfile .

docker-run:
\tdocker run -d -p 8000:8000 --env-file configs/.env --name forth-ai-underwriting forth-ai-underwriting:latest

docker-stop:
\tdocker stop forth-ai-underwriting || true
\tdocker rm forth-ai-underwriting || true

# Development setup
setup-dev:
\tuv run python scripts/dev_setup.py
\tmake db-init
"""
    
    try:
        with open("Makefile", "w") as f:
            f.write(makefile_content.strip())
        logger.info("Makefile created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create Makefile: {e}")
        return False


def main():
    """Main setup function."""
    logger.info("Starting development environment setup...")
    
    tasks = [
        ("Environment files", create_env_files),
        ("Pre-commit hooks", setup_pre_commit),
        ("VS Code settings", setup_vscode_settings),
        ("Makefile", create_makefile),
    ]
    
    success_count = 0
    for task_name, task_func in tasks:
        logger.info(f"Setting up {task_name}...")
        if task_func():
            success_count += 1
            logger.info(f"✓ {task_name} setup completed")
        else:
            logger.error(f"✗ {task_name} setup failed")
    
    logger.info(f"Development setup completed: {success_count}/{len(tasks)} tasks successful")
    
    if success_count == len(tasks):
        logger.info("🎉 Development environment is ready!")
        logger.info("Next steps:")
        logger.info("1. Update configs/.env with your actual API keys")
        logger.info("2. Run 'make db-init' to initialize the database")
        logger.info("3. Run 'make run' to start the development server")
        return True
    else:
        logger.error("Some setup tasks failed. Please check the logs above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
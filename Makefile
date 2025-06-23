
# Common development commands

.PHONY: install test run clean

install:
	@echo "Installing dependencies..."
	uv sync

test:
	@echo "Running tests..."
	uv run pytest

run:
	@echo "Starting FastAPI application..."
	uv run uvicorn forth_ai_underwriting.api.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .uv/
	rm -rf .pytest_cache/
	rm -f .coverage



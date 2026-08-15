.PHONY: help install dev test run docker-build docker-up migrate clean

help:
	@echo "install       Install runtime and dev dependencies into the active env"
	@echo "run           Start the development server on http://127.0.0.1:5000"
	@echo "test          Run the test suite"
	@echo "migrate       Import the Supabase data into data/badeel.db"
	@echo "docker-build  Build the production image"
	@echo "docker-up     Run the production image via docker compose"
	@echo "clean         Remove caches and build artefacts"

install:
	pip install -e '.[dev]'

run:
	FLASK_APP=wsgi:app flask run --debug

test:
	pytest -q

migrate:
	pip install -e '.[migrate]'
	python scripts/migrate_from_supabase.py

docker-build:
	docker build -t badeel:latest .

docker-up:
	docker compose up --build

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache *.egg-info build dist

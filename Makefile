.PHONY: bootstrap-dev lint format typecheck test build compose-up compose-down

bootstrap-dev:
	@echo "Host bootstrap handled outside (apt + docker)."

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app worker tests

test:
	pytest -q

build:
	docker compose build --no-cache

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down -v

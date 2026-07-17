.PHONY: install test run lint docker

install:
	python -m pip install -e ".[dev]"

test:
	pytest

run:
	uvicorn services.api.app.main:app --reload

lint:
	ruff check .

docker:
	docker compose up --build

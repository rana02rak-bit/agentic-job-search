.PHONY: up down logs test seed

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm backend pytest

seed:
	docker compose run --rm backend python -m app.seed


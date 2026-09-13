install:
	python -m pip install -e ".[dev]"

run:
	uvicorn backend.main:app --reload

test:
	pytest -q

lint:
	ruff check backend tests

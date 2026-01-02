.PHONY: install dev test clean

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

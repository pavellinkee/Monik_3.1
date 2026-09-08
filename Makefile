# Monik — developer commands.
# Все команды используют uv; UV_HTTP_TIMEOUT увеличен из-за медленных загрузок с PyPI.

export UV_HTTP_TIMEOUT ?= 180

PYTHON_VERSION ?= 3.12
VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: help install lint format format-check typecheck test test-fast ci clean check-architecture-docs

help:
	@echo "make install            - создать venv и установить зависимости"
	@echo "make lint               - ruff check"
	@echo "make format             - ruff format"
	@echo "make format-check       - ruff format --check"
	@echo "make typecheck          - mypy --strict"
	@echo "make test               - pytest (весь набор, кроме external)"
	@echo "make ci                 - lint + format-check + typecheck + test"
	@echo "make clean              - удалить venv и кэши"

install:
	uv sync --python $(PYTHON_VERSION) --group dev

lint:
	$(VENV)/bin/ruff check monik tests scripts conftest.py

format:
	$(VENV)/bin/ruff format monik tests scripts conftest.py

format-check:
	$(VENV)/bin/ruff format --check monik tests

typecheck:
	$(VENV)/bin/mypy monik

test:
	$(PY) -m pytest -m "not external"

test-fast:
	$(PY) -m pytest -m "not external" tests/unit

check-architecture-docs:
	@if ! git diff --quiet -- docs/architecture CLAUDE.md; then \
		echo "ОШИБКА: изменены защищённые файлы (docs/architecture/ или CLAUDE.md)"; \
		git diff --stat -- docs/architecture CLAUDE.md; \
		exit 1; \
	fi
	@echo "docs/architecture/ и CLAUDE.md не изменены"

ci: lint format-check typecheck test check-architecture-docs

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

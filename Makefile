.PHONY: help install install-dev test test-cov lint format format-check typecheck integration regression benchmark clean

help:
	@echo "PRISM Development & CI/CD Commands"
	@echo "=================================="
	@echo "  install        Install PRISM in editable mode"
	@echo "  install-dev    Install PRISM with development & testing dependencies"
	@echo "  test           Run Python unit tests via pytest"
	@echo "  test-cov       Run unit tests with terminal coverage report"
	@echo "  lint           Check code style and linting issues via ruff"
	@echo "  format         Auto-format code via ruff"
	@echo "  format-check   Check code formatting without modifying files"
	@echo "  typecheck      Run static type analysis via mypy"
	@echo "  integration    Run MeTTa PRISM integration suite (requires PeTTa)"
	@echo "  regression     Run upstream PLN rule regression suite (requires PeTTa)"
	@echo "  benchmark      Run fast synthetic chain benchmark smoke test"
	@echo "  clean          Remove build artifacts, caches, and temporary files"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python3 -m pytest tests/unit/

test-cov:
	python3 -m pytest --cov=. --cov-report=term-missing --cov-report=xml tests/unit/

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	mypy

integration:
	@if [ -d "../PeTTa" ]; then \
		cd ../PeTTa && \
		sh run.sh ../prism/tests/integration/test_depth_penalty.metta && \
		sh run.sh ../prism/tests/integration/test_stage0_metta.metta && \
		sh run.sh ../prism/tests/integration/test_fallback.metta && \
		sh run.sh ../prism/tests/integration/test_prism_hook.metta; \
	else \
		echo "Error: PeTTa directory not found at ../PeTTa"; exit 1; \
	fi

regression:
	@if [ -d "../PeTTa" ]; then \
		cd ../PeTTa && \
		for f in ./repos/PLN/ruletests/*.metta; do echo -n "$$f: "; sh run.sh "$$f" | grep "should" || exit 1; done; \
	else \
		echo "Error: PeTTa directory not found at ../PeTTa"; exit 1; \
	fi

benchmark:
	PYTHONPATH=..:$${PYTHONPATH} python3 -m prism.benchmarks.run_benchmark --depths 5 --distractors 0 --repeats 1 --max-steps 80 --guided

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .coverage coverage.xml dist build *.egg-info

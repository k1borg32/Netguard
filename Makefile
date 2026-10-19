# Windows: install make once (winget install ezwinports.make) and run it from Git Bash,
# or copy the command under a target and run it directly.
.PHONY: help setup up down reset logs ps sim perf scale kill-one test test-unit test-int test-stack coverage lint format trace

ifeq ($(OS),Windows_NT)
VENV_BIN := .venv/Scripts
else
VENV_BIN := .venv/bin
endif

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'

setup:           ## First-time: create .env and a local venv with dev tools
	@test -f .env || cp .env.example .env
	python -m venv .venv && $(VENV_BIN)/python -m pip install -e "libs/common[kafka]" -r requirements-dev.txt

up:              ## Start the whole platform
	@test -f .env || cp .env.example .env
	docker compose up -d --build

down:            ## Stop everything (keeps DB data)
	docker compose --profile sim --profile debug down

reset:           ## Stop and wipe DB + broker data
	docker compose --profile sim --profile debug down -v

logs:            ## Follow logs of all services
	docker compose logs -f --tail=50

ps:
	docker compose ps

sim:             ## Run simulator at normal rate (Ctrl+C to stop)
	docker compose --profile sim run --rm simulator

perf:            ## NFR01 load: 5000 flows/s for 5 min
	docker compose --profile sim run --rm -e SIM_RATE=5000 -e SIM_DURATION_S=300 simulator

scale:           ## NFR03: three processor instances (--no-deps: don't touch DB/broker)
	docker compose up -d --no-deps --scale processor=3 processor

kill-one:        ## NFR04: kill one processor instance mid-run
	docker kill $$(docker compose ps -q processor | head -1)

trace:           ## F15: follow one event, e.g. make trace ID=<trace_id>
	@test -n "$(ID)" || (echo "usage: make trace ID=<trace_id>" && exit 1)
	docker compose logs --no-color | grep $(ID)

test:            ## Unit + API integration tests; starts a disposable Docker database
	pytest -q

test-unit:       ## Unit tests only, without Docker
	pytest -m "not integration" -q

test-int:        ## API integration tests; database starts and stops automatically
	pytest services/api/tests/integration -q

test-stack:      ## Full-stack smoke tests (needs `make up` first)
	pytest -m stack -q

coverage:        ## Unit tests with a coverage report
	pytest -m "not integration" -q --cov --cov-report=term-missing

lint:            ## Lint + formatting check (same as CI)
	ruff check .
	ruff format --check .

format:          ## Apply ruff formatting
	ruff format .

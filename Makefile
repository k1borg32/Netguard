# Windows users: run these from Git Bash or WSL, or copy the command after the colon.
.PHONY: help setup up down reset logs ps sim perf scale kill-one test test-unit test-int lint trace

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'

setup:           ## First-time: create .env and a local venv with dev tools
	@test -f .env || cp .env.example .env
	python -m venv .venv && .venv/bin/pip install -e "libs/common[kafka]" -r requirements-dev.txt

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

scale:           ## NFR03: three processor instances
	docker compose up -d --scale processor=3

kill-one:        ## NFR04: kill one processor instance mid-run
	docker kill $$(docker compose ps -q processor | head -1)

trace:           ## F15: follow one event, e.g. make trace ID=<trace_id>
	docker compose logs --no-color | grep $(ID)

test: test-unit  ## Run unit tests

test-unit:
	pytest -m "not integration" -q

test-int:        ## Integration tests (needs `make up` first)
	pytest -m integration -q

lint:
	ruff check .

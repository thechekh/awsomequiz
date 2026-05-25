# AWSomeQuiz local dev orchestration.
# Cross-platform: works with GNU make on Linux/Mac/git-bash. Windows users
# can also use ./dev.ps1, which mirrors these targets.

.PHONY: help dev db-up db-down db-status db-reset migrate-sqlite load-flashcards app app-docker app-stop lint format clean

help:
	@echo "AWSomeQuiz dev targets:"
	@echo ""
	@echo "  make dev             One command: start Supabase + reset DB + import SQLite + run app in Docker."
	@echo ""
	@echo "  make db-up           Start local Supabase stack (Postgres + Auth + Studio + Inbucket)."
	@echo "  make db-down         Stop the Supabase stack."
	@echo "  make db-status       Show local Supabase URLs / keys (use to populate .env)."
	@echo "  make db-reset        Drop the local DB and re-apply migrations + seed."
	@echo "  make migrate-sqlite  Import dumps/CLF-C02.db into the local Supabase Postgres."
	@echo "  make load-flashcards Import questions/*.csv into flashcard_decks/flashcards."
	@echo ""
	@echo "  make app             Run Streamlit on the host (uv-managed Python, fast for iterating)."
	@echo "  make app-docker      Run Streamlit inside Docker (mirrors prod, slower to start)."
	@echo "  make app-stop        Stop the Streamlit container."
	@echo ""
	@echo "  make lint            ruff check"
	@echo "  make format          ruff format"
	@echo "  make clean           Stop Supabase + the app container."

# One-command bootstrap.
dev: db-up db-reset migrate-sqlite load-flashcards app-docker
	@echo ""
	@echo "AWSomeQuiz is running. Open http://localhost:8501"
	@echo "Studio:   http://localhost:54323"
	@echo "Inbucket: http://localhost:54324  (catches auth emails)"

db-up:
	supabase start

db-down:
	supabase stop

db-status:
	supabase status

# `supabase db reset` drops the local DB, re-runs migrations in supabase/migrations/,
# then runs supabase/seed.sql. Use this after any schema change.
db-reset:
	supabase db reset

migrate-sqlite:
	uv run python scripts/migrate_sqlite_to_supabase.py \
		--sqlite dumps/CLF-C02.db \
		--certification-code CLF-C02

load-flashcards:
	uv run python scripts/load_flashcards.py \
		--certification-code CLF-C02

app:
	uv run streamlit run streamlit_app.py

app-docker:
	docker compose up --build -d streamlit

app-stop:
	docker compose down

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean: app-stop db-down
	@echo "Stopped Supabase + Streamlit container."

# AWSomeQuiz dev orchestration for Windows / PowerShell.
# Mirrors the Makefile targets. Run with: .\dev.ps1 <target>
# Targets: dev | db-up | db-down | db-status | db-reset | migrate-sqlite |
#          app | app-docker | app-stop | lint | format | clean

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help','dev','db-up','db-down','db-status','db-reset','migrate-sqlite','load-flashcards','app','app-docker','app-stop','lint','format','clean')]
    [string]$Target = 'help'
)

$ErrorActionPreference = 'Stop'

function Require-Cmd {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name not found on PATH. $InstallHint"
        exit 1
    }
}

function Cmd-Help {
    @"
AWSomeQuiz dev targets (PowerShell):

  .\dev.ps1 dev             One command: start Supabase + reset DB + import SQLite + run app in Docker.

  .\dev.ps1 db-up           Start local Supabase stack.
  .\dev.ps1 db-down         Stop the Supabase stack.
  .\dev.ps1 db-status       Show local Supabase URLs / keys (use to populate .env).
  .\dev.ps1 db-reset        Drop the local DB and re-apply migrations + seed.
  .\dev.ps1 migrate-sqlite  Import dumps/CLF-C02.db into the local Supabase Postgres.
  .\dev.ps1 load-flashcards Import questions/*.csv into flashcard_decks/flashcards.

  .\dev.ps1 app             Run Streamlit on the host (uv-managed Python).
  .\dev.ps1 app-docker      Run Streamlit inside Docker.
  .\dev.ps1 app-stop        Stop the Streamlit container.

  .\dev.ps1 lint            ruff check
  .\dev.ps1 format          ruff format
  .\dev.ps1 clean           Stop Supabase + the app container.

Prereqs (install once):
  scoop install supabase    # or via npm / brew
  Docker Desktop
  uv (https://docs.astral.sh/uv/)
"@
}

function Cmd-DbUp        { Require-Cmd supabase 'Install: scoop install supabase'; supabase start }
function Cmd-DbDown      { supabase stop }
function Cmd-DbStatus    { supabase status }
function Cmd-DbReset     { supabase db reset }
function Cmd-MigrateSql  { uv run python scripts/migrate_sqlite_to_supabase.py --sqlite dumps/CLF-C02.db --certification-code CLF-C02 }
function Cmd-LoadFlash   { uv run python scripts/load_flashcards.py --certification-code CLF-C02 }
function Cmd-App         { uv run streamlit run streamlit_app.py }
function Cmd-AppDocker   { docker compose up --build -d streamlit }
function Cmd-AppStop     { docker compose down }
function Cmd-Lint        { uv run ruff check . }
function Cmd-Format      { uv run ruff format . }

function Cmd-Dev {
    Cmd-DbUp
    Cmd-DbReset
    Cmd-MigrateSql
    Cmd-LoadFlash
    Cmd-AppDocker
    Write-Host ""
    Write-Host "AWSomeQuiz is running. Open http://localhost:8501" -ForegroundColor Green
    Write-Host "Studio:   http://localhost:54323"
    Write-Host "Inbucket: http://localhost:54324  (catches auth emails)"
}

function Cmd-Clean {
    try { Cmd-AppStop } catch { }
    try { Cmd-DbDown }  catch { }
    Write-Host "Stopped Supabase + Streamlit container."
}

switch ($Target) {
    'help'           { Cmd-Help }
    'dev'            { Cmd-Dev }
    'db-up'          { Cmd-DbUp }
    'db-down'        { Cmd-DbDown }
    'db-status'      { Cmd-DbStatus }
    'db-reset'       { Cmd-DbReset }
    'migrate-sqlite' { Cmd-MigrateSql }
    'load-flashcards' { Cmd-LoadFlash }
    'app'            { Cmd-App }
    'app-docker'     { Cmd-AppDocker }
    'app-stop'       { Cmd-AppStop }
    'lint'           { Cmd-Lint }
    'format'         { Cmd-Format }
    'clean'          { Cmd-Clean }
}

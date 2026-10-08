# ClipFarm : installation de l'environnement de dev sur Windows (tout gratuit)
# Lancer depuis la racine du projet :
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
# Options : -SkipDocker (pas de Postgres pour l'instant), -Model qwen3:14b (si ta carte a 12 Go+)

param(
    [switch]$SkipDocker,
    [string]$Model = "qwen3:8b"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Ensure($cmd, $wingetId) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        Write-Host "  ok  $cmd"
        return
    }
    Write-Host "  ... installation $wingetId"
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements | Out-Host
    Refresh-Path
}

Write-Host "1/7 Outils"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "winget introuvable : installe 'App Installer' depuis le Microsoft Store" }
Ensure git    "Git.Git"
Ensure node   "OpenJS.NodeJS.LTS"
Ensure uv     "astral-sh.uv"
Ensure ffmpeg "Gyan.FFmpeg"
Ensure ollama "Ollama.Ollama"
if (-not $SkipDocker) { Ensure docker "Docker.DockerDesktop" }

$missing = @("git", "node", "uv", "ffmpeg", "ollama") | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
if ($missing) {
    Write-Host "Installe mais pas encore visible : $($missing -join ', '). Ferme PowerShell, rouvre-le et relance ce script."
    exit 0
}

Write-Host "2/7 GPU"
$gpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | Out-Host
    $gpu = $true
} else {
    Write-Host "  pas de GPU NVIDIA detecte : tout tournera sur le processeur (beaucoup plus lent)"
}

Write-Host "3/7 Fichier .env"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    if (-not $gpu) {
        (Get-Content ".env") -replace "WHISPER_DEVICE=cuda", "WHISPER_DEVICE=cpu" -replace "WHISPER_COMPUTE_TYPE=float16", "WHISPER_COMPUTE_TYPE=int8" | Set-Content ".env"
    }
    Write-Host "  .env cree"
} else {
    Write-Host "  .env deja present, on n'y touche pas"
}

Write-Host "4/7 Python 3.12 + dependances du moteur (torch CUDA, WhisperX, Demucs, yt-dlp) : long la premiere fois"
Push-Location engine
uv python install 3.12
uv sync --python 3.12 --extra ai --extra dev
Pop-Location

Write-Host "5/7 Modele LLM local ($Model)"
ollama pull $Model

Write-Host "6/7 Node / pnpm (pour le front, phase 3)"
corepack enable 2>$null
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { npm install -g pnpm | Out-Host }

if (-not $SkipDocker) {
    Write-Host "7/7 Postgres (Docker Desktop doit etre lance)"
    try { docker compose -f infra/docker-compose.yml up -d | Out-Host } catch { Write-Host "  Docker pas pret : lance Docker Desktop puis : docker compose -f infra/docker-compose.yml up -d" }
} else {
    Write-Host "7/7 Docker ignore (-SkipDocker)"
}

Write-Host ""
Write-Host "Verification : tests du moteur"
Push-Location engine
uv run pytest -q
Pop-Location

Write-Host ""
Write-Host "Termine. Test reel :"
Write-Host '  cd engine'
Write-Host '  uv run python -m clipfarm_engine run "C:\chemin\video.mp4" --layout facecam_top --cam 0.739,0.083,0.246,0.245'

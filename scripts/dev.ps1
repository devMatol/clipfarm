# ClipFarm : lancement de tout l'environnement de dev en une commande
# Usage : powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1. Rafraîchir le PATH pour trouver uv, ffmpeg, pnpm, docker
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
$env:PYTHONPATH = "$root\api;$root\engine"
$env:DATABASE_URL = "postgresql://clipfarm:clipfarm@localhost:5432/clipfarm"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " ClipFarm - Environnement de développement" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 2. Démarrage de Docker Desktop ou Postgres portable
Write-Host "`n[1/4] Vérification de Postgres (port 5432)..." -ForegroundColor Yellow

$pgReady = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 5432)
    if ($tcp.Connected) {
        $pgReady = $true
        $tcp.Close()
    }
} catch {}

if (-not $pgReady) {
    # Vérifier si postgres portable existe dans infra/pgsql
    $pgExe = "$root\infra\pgsql\pgsql\bin\postgres.exe"
    $pgData = "$root\infra\pgsql\data"
    if ((Test-Path $pgExe) -and (Test-Path $pgData)) {
        Write-Host "  Démarrage de Postgres local ($pgExe)..." -ForegroundColor Gray
        Start-Process -FilePath $pgExe -ArgumentList "-D", "`"$pgData`"" -WindowStyle Hidden
    } else {
        # Sinon tenter Docker
        $dockerReady = $false
        try {
            $null = docker info 2>&1
            if ($LASTEXITCODE -eq 0) { $dockerReady = $true }
        } catch {}

        if (-not $dockerReady) {
            Write-Host "  Démarrage de Docker Desktop en cours..." -ForegroundColor Gray
            $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
            if (Test-Path $dockerExe) {
                Start-Process $dockerExe
            }
            $attempts = 0
            while (-not $dockerReady -and $attempts -lt 30) {
                Start-Sleep -Seconds 2
                $attempts++
                try {
                    $null = docker info 2>&1
                    if ($LASTEXITCODE -eq 0) { $dockerReady = $true }
                } catch {}
                Write-Host "  Attente de Docker daemon ($attempts/30)..." -ForegroundColor DarkGray
            }
        }

        if ($dockerReady) {
            Write-Host "  Démarrage du conteneur Postgres..." -ForegroundColor Gray
            docker compose -f infra/docker-compose.yml up -d | Out-Null
        }
    }

    # Attente de la disponibilité de Postgres
    Write-Host "  Attente de la disponibilité de Postgres (port 5432)..." -ForegroundColor Gray
    $pgAttempts = 0
    while (-not $pgReady -and $pgAttempts -lt 25) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", 5432)
            if ($tcp.Connected) {
                $pgReady = $true
                $tcp.Close()
            }
        } catch {
            Start-Sleep -Seconds 1
            $pgAttempts++
        }
    }
}

if (-not $pgReady) {
    Write-Host "  ERREUR: Postgres ne répond pas sur le port 5432." -ForegroundColor Red
    exit 1
}
Write-Host "  Postgres opérationnel." -ForegroundColor Green

# 3. Application du schéma Procrastinate
Write-Host "`n[2/4] Application du schéma Procrastinate sur Postgres..." -ForegroundColor Yellow
uv run python -c "from clipfarm_api.queue import procrastinate_app;
with procrastinate_app.open():
    procrastinate_app.schema_manager.apply_schema()
print('  Schéma appliqué.')"

# 4. Démarrage de l'API FastAPI et du Worker via uv run
Write-Host "`n[3/4] Démarrage de l'API et du Worker GPU..." -ForegroundColor Yellow
$apiProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$root'; `$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User'); uv run python -m clipfarm_api.server" -PassThru
$workerProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$root'; `$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User'); uv run python -m clipfarm_api.worker" -PassThru

# 5. Démarrage du frontend Web
Write-Host "`n[4/4] Démarrage du frontend Web (http://localhost:3000)..." -ForegroundColor Yellow
Write-Host "`nClipFarm est prêt !" -ForegroundColor Green
Write-Host "Interface Web : http://localhost:3000" -ForegroundColor Cyan
Write-Host "Documentation API : http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Pour arrêter : ferme les fenêtres PowerShell ouvertes." -ForegroundColor Gray

cd "$root\apps\web"
pnpm dev

<#
.SYNOPSIS
    Script de test manuel sécurisé pour valider la publication réelle d'un clip sur YouTube en mode privé ou non répertorié.

.DESCRIPTION
    Ce script vérifie la présence d'un compte connecté, permet la prévisualisation des métadonnées,
    exige une confirmation explicite de l'utilisateur, et soumet la vidéo à l'API ClipFarm.
    Conformément aux consignes de sécurité, aucun contenu n'est publié sans validation explicite.

.EXAMPLE
    .\scripts\test-publish.ps1 -ClipId "test_proj_1" -Privacy unlisted
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("youtube")]
    [string]$Platform = "youtube",

    [Parameter(Mandatory=$true)]
    [string]$ClipId,

    [Parameter(Mandatory=$false)]
    [ValidateSet("private", "unlisted")]
    [string]$Privacy = "unlisted",

    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "http://localhost:8000"
)

Write-Host "=== ClipFarm - Test de Publication Réelle Sécurisée ($Platform) ===" -ForegroundColor Cyan

# 1. Vérifier la disponibilité de l'API
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get -TimeoutSec 5
    Write-Host "[OK] API joignable ($($health.app))" -ForegroundColor Green
} catch {
    Write-Error "Impossible de joindre l'API ClipFarm sur $ApiUrl. Assurez-vous que le serveur tourne."
    exit 1
}

# 2. Vérifier les comptes connectés
try {
    $accounts = Invoke-RestMethod -Uri "$ApiUrl/accounts" -Method Get
} catch {
    Write-Error "Erreur lors de la récupération des comptes: $_"
    exit 1
}

$matching = $accounts | Where-Object { $_.platform -eq $Platform -and $_.status -eq "connected" }
if (-not $matching) {
    Write-Host "[!] Aucun compte $Platform connecté." -ForegroundColor Yellow
    Write-Host "Rendez-vous sur http://localhost:3000/accounts pour connecter votre chaîne YouTube." -ForegroundColor Yellow
    exit 1
}

$account = $matching[0]
Write-Host "[OK] Compte sélectionné : $($account.name) (ID: $($account.id))" -ForegroundColor Green

# 3. Récupérer ou générer les métadonnées
Write-Host "-> Génération des métadonnées pour le clip $ClipId..." -ForegroundColor Gray
try {
    $meta = Invoke-RestMethod -Uri "$ApiUrl/clips/$ClipId/metadata" -Method Post -Body (@{ platform = $Platform } | ConvertTo-Json) -ContentType "application/json"
    $title = $meta.title
    $description = $meta.description
    $tags = $meta.tags
} catch {
    Write-Host "[!] Génération IA indisponible, utilisation du titre par défaut" -ForegroundColor Yellow
    $title = "Test ClipFarm Shorts #Shorts"
    $description = "Test de publication automatisée via ClipFarm API"
    $tags = @("shorts", "test", "clipfarm")
}

Write-Host "`n--- Récapitulatif de la publication ---" -ForegroundColor Cyan
Write-Host "Titre       : $title"
Write-Host "Visibilité  : $Privacy (Sécurisé : aucun public)" -ForegroundColor Yellow
Write-Host "Chaîne      : $($account.name)"
Write-Host "Tags        : $($tags -join ', ')"
Write-Host "---------------------------------------`n"

# 4. Confirmation explicite obligatoire
$confirmation = Read-Host "Confirmez-vous détenir les droits et autoriser l'envoi vers YouTube ? (tapez 'OUI' pour valider)"
if ($confirmation -ne "OUI" -and $confirmation -ne "oui" -and $confirmation -ne "O" -and $confirmation -ne "o") {
    Write-Host "Publication annulée par l'utilisateur." -ForegroundColor Yellow
    exit 0
}

# 5. Envoi
$payload = @{
    clip_id = $ClipId
    account_id = $account.id
    platform = $Platform
    title = $title
    description = $description
    tags = $tags
    privacy = $Privacy
    made_for_kids = $false
    rights_confirmed = $true
    publish_now = $true
} | ConvertTo-Json

Write-Host "-> Envoi en cours vers YouTube Data API..." -ForegroundColor Cyan
try {
    $result = Invoke-RestMethod -Uri "$ApiUrl/clips/$ClipId/publish" -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 120
    Write-Host "`n[SUCCÈS] Clip publié avec succès !" -ForegroundColor Green
    Write-Host "ID Vidéo YouTube : $($result.external_id)" -ForegroundColor Green
    Write-Host "Lien du Short    : $($result.url)" -ForegroundColor Green
} catch {
    Write-Error "Échec de publication : $_"
    exit 1
}

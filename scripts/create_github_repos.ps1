param(
    [Parameter(Mandatory=$true)][string]$Owner,
    [ValidateSet("public", "private")][string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$repositories = @(
    "incubator-sensor-service",
    "incubator-aggregator-service",
    "quantum-anomaly-detector-service",
    "hybrid-incubator-deployment"
)

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "No se encontro GitHub CLI (gh). Instalalo y ejecuta: gh auth login"
}

foreach ($name in $repositories) {
    $path = Join-Path $root $name
    Push-Location $path
    try {
        if (-not (Test-Path ".git")) { git init }
        git branch -M main
        git add .
        git rev-parse --verify HEAD *> $null
        if ($LASTEXITCODE -ne 0) {
            git commit -m "Initial version"
        } elseif (git status --porcelain) {
            git commit -m "Update project files"
        }
        gh repo create "$Owner/$name" "--$Visibility" --source . --remote origin --push
    }
    finally {
        Pop-Location
    }
}

Write-Host "Repositorios creados. Actualiza application.cloud.yaml:"
Write-Host "python scripts/set_github_owner.py $Owner"

<#
.SYNOPSIS
  HÂKİM yarışma günü başlatma scripti: infra → backend → frontend (production) → Cloudflare Tunnel.

.DESCRIPTION
  Dört bileşeni sırayla, her biri ayrı bir görünür PowerShell penceresinde açar:
    1. Docker Compose (Postgres/Elasticsearch/Neo4j/Redis/MinIO)
    2. FastAPI backend (uvicorn, 127.0.0.1:8000)
    3. Next.js frontend — PRODUCTION build + start (localhost:3000)
    4. Cloudflare named Tunnel (varsa; yoksa yalnızca uyarır, diğerlerini durdurmaz)

  Zaten bir portta dinleyen bir şey varsa o adımı ATLAR (duplicate process açmaz).
  Cloudflare/tunnel adımı başarısız olsa bile backend+frontend AYAKTA kalır —
  uygulama http://localhost:3000 üzerinden çalışmaya devam eder (bkz.
  docs/competition_deployment.md "İnternet kesilirse").

.PARAMETER SkipInfra
  Docker Compose adımını atla (infra zaten ayaktaysa).

.PARAMETER SkipBuild
  `npm run build` adımını atla, doğrudan `npm run start` dene (zaten build
  edilmiş bir .next varsa ve env var'lar değişmediyse hızlı yeniden başlatma).

.PARAMETER SkipTunnel
  Cloudflare Tunnel'ı başlatma; yalnızca localhost'ta çalıştır.

.PARAMETER TunnelName
  `cloudflared tunnel run <isim>` için tunnel adı. Varsayılan: hakim-competition.

.EXAMPLE
  .\scripts\start_competition.ps1
.EXAMPLE
  .\scripts\start_competition.ps1 -SkipTunnel
.EXAMPLE
  .\scripts\start_competition.ps1 -SkipInfra -SkipBuild
#>

[CmdletBinding()]
param(
    [switch]$SkipInfra,
    [switch]$SkipBuild,
    [switch]$SkipTunnel,
    [string]$TunnelName = "hakim-competition"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendHealthUrl = "http://127.0.0.1:8000/health"
$FrontendUrl = "http://127.0.0.1:3000"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Text)
    Write-Host "    OK  $Text" -ForegroundColor Green
}

function Write-Warn2 {
    param([string]$Text)
    Write-Host "    !!  $Text" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Text)
    Write-Host "    XX  $Text" -ForegroundColor Red
}

function Test-PortListening {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSec = 60,
        [string]$Label = $Url
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
            # henüz ayakta değil, bekle
        }
        Start-Sleep -Seconds 2
    }
    Write-Err "$Label $TimeoutSec sn içinde yanıt vermedi."
    return $false
}

function Start-InNewWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $psArgs = @(
        "-NoExit",
        "-Command",
        "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$WorkingDirectory'; $Command"
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $psArgs -WorkingDirectory $WorkingDirectory | Out-Null
}

Write-Host "HÂKİM — yarışma başlatma" -ForegroundColor Magenta
Write-Host "Repo: $RepoRoot"

# --- 0) .env kontrolü -------------------------------------------------------
Write-Step ".env kontrol ediliyor"
$envPath = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Err ".env yok ($envPath). 'copy .env.example .env' ile oluşturup HAKIM_LLM_API_KEY / HAKIM_PROFILE=evren değerlerini doldurun."
    exit 1
}
Write-Ok ".env bulundu."

# --- 1) Infra (Docker Compose) ----------------------------------------------
if ($SkipInfra) {
    Write-Step "Infra adımı atlandı (-SkipInfra)"
} else {
    Write-Step "Docker Compose (Postgres/Elasticsearch/Neo4j/Redis/MinIO) başlatılıyor"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "docker komutu bulunamadı. Docker Desktop kurulu/açık olmalı."
        exit 1
    }
    Push-Location (Join-Path $RepoRoot "infra")
    try {
        docker compose up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Err "docker compose up -d başarısız oldu (exit $LASTEXITCODE)."
            exit 1
        }
    } finally {
        Pop-Location
    }
    Write-Ok "Docker Compose komutu tamamlandı. Servislerin sağlıklı olması birkaç saniye sürebilir."
}

# --- 2) Backend (FastAPI/uvicorn) -------------------------------------------
Write-Step "Backend (FastAPI, 127.0.0.1:8000)"
if (Test-PortListening -Port 8000) {
    Write-Warn2 "8000 portu zaten dinleniyor — mevcut süreç kullanılacak, yeni bir backend açılmadı."
} else {
    $backendCmd = "uv run uvicorn hakim_api.main:app --app-dir apps/api/src --port 8000 --host 127.0.0.1"
    Start-InNewWindow -Title "HAKIM backend (8000)" -WorkingDirectory $RepoRoot -Command $backendCmd
    Write-Ok "Backend yeni pencerede başlatıldı: $backendCmd"
}
Write-Host "    Backend hazır olması bekleniyor ($BackendHealthUrl) ..."
if (-not (Wait-HttpOk -Url $BackendHealthUrl -TimeoutSec 90 -Label "Backend")) {
    Write-Err "Backend zamanında ayağa kalkmadı. Backend penceresindeki hata çıktısını kontrol edin."
    exit 1
}
Write-Ok "Backend yanıt veriyor."

# --- 3) Frontend (Next.js, production build + start) -----------------------
Write-Step "Frontend (Next.js production, localhost:3000)"
$webDir = Join-Path $RepoRoot "apps\web"
if (Test-PortListening -Port 3000) {
    Write-Warn2 "3000 portu zaten dinleniyor — mevcut süreç kullanılacak, yeni bir frontend açılmadı."
} else {
    if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
        Write-Err "apps/web/node_modules yok. Önce 'cd apps\web; npm install' çalıştırın."
        exit 1
    }
    $frontendCmd = if ($SkipBuild) {
        "npm run start"
    } else {
        "npm run build; if (`$LASTEXITCODE -ne 0) { Write-Host 'BUILD BASARISIZ' -ForegroundColor Red; Read-Host 'Devam etmek icin Enter'; exit 1 }; npm run start"
    }
    Start-InNewWindow -Title "HAKIM frontend (3000)" -WorkingDirectory $webDir -Command $frontendCmd
    Write-Ok "Frontend yeni pencerede başlatıldı ($(if ($SkipBuild) {'build atlandı'} else {'build + start'}))."
}
Write-Host "    Frontend hazır olması bekleniyor ($FrontendUrl) ..."
if (-not (Wait-HttpOk -Url $FrontendUrl -TimeoutSec 180 -Label "Frontend")) {
    Write-Err "Frontend zamanında ayağa kalkmadı (build uzun sürüyor olabilir). Frontend penceresini kontrol edin."
    exit 1
}
Write-Ok "Frontend yanıt veriyor."

# --- 4) Cloudflare Tunnel ----------------------------------------------------
if ($SkipTunnel) {
    Write-Step "Tunnel adımı atlandı (-SkipTunnel) — yalnızca localhost:3000 kullanılabilir."
} else {
    Write-Step "Cloudflare Tunnel ($TunnelName)"
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Warn2 "cloudflared kurulu değil — tunnel atlanıyor, uygulama yalnızca localhost:3000 üzerinden erişilebilir."
        Write-Warn2 "Kurulum için docs/competition_deployment.md 'İlk kurulum' bölümüne bakın."
    } else {
        $cfConfig = Join-Path $RepoRoot "infra\cloudflared\config.yml"
        if (-not (Test-Path $cfConfig)) {
            Write-Warn2 "infra\cloudflared\config.yml yok (bkz. config.yml.example) — tunnel atlanıyor."
            Write-Warn2 "Uygulama yalnızca localhost:3000 üzerinden erişilebilir."
        } else {
            $tunnelCmd = "cloudflared tunnel --config `"$cfConfig`" run $TunnelName"
            Start-InNewWindow -Title "HAKIM cloudflared ($TunnelName)" -WorkingDirectory $RepoRoot -Command $tunnelCmd
            Write-Ok "Tunnel yeni pencerede başlatıldı: $tunnelCmd"
            Write-Warn2 "Public URL'in gerçekten açıldığını tunnel penceresinden ve tarayıcıdan doğrulayın."
        }
    }
}

Write-Host ""
Write-Host "=== Özet ===" -ForegroundColor Magenta
Write-Ok "Local:  $FrontendUrl"
if ($env:HAKIM_PUBLIC_HOSTNAME) {
    Write-Ok "Public: https://$($env:HAKIM_PUBLIC_HOSTNAME)  (HAKIM_PUBLIC_HOSTNAME env var'dan)"
} else {
    Write-Warn2 "HAKIM_PUBLIC_HOSTNAME set değil — public URL'i docs/competition_deployment.md'den kontrol edin."
}
Write-Host "Sağlık kontrolü: $BackendHealthUrl  (checks.yazim = Evren, checks.elasticsearch/neo4j = Retriever, checks.postgres = Database)"
Write-Host "Kapatmak için: her bileşenin kendi penceresinde Ctrl+C, ya da pencereleri kapatın."

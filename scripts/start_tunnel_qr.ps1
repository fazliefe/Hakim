# Starts a Cloudflare quick tunnel to localhost:3000, writes the public URL
# to data/tunnel-url.txt, and opens the desktop QR page.
param(
    [string]$LocalUrl = "http://localhost:3000"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$UrlFile = Join-Path $RepoRoot "data\tunnel-url.txt"
$Cloudflared = @(
    "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
    "$env:ProgramFiles\cloudflared\cloudflared.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Cloudflared) {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { $Cloudflared = $cmd.Source }
}

if (-not $Cloudflared) {
    throw "cloudflared not found. Run: winget install --id Cloudflare.cloudflared"
}

New-Item -ItemType Directory -Force -Path (Split-Path $UrlFile) | Out-Null
Write-Host "Starting tunnel: $LocalUrl"
Write-Host "QR page: http://localhost:3000/qr"
Write-Host ""

$opened = $false
$pattern = "https://(?!api\.)[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com"
$arg = "tunnel --url `"$LocalUrl`""

cmd.exe /c "`"$Cloudflared`" $arg 2>&1" | ForEach-Object {
    $line = "$_"
    if (-not $line) { return }
    Write-Host $line
    if ($line -match $pattern) {
        $url = $Matches[0].Trim()
        Set-Content -Path $UrlFile -Value $url -Encoding ascii
        Write-Host ""
        Write-Host "Public URL: $url"
        Write-Host "QR target:  $url/giris"
        if (-not $opened) {
            $opened = $true
            Start-Process "http://127.0.0.1:3000/qr"
        }
    }
}

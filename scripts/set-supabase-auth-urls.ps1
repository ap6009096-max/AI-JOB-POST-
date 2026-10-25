# Requires a Supabase Personal Access Token:
#   https://supabase.com/dashboard/account/tokens
# Usage (PowerShell):
#   $env:SUPABASE_ACCESS_TOKEN = "sbp_..."
#   .\scripts\set-supabase-auth-urls.ps1 -WebUrl "https://aether-web-XXXX-as.a.run.app"

param(
  [string]$ProjectRef = "dmcnucnqtrdohodjoqks",
  [string]$WebUrl = "https://aether-web-XXXX-as.a.run.app"
)

$ErrorActionPreference = "Stop"
$siteUrl = $WebUrl.TrimEnd("/")
$uriAllowList = @(
  "$siteUrl/auth/callback",
  "$siteUrl/**",
  "http://localhost:3000/auth/callback",
  "http://127.0.0.1:3000/auth/callback"
) -join ","

$token = $env:SUPABASE_ACCESS_TOKEN
if (-not $token) {
  throw "Set SUPABASE_ACCESS_TOKEN to a Supabase Personal Access Token (Account → Access Tokens)."
}

$headers = @{
  Authorization = "Bearer $token"
  "Content-Type" = "application/json"
}

$getUrl = "https://api.supabase.com/v1/projects/$ProjectRef/config/auth"
$before = Invoke-RestMethod -Method Get -Uri $getUrl -Headers $headers
Write-Output "before site_url=$($before.site_url)"

$body = @{
  site_url = $siteUrl
  uri_allow_list = $uriAllowList
} | ConvertTo-Json

$after = Invoke-RestMethod -Method Patch -Uri $getUrl -Headers $headers -Body $body
Write-Output "after site_url=$($after.site_url)"
Write-Output "uri_allow_list_has_web=$($after.uri_allow_list -match [regex]::Escape($siteUrl))"
Write-Output "ok"

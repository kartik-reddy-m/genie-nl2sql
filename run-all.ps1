# Starts the whole stack:
#   - redis + redisinsight   (standalone containers on the genie-net network)
#   - genie-service + conversation-service  (docker compose)
#   - ui-app (Vite)          (runs on the host)
#
# Run from the genie-nl2sql root:  ./run-all.ps1

$root = $PSScriptRoot

# Docker CLI + credential helper aren't on PATH by default on this machine.
$dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
if (Test-Path $dockerBin) { $env:PATH = "$dockerBin;$env:PATH" }

# --- shared network ---
docker network inspect genie-net *> $null
if ($LASTEXITCODE -ne 0) { docker network create genie-net | Out-Null }

# --- redis ---
if ((docker ps --filter "name=redis" --format "{{.Names}}") -ne "redis") {
  if ((docker ps -a --filter "name=redis" --format "{{.Names}}") -eq "redis") {
    docker start redis | Out-Null
  } else {
    docker run -d --name redis --network genie-net -p 6379:6379 --restart unless-stopped redis:7-alpine | Out-Null
  }
}
docker network connect genie-net redis *> $null   # no-op if already connected

# --- redisinsight (GUI on http://localhost:5540) ---
if ((docker ps --filter "name=redisinsight" --format "{{.Names}}") -ne "redisinsight") {
  if ((docker ps -a --filter "name=redisinsight" --format "{{.Names}}") -eq "redisinsight") {
    docker start redisinsight | Out-Null
  } else {
    docker run -d --name redisinsight --network genie-net -p 5540:5540 --restart unless-stopped redis/redisinsight:latest | Out-Null
  }
}
docker network connect genie-net redisinsight *> $null

# --- genie-service + conversation-service ---
Push-Location $root
docker compose up -d --build
Pop-Location

# --- ui-app (Vite) on the host; ComSpec must be set or npm can't spawn ---
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "`$env:ComSpec='C:\Windows\System32\cmd.exe'; cd '$root\ui-app'; npm run dev"
)

Write-Host ""
Write-Host "Up:  redis(:6379)  redisinsight(:5540)  genie-service(:8001)  conversation-service(:8000)  ui(:5173)"
Write-Host "Open http://localhost:5173"

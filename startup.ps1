# Git PATH Setup - Run this at start of each PowerShell session
# Usage: . .\startup.ps1

Write-Host "🔧 Adding Git to PATH..." -ForegroundColor Cyan
$env:Path += ";C:\Program Files\Git\cmd"

# Verify
$gitVersion = git --version 2>$null
if ($gitVersion) {
    Write-Host "✅ Git is now available: $gitVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Git not found. Please check installation." -ForegroundColor Red
}

Write-Host "📂 Current directory: $PWD" -ForegroundColor Yellow
Write-Host ""
Write-Host "🎯 Quick commands:" -ForegroundColor Cyan
Write-Host "  git status          - Check what's changed" -ForegroundColor Gray
Write-Host "  git log --oneline   - View commit history" -ForegroundColor Gray
Write-Host "  git add .           - Stage all changes" -ForegroundColor Gray
Write-Host "  git commit -m 'msg' - Save changes" -ForegroundColor Gray
Write-Host ""

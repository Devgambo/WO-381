# deploy-hf.ps1
# ─────────────────────────────────────────────────────────────────
# Deploys the server/ directory to Hugging Face Spaces as a
# Docker Space.  Files are placed at the REPO ROOT so HF can
# find the Dockerfile.
#
# Usage:  .\deploy-hf.ps1
# ─────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

Write-Host "`n🚀  Deploying to Hugging Face Spaces...`n" -ForegroundColor Cyan

# ── 1. Start from main ──────────────────────────────────────────
git checkout main 2>$null
Write-Host "  ✓ On main branch" -ForegroundColor DarkGray

# ── 2. Delete old hf-deploy branch if it exists ─────────────────
git branch -D hf-deploy 2>$null
Write-Host "  ✓ Cleaned old hf-deploy branch" -ForegroundColor DarkGray

# ── 3. Create a fresh orphan branch (no history) ────────────────
git checkout --orphan hf-deploy
Write-Host "  ✓ Created orphan hf-deploy branch" -ForegroundColor DarkGray

# ── 4. Clear the index completely ────────────────────────────────
git rm -rf --cached . 2>$null
Write-Host "  ✓ Cleared index" -ForegroundColor DarkGray

# ── 5. Read the server/ subtree from main into root of index ────
#    This makes Dockerfile, main.py, Procfile, etc. appear at
#    the repo root — exactly what HF Docker Spaces expects.
git read-tree "main:server"
Write-Host "  ✓ Mapped server/ contents to repo root" -ForegroundColor DarkGray

# ── 6. Create the HF Space README with required front-matter ────
$readme = @"
---
title: WO-381
emoji: 🏗️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# Structural Drawing Compliance Checker — API Server

FastAPI backend + RQ worker for the Structural Drawing Compliance Checker.
"@

[System.IO.File]::WriteAllText(
    (Join-Path $PWD "README.md"),
    $readme,
    [System.Text.UTF8Encoding]::new($false)   # UTF-8 without BOM
)
git add README.md
Write-Host "  ✓ Created HF Space README" -ForegroundColor DarkGray

# ── 7. Commit ───────────────────────────────────────────────────
git commit -m "deploy: server at root for HF Docker Space"
Write-Host "  ✓ Committed" -ForegroundColor DarkGray

# ── 8. Push to HF ──────────────────────────────────────────────
git push hf hf-deploy:main --force
Write-Host "  ✓ Pushed to HF" -ForegroundColor DarkGray

# ── 9. Return to main ──────────────────────────────────────────
git checkout -f main
Write-Host "  ✓ Back on main" -ForegroundColor DarkGray

Write-Host "`n✅  Deployed successfully!`n" -ForegroundColor Green
Write-Host "  Remember to set secrets in HF Space Settings:" -ForegroundColor Yellow
Write-Host "    OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY," -ForegroundColor Yellow
Write-Host "    SUPABASE_SERVICE_ROLE_KEY, REDIS_URL," -ForegroundColor Yellow
Write-Host "    CORS_ALLOW_ORIGINS, RQ_SIMPLE_WORKER=1" -ForegroundColor Yellow
Write-Host ""

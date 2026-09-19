<#
.SYNOPSIS
    Voxlery Automated Uninstaller for Windows PowerShell
.DESCRIPTION
    Safely removes Voxlery data directories, virtual environments, build artifacts,
    and optionally pulls/removes installed Ollama AI models.
    Original user photo files are NEVER modified or deleted.
#>

param(
    [switch]$RemoveData,
    [switch]$RemoveVenv,
    [switch]$RemoveModels,
    [switch]$All,
    [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  Voxlery Uninstallation Utility (Windows PowerShell)" -ForegroundColor Cyan
Write-Host "  Safe Cleanup · Privacy Preserving · Photos Untouched" -ForegroundColor Gray
Write-Host "=====================================================================`n" -ForegroundColor Cyan

Write-Host "Note: Original photo files on your disk will NEVER be touched or deleted.`n" -ForegroundColor DarkGray

$doRemoveData = $RemoveData.IsPresent -or $All.IsPresent
$doRemoveVenv = $RemoveVenv.IsPresent -or $All.IsPresent
$doRemoveModels = $RemoveModels.IsPresent -or $All.IsPresent

if (-not $Force -and -not $All) {
    if (-not $RemoveData) {
        $ans = Read-Host "1. Remove library database, thumbnails, and vector index (~/.voxlery)? [Y/n]"
        if ($ans -notmatch "^[Nn]") { $doRemoveData = $true }
    }
    if (-not $RemoveVenv) {
        $ans = Read-Host "2. Remove isolated Python virtual environment (.venv) and build cache? [Y/n]"
        if ($ans -notmatch "^[Nn]") { $doRemoveVenv = $true }
    }
    if (-not $RemoveModels) {
        $ans = Read-Host "3. Do you also want to remove downloaded Ollama AI models (moondream, gemma4:e2b)? [y/N]"
        if ($ans -match "^[Yy]") { $doRemoveModels = $true }
    }
    Write-Host ""
}

# 1. Remove User Data Directory (~/.voxlery and legacy ~/.pixelmemory)
if ($doRemoveData) {
    $VoxleryData = Join-Path $env:USERPROFILE ".voxlery"
    if (Test-Path $VoxleryData) {
        Write-Host "[*] Removing Voxlery data directory ($VoxleryData)..." -ForegroundColor Cyan
        try {
            Remove-Item -Path $VoxleryData -Recurse -Force -ErrorAction Stop
            Write-Host "[OK] Removed: $VoxleryData" -ForegroundColor Green
        } catch {
            Write-Host "[!] Warning: Could not completely remove $VoxleryData (in use?): $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[i] No data directory found at $VoxleryData" -ForegroundColor DarkGray
    }

    $LegacyData = Join-Path $env:USERPROFILE ".pixelmemory"
    if (Test-Path $LegacyData) {
        Write-Host "[*] Removing legacy data directory ($LegacyData)..." -ForegroundColor Cyan
        try {
            Remove-Item -Path $LegacyData -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] Removed: $LegacyData" -ForegroundColor Green
        } catch {}
    }
}

# 2. Remove Local Virtual Environment and Cache
if ($doRemoveVenv) {
    $VenvPath = Join-Path $ScriptDir ".venv"
    if (Test-Path $VenvPath) {
        Write-Host "[*] Removing Python virtual environment ($VenvPath)..." -ForegroundColor Cyan
        try {
            Remove-Item -Path $VenvPath -Recurse -Force -ErrorAction Stop
            Write-Host "[OK] Removed virtual environment (.venv)" -ForegroundColor Green
        } catch {
            Write-Host "[!] Warning: Could not remove $VenvPath: $_" -ForegroundColor Yellow
        }
    }

    $NodeModules = Join-Path $ScriptDir "node_modules"
    if (Test-Path $NodeModules) {
        Write-Host "[*] Removing node_modules..." -ForegroundColor Cyan
        Remove-Item -Path $NodeModules -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Removed node_modules" -ForegroundColor Green
    }

    $TauriTarget = Join-Path $ScriptDir "src-tauri\target"
    if (Test-Path $TauriTarget) {
        Write-Host "[*] Removing desktop build artifacts (src-tauri/target)..." -ForegroundColor Cyan
        Remove-Item -Path $TauriTarget -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Removed src-tauri/target" -ForegroundColor Green
    }

    # Clean __pycache__ folders
    Get-ChildItem -Path $ScriptDir -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 3. Remove Ollama AI Models
if ($doRemoveModels) {
    Write-Host "`n── Ollama Model Removal ───────────────────────────────────────────" -ForegroundColor Cyan
    $HasOllama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $HasOllama -and (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")) {
        $env:PATH = "$env:LOCALAPPDATA\Programs\Ollama;$env:PATH"
        $HasOllama = Get-Command ollama -ErrorAction SilentlyContinue
    }

    if ($HasOllama) {
        $modelsToRemove = @("moondream", "gemma4:e2b")
        foreach ($m in $modelsToRemove) {
            Write-Host "[*] Removing Ollama model '$m'..." -ForegroundColor Cyan
            & ollama rm $m 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Removed model: $m" -ForegroundColor Green
            } else {
                Write-Host "[i] Model '$m' was not installed or already removed." -ForegroundColor DarkGray
            }
        }
    } else {
        Write-Host "[!] Ollama command line utility not found. Skipping model removal." -ForegroundColor Yellow
    }
}

Write-Host "`n=====================================================================" -ForegroundColor Green
Write-Host "  [OK] Voxlery Uninstallation Complete!" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host ""

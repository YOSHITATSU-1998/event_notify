# ============================================================
# Fukuoka Event Notification System Ver.3.1.2
# Local Debug Execution Script
# 
# Usage: .\run\dispatch.ps1
# Flow: Scraping -> DB Save -> HTML Generation -> Slack Notification
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Fukuoka Event Notification System Ver.3.1.2" -ForegroundColor Cyan
Write-Host "  Local Debug Mode" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# Load .env file (if exists)
# ============================================================
$envFile = Join-Path (Get-Location) ".env"
if (Test-Path $envFile) {
    Write-Host "[SETUP] Loading .env file..." -ForegroundColor Cyan
    
    try {
        Get-Content $envFile -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            
            # Skip empty lines and comments
            if ($line -and -not $line.StartsWith("#")) {
                # Find the first '=' character
                $equalsIndex = $line.IndexOf("=")
                
                if ($equalsIndex -gt 0) {
                    $key = $line.Substring(0, $equalsIndex).Trim()
                    $value = $line.Substring($equalsIndex + 1).Trim()
                    
                    # Remove surrounding quotes if present
                    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                        $value = $value.Substring(1, $value.Length - 2)
                    } elseif ($value.StartsWith("'") -and $value.EndsWith("'")) {
                        $value = $value.Substring(1, $value.Length - 2)
                    }
                    
                    # Set environment variable
                    if ($key) {
                        Set-Item -Path "env:$key" -Value $value -Force
                        
                        # Display (hide sensitive data)
                        if ($value) {
                            $displayValue = $value.Substring(0, [Math]::Min(20, $value.Length))
                            Write-Host "  [OK] Loaded $key = $displayValue..." -ForegroundColor Gray
                        }
                    }
                }
            }
        }
        
        Write-Host "[OK] .env file loaded successfully" -ForegroundColor Green
        Write-Host ""
    } catch {
        Write-Host "[ERROR] Failed to load .env file: $_" -ForegroundColor Red
        Write-Host ""
    }
} else {
    Write-Host "[WARN] .env file not found at: $envFile" -ForegroundColor Yellow
    Write-Host "[INFO] Environment variables must be set manually or via system environment" -ForegroundColor Gray
    Write-Host ""
}

# ============================================================
# Environment Variables Check
# ============================================================
Write-Host "[CHECK] Environment variables..." -ForegroundColor Cyan
Write-Host ""

# Function to get environment variable from multiple sources
function Get-EnvironmentVariable {
    param($Name)
    
    # 1. Check current session
    if (Test-Path env:$Name) {
        return (Get-Item env:$Name).Value
    }
    
    # 2. Check user environment variables
    $userValue = [Environment]::GetEnvironmentVariable($Name, "User")
    if ($userValue) {
        return $userValue
    }
    
    # 3. Check machine environment variables
    $machineValue = [Environment]::GetEnvironmentVariable($Name, "Machine")
    if ($machineValue) {
        return $machineValue
    }
    
    return $null
}

$required_vars = @("SUPABASE_URL", "SUPABASE_KEY", "SLACK_WEBHOOK_URL")
$missing = @()

foreach ($var in $required_vars) {
    $value = Get-EnvironmentVariable -Name $var
    
    if (-not $value) {
        $missing += $var
        Write-Host "  [X] $var : Not set" -ForegroundColor Red
    } else {
        # Set to current session if not already set
        if (-not (Test-Path env:$var)) {
            Set-Item -Path env:$var -Value $value
        }
        
        $display_value = $value.Substring(0, [Math]::Min(20, $value.Length))
        Write-Host "  [OK] $var : $display_value..." -ForegroundColor Green
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Required environment variables are not set" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please set them in one of the following ways:" -ForegroundColor Yellow
    Write-Host "  1. PowerShell session (temporary):" -ForegroundColor Gray
    Write-Host '     $env:SUPABASE_URL = "https://xxx.supabase.co"' -ForegroundColor Gray
    Write-Host '     $env:SUPABASE_KEY = "eyJxxx..."' -ForegroundColor Gray
    Write-Host '     $env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/xxx"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. .env file (edit the .env file in project root)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  3. System Environment Variables (already set in your case)" -ForegroundColor Gray
    Write-Host "     If you've set them as system variables, try restarting PowerShell" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "[OK] Environment variables check completed" -ForegroundColor Green
Write-Host ""

# ============================================================
# Environment Variables Setup (Same as GitHub Actions YML)
# ============================================================
Write-Host "[SETUP] Configuring environment variables..." -ForegroundColor Cyan

$env:TZ = "Asia/Tokyo"
$env:PYTHONPATH = (Get-Location).Path
# ENABLE_DB_SAVE is already loaded from .env file
$env:GITHUB_PAGES = "false"

# Build path step by step for compatibility
$sitePath = Join-Path (Get-Location) "site"
$indexPath = Join-Path $sitePath "index.html"
$env:GITHUB_PAGES_URL = "file:///" + $indexPath

Write-Host "  - TZ = Asia/Tokyo" -ForegroundColor Gray
Write-Host "  - PYTHONPATH = $env:PYTHONPATH" -ForegroundColor Gray
Write-Host "  - ENABLE_DB_SAVE = $env:ENABLE_DB_SAVE" -ForegroundColor Gray
Write-Host "  - GITHUB_PAGES = false (Local mode)" -ForegroundColor Gray
Write-Host "  - GITHUB_PAGES_URL = $env:GITHUB_PAGES_URL" -ForegroundColor Gray
Write-Host ""

# ============================================================
# Python Version Check
# ============================================================
Write-Host "[CHECK] Python environment..." -ForegroundColor Cyan

try {
    $python_version = python --version 2>&1
    Write-Host "  [OK] $python_version" -ForegroundColor Green
} catch {
    Write-Host "  [X] Python not found" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================================
# Prepare Manual Events Directory (Same as YML)
# ============================================================
Write-Host "[SETUP] Preparing manual events directory..." -ForegroundColor Cyan

if (-not (Test-Path "manual_events")) {
    New-Item -ItemType Directory -Path "manual_events" | Out-Null
    Write-Host "  [OK] Created manual_events/ directory" -ForegroundColor Green
}

if (-not (Test-Path "manual_events/oneshot.json")) {
    "[]" | Out-File -FilePath "manual_events/oneshot.json" -Encoding utf8
    Write-Host "  [OK] Created manual_events/oneshot.json" -ForegroundColor Green
}

if (-not (Test-Path "manual_events/recurring.json")) {
    "[]" | Out-File -FilePath "manual_events/recurring.json" -Encoding utf8
    Write-Host "  [OK] Created manual_events/recurring.json" -ForegroundColor Green
}

Write-Host "  [OK] Manual events directory ready" -ForegroundColor Green
Write-Host ""

# ============================================================
# Debug Information Display (Same as YML)
# ============================================================
Write-Host "[DEBUG] Environment information:" -ForegroundColor Cyan
Write-Host "  - Working directory: $(Get-Location)" -ForegroundColor Gray
Write-Host "  - PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Gray
Write-Host "  - ENABLE_DB_SAVE: $env:ENABLE_DB_SAVE" -ForegroundColor Gray

# Python path check
python -c "import sys; print('  - Python path:', sys.path[:3])" 2>&1 | Write-Host -ForegroundColor Gray

Write-Host ""

# ============================================================
# STEP 1: Data Refresh (Scraping + DB Save)
# ============================================================
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "[STEP 1/4] Data Refresh (Scraping + DB Save)" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""

$start_time_1 = Get-Date
Write-Host "Start time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

python -m scripts.refresh_future_events
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Data refresh failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

$end_time_1 = Get-Date
$duration_1 = ($end_time_1 - $start_time_1).TotalSeconds

Write-Host ""
Write-Host "[OK] Data refresh completed (Duration: $([Math]::Round($duration_1, 2))s)" -ForegroundColor Green
Write-Host ""

# ============================================================
# STEP 2: Prepare site Directory
# ============================================================
Write-Host "[STEP 2/4] Preparing output directory..." -ForegroundColor Cyan

if (-not (Test-Path "site")) {
    New-Item -ItemType Directory -Path "site" | Out-Null
    Write-Host "  [OK] Created site/ directory" -ForegroundColor Green
} else {
    Write-Host "  [OK] site/ directory already exists" -ForegroundColor Gray
}
Write-Host ""

# ============================================================
# STEP 3: HTML Generation
# ============================================================
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "[STEP 3/4] HTML Generation (index.html + manual.html)" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""

$start_time_2 = Get-Date
Write-Host "Start time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

python -m notify.html_export
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] HTML generation failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

$end_time_2 = Get-Date
$duration_2 = ($end_time_2 - $start_time_2).TotalSeconds

Write-Host ""
Write-Host "[OK] HTML generation completed (Duration: $([Math]::Round($duration_2, 2))s)" -ForegroundColor Green
Write-Host ""

# Generated files check
Write-Host "Generated files:" -ForegroundColor Cyan
if (Test-Path "site/index.html") {
    $index_size = (Get-Item "site/index.html").Length
    Write-Host "  [OK] site/index.html ($([Math]::Round($index_size/1KB, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "  [X] site/index.html (not generated)" -ForegroundColor Red
}

if (Test-Path "site/manual.html") {
    $manual_size = (Get-Item "site/manual.html").Length
    Write-Host "  [OK] site/manual.html ($([Math]::Round($manual_size/1KB, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "  [X] site/manual.html (not generated)" -ForegroundColor Red
}

Write-Host ""

# ============================================================
# STEP 4: Slack Notification
# ============================================================
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "[STEP 4/4] Slack Notification" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""

$start_time_3 = Get-Date
Write-Host "Start time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

python -m notify.dispatch
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Slack notification failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

$end_time_3 = Get-Date
$duration_3 = ($end_time_3 - $start_time_3).TotalSeconds

Write-Host ""
Write-Host "[OK] Slack notification completed (Duration: $([Math]::Round($duration_3, 2))s)" -ForegroundColor Green
Write-Host ""

# ============================================================
# Execution Summary
# ============================================================
$total_duration = ($end_time_3 - $start_time_1).TotalSeconds

Write-Host "============================================================" -ForegroundColor Green
Write-Host "All processes completed - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Execution Summary:" -ForegroundColor Cyan
Write-Host "  [OK] STEP 1: Data Refresh ($([Math]::Round($duration_1, 2))s)" -ForegroundColor Gray
Write-Host "  [OK] STEP 2: Directory Preparation" -ForegroundColor Gray
Write-Host "  [OK] STEP 3: HTML Generation ($([Math]::Round($duration_2, 2))s)" -ForegroundColor Gray
Write-Host "  [OK] STEP 4: Slack Notification ($([Math]::Round($duration_3, 2))s)" -ForegroundColor Gray
Write-Host "  Total Duration: $([Math]::Round($total_duration, 2))s" -ForegroundColor Yellow
Write-Host ""

Write-Host "Output Files:" -ForegroundColor Cyan
Write-Host "  - site/index.html" -ForegroundColor Gray
Write-Host "  - site/manual.html" -ForegroundColor Gray
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  View HTML: start site\index.html" -ForegroundColor Yellow
Write-Host "  Or: start site (open folder)" -ForegroundColor Yellow
Write-Host ""

Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
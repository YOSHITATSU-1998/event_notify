# ============================================================
# Storage Cleanup Script
# Usage: .\run\run_a.ps1
# Purpose: storage/内のJSONファイルを一括削除（確認なし）
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Storage Cleanup Tool" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# storage/ ディレクトリの確認
# ============================================================
$storagePath = Join-Path (Get-Location) "storage"

if (-not (Test-Path $storagePath)) {
    Write-Host "[INFO] storage/ directory does not exist" -ForegroundColor Yellow
    Write-Host "[INFO] Nothing to clean up" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# ============================================================
# JSONファイルの検索
# ============================================================
Write-Host "[SCAN] Scanning storage/ directory..." -ForegroundColor Cyan

$jsonFiles = Get-ChildItem -Path $storagePath -Filter "*.json" -File

if ($jsonFiles.Count -eq 0) {
    Write-Host "[INFO] No JSON files found in storage/" -ForegroundColor Green
    Write-Host ""
    exit 0
}

Write-Host "[FOUND] $($jsonFiles.Count) JSON file(s)" -ForegroundColor Yellow
Write-Host ""

# ============================================================
# 削除実行（確認なし）
# ============================================================
Write-Host "[DELETE] Deleting JSON files..." -ForegroundColor Cyan

$deletedCount = 0
$failedCount = 0

foreach ($file in $jsonFiles) {
    try {
        Remove-Item -Path $file.FullName -Force
        Write-Host "  [OK] $($file.Name)" -ForegroundColor Green
        $deletedCount++
    } catch {
        Write-Host "  [ERROR] Failed: $($file.Name)" -ForegroundColor Red
        Write-Host "    $_" -ForegroundColor DarkRed
        $failedCount++
    }
}

# ============================================================
# 結果表示
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Deleted: $deletedCount / Failed: $failedCount" -ForegroundColor $(if ($failedCount -gt 0) { "Yellow" } else { "Green" })
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($deletedCount -gt 0) {
    Write-Host "[SUCCESS] Storage cleanup completed" -ForegroundColor Green
} else {
    Write-Host "[WARNING] No files were deleted" -ForegroundColor Yellow
}

Write-Host ""

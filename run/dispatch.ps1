# ===== Run all scrapers + dispatch (simple) =====
$ErrorActionPreference = "Continue"

# repo ROOT (one level above event_notify)
Set-Location "C:\Users\w33ae\python"

# scrapers
python -m event_notify.scrapers.marinemesse_a
python -m event_notify.scrapers.marinemesse_b
python -m event_notify.scrapers.kokusai_center
python -m event_notify.scrapers.congress_b

# dispatch
python -m event_notify.notify.dispatch

# page
python -m event_notify.notify.html_export
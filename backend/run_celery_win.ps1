$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
celery -A celery_app.celery_app worker -P solo -l info


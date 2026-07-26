param(
  [Parameter(Mandatory = $true)]
  [string]$Python
)

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

Write-Host "[3/3] Khoi dong Aqua Scope tai http://localhost:8000"
Start-Process "http://localhost:8000"

try {
  & $Python -m uvicorn --app-dir web/backend app.main:app --host 0.0.0.0 --port 8000
  $code = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
}
catch [System.Management.Automation.PipelineStoppedException] {
  $code = 0
}
catch {
  Write-Host "[LOI] Khong chay duoc uvicorn: $($_.Exception.Message)"
  Read-Host "Nhan Enter de dong cua so"
  exit 1
}

if ($code -eq 3) {
  Write-Host "[LOI] Uvicorn thoat voi ma loi 3 - khong khoi dong duoc. Kiem cong 8000 co dang bi chiem khong (vd: mot start.bat khac dang chay)."
  Read-Host "Nhan Enter de dong cua so"
  exit 1
}

if ($code -ne 0 -and $code -ne 3221225786 -and $code -ne -1073741510) {
  Write-Host "[LOI] Uvicorn thoat voi ma loi $code."
  Read-Host "Nhan Enter de dong cua so"
  exit $code
}

exit 0

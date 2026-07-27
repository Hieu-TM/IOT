param(
  [Parameter(Mandatory = $true)]
  [string]$Python
)

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

Write-Host "[3/3] Khoi dong Aqua Scope tai http://localhost:8000"

# Importing FastAPI/SQLModel/uvicorn takes a few seconds, so opening the
# browser immediately (the old behavior) showed ERR_CONNECTION_REFUSED more
# often than not. Fix: start a background job BEFORE uvicorn that polls the
# port and opens the browser itself the moment something answers - it runs in
# its own PowerShell process, so it doesn't block starting uvicorn, and it
# opens the browser itself because this thread is about to block inside
# uvicorn's own foreground run below and won't be free to do it later.
# Bounded to 20s so a server that never comes up (bad venv, port already
# taken, etc.) leaves the job exiting quietly instead of polling forever;
# uvicorn's own error handling further down still reports that case to the
# operator. uvicorn stays a normal foreground `&` call in THIS window (not
# inside the job), so Ctrl+C here keeps stopping it exactly as before.
$browserJob = Start-Job -ScriptBlock {
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    try {
      $client = New-Object System.Net.Sockets.TcpClient
      $client.Connect("127.0.0.1", 8000)
      $client.Close()
      Start-Process "http://localhost:8000"
      return
    }
    catch {
      Start-Sleep -Milliseconds 300
    }
  }
}

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
finally {
  # uvicorn has exited (or was Ctrl+C'd) by this point; the job has either
  # already finished (port answered, browser opened) or is still within its
  # own 20s bound and will exit on its own. Either way there is nothing left
  # for it to do once the server is gone.
  Remove-Job $browserJob -Force -ErrorAction SilentlyContinue
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

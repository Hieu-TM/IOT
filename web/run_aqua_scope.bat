@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Aqua Scope one-click local runner.
rem Double-click this file to start the web dashboard and, optionally, the
rem ESP32-CAM capture/upload pipeline with a local SQLite DB.
rem To create another account:
rem   run_aqua_scope.bat create-user USERNAME PASSWORD operator
rem   run_aqua_scope.bat create-user USERNAME PASSWORD admin

cd /d "%~dp0"

if /I "%~1"=="create-user" goto create_user

if not exist "backend\data" mkdir "backend\data"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.11+ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

python -c "import fastapi, uvicorn, sqlmodel, jinja2, PIL, requests, serial" >nul 2>nul
if errorlevel 1 (
  echo [Aqua Scope] Installing Python dependencies...
  python -m pip install -r requirements.txt
  python -m pip install pyserial
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
  )
)

set "DB_PATH=%CD:\=/%/backend/data/aqua_scope_demo.db"
set "AQUA_SCOPE_DATABASE_URL=sqlite:///%DB_PATH%"
set "AQUA_SCOPE_SESSION_SECRET=aqua-scope-local-demo-session-secret"
set "AQUA_SCOPE_ADMIN_USERNAME=admin"
set "AQUA_SCOPE_ADMIN_PASSWORD=1"
set "AQUA_SCOPE_COOKIE_SECURE=false"
set "PYTHONPATH=%CD%\backend"
set "AQUA_INGEST_API_URL=http://127.0.0.1:8000"

echo.
echo ==========================================
echo  Aqua Scope one-click runner
echo ==========================================
echo  URL:      http://127.0.0.1:8000
echo  Admin:    admin
echo  Password: 1
echo.
echo  Data DB:  backend\data\aqua_scope_demo.db
echo.
echo  Camera mode uses Roboflow by default and needs ESP32-CAM firmware:
echo    firmware\aqua_scope_station
echo  Capture mode:
echo    auto-detect USB serial, Roboflow, continuous, every 2 seconds
echo.
echo  Create another account from CMD:
echo    run_aqua_scope.bat create-user operator1 password123456 operator
echo    run_aqua_scope.bat create-user admin2 password123456 admin
echo.
echo  Close both CMD windows, or press Ctrl+C, to stop everything.
echo ==========================================
echo.

python -c "import sys,requests; r=requests.get('http://127.0.0.1:8000/login',timeout=1); sys.exit(0 if r.status_code < 500 else 1)" >nul 2>nul
if errorlevel 1 (
  echo [Aqua Scope] Starting web server in a separate window...
  start "Aqua Scope Web" /D "%~dp0backend" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
) else (
  echo [Aqua Scope] Web server is already running on port 8000. Reusing it.
)

echo [Aqua Scope] Waiting for web server...
set "WEB_READY="
for /L %%I in (1,1,30) do (
  python -c "import sys,requests; r=requests.get('http://127.0.0.1:8000/login',timeout=1); sys.exit(0 if r.status_code < 500 else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "WEB_READY=1"
    goto web_ready
  )
  timeout /t 1 /nobreak >nul
)

:web_ready
if not "%WEB_READY%"=="1" (
  echo [ERROR] Web server did not become ready within 30 seconds.
  echo Check the "Aqua Scope Web" window for the real error.
  pause
  exit /b 1
)
echo [OK] Web server is ready.

start "" "http://127.0.0.1:8000/login"

echo.
set "BOARD_IP="
echo [Aqua Scope] Detecting ESP32-CAM from USB serial...
python auto_detect_board.py --timeout 30 > "backend\data\detected_board_ip.txt"
if not errorlevel 1 (
  set /p "BOARD_IP="<"backend\data\detected_board_ip.txt"
  echo [OK] Detected ESP32-CAM at http://!BOARD_IP!
) else (
  echo [WARN] Could not auto-detect the camera from USB serial.
  echo        Make sure the board is plugged in, firmware is running, and no Serial Monitor is open.
  set /p "BOARD_IP=Enter ESP32-CAM IP manually (blank = web only): "
)
if "%BOARD_IP%"=="" (
  echo.
  echo [Aqua Scope] Web-only mode is running at http://127.0.0.1:8000
  echo Press any key here when you want to close this launcher window.
  pause >nul
  exit /b 0
)

echo.
set "INFER_BACKEND=roboflow"
set "CAPTURE_INTERVAL=2"
set "CAPTURE_COUNT=999999"
echo [Aqua Scope] Using Roboflow, continuous capture, interval %CAPTURE_INTERVAL%s.

python -c "import numpy, PIL, requests, serial" >nul 2>nul
if errorlevel 1 (
  echo [Aqua Scope] Installing minimal ML runtime dependencies...
  cd /d "%~dp0.."
  python -m pip install numpy pillow requests pyserial
  if errorlevel 1 (
    echo [ERROR] Minimal ML dependency installation failed.
    pause
    exit /b 1
  )
  cd /d "%~dp0"
)

cd /d "%~dp0.."
python -m ml.infer --check-config --from-board "%BOARD_IP%" --backend "%INFER_BACKEND%" --api-url http://127.0.0.1:8000
if errorlevel 1 (
  echo.
  echo [ERROR] Inference config is not ready. Fix the messages above, then run this BAT again.
  pause
  exit /b 1
)
cd /d "%~dp0"

echo.
echo ==========================================
echo  Camera capture/upload is starting
echo ==========================================
echo  Board:    http://%BOARD_IP%
echo  Backend:  %INFER_BACKEND%
echo  Count:    %CAPTURE_COUNT%
echo  Interval: %CAPTURE_INTERVAL%s
echo.
echo  Uploaded samples will appear on:
echo    http://127.0.0.1:8000
echo.
echo  Press Ctrl+C in this window to stop capture/upload.
echo ==========================================
echo.

cd /d "%~dp0.."
python -m ml.infer --from-board "%BOARD_IP%" --backend "%INFER_BACKEND%" --count "%CAPTURE_COUNT%" --interval "%CAPTURE_INTERVAL%" --api-url http://127.0.0.1:8000
pause
exit /b 0

:create_user
if "%~4"=="" (
  echo Usage:
  echo   run_aqua_scope.bat create-user USERNAME PASSWORD operator
  echo   run_aqua_scope.bat create-user USERNAME PASSWORD admin
  exit /b 1
)

set "NEW_USERNAME=%~2"
set "NEW_PASSWORD=%~3"
set "NEW_ROLE=%~4"
set "DB_PATH=%CD:\=/%/backend/data/aqua_scope_demo.db"
set "AQUA_SCOPE_DATABASE_URL=sqlite:///%DB_PATH%"
set "PYTHONPATH=%CD%\backend"

if /I not "%NEW_ROLE%"=="admin" if /I not "%NEW_ROLE%"=="operator" (
  echo [ERROR] Role must be admin or operator.
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.11+ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

python -c "import sqlmodel" >nul 2>nul
if errorlevel 1 (
  echo [Aqua Scope] Installing Python dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
  )
)

python -c "import sys; from sqlmodel import Session, select; from app.database import create_db_and_tables, engine; from app.models import User; from app.auth import hash_password; username=sys.argv[1]; password=sys.argv[2]; role=sys.argv[3]; create_db_and_tables(); s=Session(engine); existing=s.exec(select(User).where(User.username==username)).first(); (print('[ERROR] Username already exists: '+username) or sys.exit(2)) if existing else None; s.add(User(username=username, password_hash=hash_password(password), role=role)); s.commit(); s.close(); print('[OK] Created user '+username+' with role '+role)" "%NEW_USERNAME%" "%NEW_PASSWORD%" "%NEW_ROLE%"
if errorlevel 1 (
  pause
  exit /b 1
)
pause
exit /b 0

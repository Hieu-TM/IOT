@echo off
REM Aqua Scope - khoi dong toan bo he thong bang mot cu dup.
REM
REM Chay uvicorn TU GOC REPO voi --app-dir web/backend: `python -m` dua thu muc
REM hien tai (goc repo) vao sys.path de `import ml.infer...` chay duoc, con
REM --app-dir dua web/backend vao de `app.main` chay duoc. Doi cach khoi dong
REM thi kiem lai ca hai import do.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay python. Cai Python 3.11+ va tich "Add to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Tao moi truong ao .venv ...
  python -m venv .venv || (echo [LOI] Tao .venv that bai. & pause & exit /b 1)
)

set PY=.venv\Scripts\python.exe

if not exist ".venv\.deps-installed" (
  echo [2/3] Cai thu vien lan dau, doi mot chut ...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r web\requirements.txt || (echo [LOI] Cai web deps that bai. & pause & exit /b 1)
  "%PY%" -m pip install -r ml\requirements-infer.txt || (echo [LOI] Cai ml deps that bai. & pause & exit /b 1)
  echo ok > ".venv\.deps-installed"
)

echo [3/3] Khoi dong Aqua Scope tai http://localhost:8000
start "" http://localhost:8000
"%PY%" -m uvicorn --app-dir web/backend app.main:app --host 0.0.0.0 --port 8000

if errorlevel 1 (
  echo [LOI] Uvicorn thoat voi loi. Kiem cong 8000 co dang bi chiem khong.
  pause
  exit /b 1
)

endlocal

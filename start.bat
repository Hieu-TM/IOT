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

REM Ma loi 3 = uvicorn.config.STARTUP_FAILURE (vd: cong 8000 dang bi chiem) -
REM day la ma loi RIENG cua uvicorn cho "khong khoi dong duoc", da xac minh
REM trong ma nguon uvicorn cai trong .venv. Dung "if errorlevel 3 if not
REM errorlevel 4" (khop CHINH XAC ma 3) thay vi "if errorlevel 1" (khop MOI ma
REM >=1) vi ma rong hon se bao loi GIA khi operator bam Ctrl+C de dung binh
REM thuong: cmd.exe hien "Terminate batch job (Y/N)?", va tra loi N roi ve
REM day voi mot errorlevel khac 3 (uvicorn thoat sach da tat KeyboardInterrupt,
REM khong goi sys.exit(3) vi server.started=True). Kiem dung ma 3 tranh bao
REM loi gia tren duong dung pho bien nhat.
if errorlevel 3 if not errorlevel 4 (
  echo [LOI] Uvicorn thoat voi ma loi 3 - khong khoi dong duoc. Kiem cong 8000 co dang bi chiem khong ^(vd: mot start.bat khac dang chay^).
  pause
  exit /b 1
)

endlocal

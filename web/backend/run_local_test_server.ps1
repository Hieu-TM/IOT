$env:AQUA_SCOPE_DATABASE_URL = 'sqlite:///E:/iykyk/S4/IOT102/IOT/web/backend/data/aqua_scope_local_test.db'
$env:AQUA_SCOPE_SESSION_SECRET = 'local-test-session-secret-change-me'
$env:AQUA_SCOPE_ADMIN_USERNAME = 'admin'
$env:AQUA_SCOPE_ADMIN_PASSWORD = 'adminpass1234'
$env:AQUA_SCOPE_COOKIE_SECURE = 'false'

Set-Location -LiteralPath 'E:\iykyk\S4\IOT102\IOT\web\backend'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

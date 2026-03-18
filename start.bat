@echo off
echo ============================================
echo   MKJ SUPA CUP Development Servers
echo ============================================
echo.

:: Activate Python venv
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate
)

:: Start Django API server in background
echo Starting Django API on http://127.0.0.1:8000 ...
start "Django" cmd /c "python manage.py runserver 8000"

:: Start Vite React dev server in background
echo Starting React frontend on http://localhost:5173 ...
start "Vite" cmd /c "cd frontend && npm run dev"

echo.
echo Both servers running. Close this window to stop them.
echo   Django API:  http://127.0.0.1:8000
echo   React SPA:   http://localhost:5173
echo.
pause

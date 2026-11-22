@echo off
cd /d "%~dp0"
echo Starting RentEase at http://127.0.0.1:8000/  (press Ctrl+C to stop)
start "" http://127.0.0.1:8000/
"%~dp0venv\Scripts\python.exe" manage.py runserver
pause

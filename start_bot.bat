@echo off
echo Starting Discord Virtual Fisher Bot...
IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run setup.bat first!
    pause
    exit /b
)
call .venv\Scripts\activate
python user_auto_fisher.py
pause

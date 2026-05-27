@echo off
echo ==============================================
echo     Discord Virtual Fisher Bot - Auto Setup
echo ==============================================
echo.

:: Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.7+ and check "Add Python to PATH".
    pause
    exit /b
)

:: Create virtual environment
echo [1/3] Creating Python Virtual Environment (.venv)...
python -m venv .venv

:: Activate and install requirements
echo [2/3] Installing required packages...
call .venv\Scripts\activate
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

:: Setup .env file
echo [3/3] Setting up configuration...
IF NOT EXIST ".env" (
    copy .env.example .env >nul 2>&1
    echo [SUCCESS] Created .env file from .env.example.
    echo Please open the .env file in Notepad/VS Code and add your tokens.
) ELSE (
    echo [SKIP] .env file already exists.
)

echo.
echo ==============================================
echo Setup Complete!
echo You can now edit the .env file with your details.
echo To run the bot later, just double-click start_bot.bat
echo ==============================================
pause

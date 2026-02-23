@echo off
echo === Video Uniqueluzer Setup ===
cd /d "%~dp0"

echo Creating virtual environment...
python -m venv venv

echo Installing dependencies...
venv\Scripts\pip install --prefer-binary -r requirements.txt

echo.
echo Setup complete!
echo.
echo 1. Copy .env.example to .env
echo 2. Set BOT_TOKEN in .env
echo 3. Run: run.bat
pause

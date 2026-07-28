@echo off
echo ============================================
echo   Affiliate Marketing System - Setup
echo ============================================
echo.

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [2/4] Installing dependencies...
pip install -r requirements.txt

echo [3/4] Setting up config...
if not exist .env (
    copy .env.example .env
    echo.
    echo  IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY
    echo  Then add affiliate network credentials as you join them.
    echo.
)

echo [4/4] Creating logs directory...
if not exist logs mkdir logs

echo.
echo ============================================
echo   Setup complete!
echo.
echo   1. Edit .env with your API keys
echo   2. Run: python main.py
echo   3. Open: http://localhost:8000
echo ============================================
pause

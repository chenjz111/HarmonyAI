@echo off
chcp 65001 >nul
echo.
echo Installing dependencies (first run may take a while)...
pip install -r requirements.txt -q
echo.
echo Starting HarmonyAI backend stub...
echo API docs: http://localhost:8000/docs
echo.
python server.py
pause

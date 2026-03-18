@echo off
echo.
echo  ============================================================
echo  MPD COMMAND - Starting Up
echo  ============================================================
echo.
echo  Installing required components (first time only)...
echo.
pip install dash plotly pandas numpy scipy lasio openpyxl 2>nul >nul
echo  Done.
echo.
echo  Starting MPD Command...
echo  When you see "Dash is running" below, open your web browser
echo  and go to:
echo.
echo      http://127.0.0.1:8050
echo.
echo  To stop the program, close this window.
echo  ============================================================
echo.
cd /d "%~dp0"
python app.py
pause

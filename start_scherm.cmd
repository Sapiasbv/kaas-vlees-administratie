@echo off
REM Start het scherm voor de voorraadcorrectie. Sluit dit venster om te stoppen.
cd /d "%~dp0"
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8501"
python -m streamlit run src\kva\scherm.py
pause

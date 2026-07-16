@echo off
cd /d "%~dp0"
C:\Python314\python.exe -m streamlit run app.py --server.headless false
pause

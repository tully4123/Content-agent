@echo off
title PubCam Agent (close this window to quit the app)
cd /d "%~dp0"
C:\Python314\python.exe -m streamlit run streamlit_app.py --server.headless false
pause

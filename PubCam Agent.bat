@echo off
title PubCam Agent (close this window to quit the app)
cd /d "%~dp0"
py -m streamlit run streamlit_app.py --server.headless false
pause

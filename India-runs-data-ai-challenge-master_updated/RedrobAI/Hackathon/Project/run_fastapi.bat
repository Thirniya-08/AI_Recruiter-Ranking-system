@echo off
REM FastAPI Server Start Script for Redrob Candidate Ranking System
REM This script starts the FastAPI server on http://127.0.0.1:8000

echo.
echo ========================================
echo Redrob Candidate Ranking System (FastAPI)
echo ========================================
echo.
echo Starting FastAPI server...
echo.
echo Web UI:  http://127.0.0.1:8000
echo API Docs: http://127.0.0.1:8000/docs
echo ReDoc:   http://127.0.0.1:8000/redoc
echo.

python app_fastapi.py

pause

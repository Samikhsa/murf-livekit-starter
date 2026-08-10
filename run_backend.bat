@echo off
title Murf LiveKit - Backend Agent
cd /d "%~dp0backend"
set "PATH=%PATH%;%USERPROFILE%\.local\bin"
echo Starting Backend Agent...
uv run python src/agent.py dev
pause

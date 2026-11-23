@echo off
cd /d "%~dp0"
python -m enosh_sdl.experiments --out results\v0_3
pause

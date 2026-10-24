@echo off
cd /d "%~dp0"
set "FRIDAY_TTS_ENGINE=edge"
set "FRIDAY_EDGE_VOICE=en-US-AvaNeural"
set "FRIDAY_EDGE_RATE=+0%"
python assistant.py

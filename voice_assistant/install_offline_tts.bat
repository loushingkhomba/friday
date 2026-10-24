@echo off
cd /d "%~dp0"
python -m pip install --no-index --find-links offline_packages --constraint offline_constraints.txt piper-tts==1.8.0 winrt-runtime==3.2.1 winrt-Windows.Foundation==3.2.1 winrt-Windows.Media.SpeechSynthesis==3.2.1 winrt-Windows.Storage.Streams==3.2.1
if errorlevel 1 (
    echo Offline speech packages could not be installed from the bundled wheelhouse.
    exit /b 1
)
echo Piper and Windows offline speech support are installed.

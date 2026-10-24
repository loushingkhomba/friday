@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Installation complete!
echo.
echo Make sure Ollama is installed and running:
echo 1. Install from https://ollama.com
echo 2. Friday routes tasks across local Llama 3.2, Qwen 3.5 9B, and Gemma 4 26B.
echo    Check installed models with: ollama list
echo 3. Then run: python assistant.py
echo.
pause


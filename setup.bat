@echo off
setlocal

REM Install required Python dependencies.
python -m pip install --upgrade pip
python -m pip install torch transformers Pillow pillow-heif tqdm pytest

if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo Setup complete. You can now run the renamer with run_renamer.bat.
pause
exit /b 0

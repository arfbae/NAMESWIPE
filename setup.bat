@echo off

REM Check for Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python 3.8+ from python.org.
    echo Make sure to check 'Add Python to PATH' during installation.
    pause
    exit /b 1
)

REM Install required Python packages
echo Installing required Python packages...
pip install torch transformers Pillow pillow-heif tqdm
if %errorlevel% neq 0 (
    echo Failed to install Python packages. Please check your internet connection and try again.
    pause
    exit /b 1
)

echo Setup complete. You can now run the image renamer using run_renamer.bat.
pause
exit /b 0

@echo off
setlocal

set INPUT_DIR=%~dp0input_images
set OUTPUT_DIR=%~dp0SB3D_output
set CONFIG=%~dp0config.json

if not exist "%INPUT_DIR%" mkdir "%INPUT_DIR%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

if not exist "%CONFIG%" (
    echo Config file not found. Creating a default one...
    copy NUL "%CONFIG%" >nul
)

echo Starting NameSwipe image renamer...
echo Input folder: %INPUT_DIR%
echo Output folder: %OUTPUT_DIR%
echo.
python "%~dp0image_renamer.py" --input-dir "%INPUT_DIR%" --output-dir "%OUTPUT_DIR%" --config "%CONFIG%"

if errorlevel 1 (
    echo The image renaming process finished with errors.
    pause
    exit /b 1
)

echo Image renamer finished.
pause
exit /b 0

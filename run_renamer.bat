@echo off

REM Define input and output folders
set INPUT_FOLDER=input_images
set SB3D_FOLDER=SB3D_output

REM Create folders if they don't exist
if not exist %INPUT_FOLDER%\ mkdir %INPUT_FOLDER%
if not exist %SB3D_FOLDER%\ mkdir %SB3D_FOLDER%

echo Starting Image Renamer Tool...
echo Make sure your images are in the ".\%INPUT_FOLDER%" folder.
echo Renamed images will be moved to the ".\%SB3D_FOLDER%" folder.
echo Press any key to start...
pause >nul

python image_renamer.py

echo Image Renamer Tool finished.
pause
exit /b 0

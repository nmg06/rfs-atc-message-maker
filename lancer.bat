@echo off
setlocal
cd /d "%~dp0"
if exist "dist\RFSATCMessageMaker-v5\RFSATCMessageMaker.exe" (
    start "" "dist\RFSATCMessageMaker-v5\RFSATCMessageMaker.exe"
    exit /b 0
)
if exist "dist\RFSATCMessageMaker-v4\RFSATCMessageMaker.exe" (
    start "" "dist\RFSATCMessageMaker-v4\RFSATCMessageMaker.exe"
    exit /b 0
)
if exist "dist\RFSATCMessageMaker-v3\RFSATCMessageMaker.exe" (
    start "" "dist\RFSATCMessageMaker-v3\RFSATCMessageMaker.exe"
    exit /b 0
)
if exist "dist\RFSATCMessageMaker-v2\RFSATCMessageMaker.exe" (
    start "" "dist\RFSATCMessageMaker-v2\RFSATCMessageMaker.exe"
    exit /b 0
)
if exist "dist\RFSATCMessageMaker\RFSATCMessageMaker.exe" (
    start "" "dist\RFSATCMessageMaker\RFSATCMessageMaker.exe"
    exit /b 0
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "main.py"
    exit /b 0
)
echo L'executable n'a pas encore ete construit.
echo Lancez build_exe.bat une fois, puis relancez ce fichier.
pause
exit /b 1

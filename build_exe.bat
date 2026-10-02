@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

if not exist ".venv\Scripts\python.exe" (
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --distpath dist RFSATCMessageMaker.spec
if errorlevel 1 goto :error

echo.
echo Construction terminee : dist\RFSATCMessageMaker\RFSATCMessageMaker.exe
exit /b 0

:error
echo.
echo La construction a echoue. Consultez les messages ci-dessus.
exit /b 1

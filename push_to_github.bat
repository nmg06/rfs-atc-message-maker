@echo off
cd /d "%~dp0"
echo ========================================================
echo   Envoi du projet vers GitHub : rfs-atc-message-maker
echo ========================================================
echo.
git push -u origin main --tags
echo.
if errorlevel 1 (
    echo [ERREUR] L'envoi a echoue. Verifiez votre connexion ou authentification GitHub.
) else (
    echo [SUCCES] Le code et les tags ont ete envoyes avec succes sur GitHub !
)
echo.
pause

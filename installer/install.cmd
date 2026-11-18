@echo off
rem Keep this file ASCII-only: cmd.exe decodes a batch file with the active code page,
rem so non-ASCII text here can be split into broken commands. Japanese lives in install.ps1.
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (
    echo Installation failed. See the message above and the log path.
) else (
    echo Done. You can close this window.
)
pause
exit /b %CODE%

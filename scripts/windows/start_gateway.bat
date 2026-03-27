@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0start_gateway.ps1" %*
exit /b %ERRORLEVEL%

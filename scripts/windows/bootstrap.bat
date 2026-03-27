@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
exit /b %ERRORLEVEL%

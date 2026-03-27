@echo off
setlocal EnableExtensions

powershell -ExecutionPolicy Bypass -File "%~dp0qmt.ps1" %*
exit /b %ERRORLEVEL%

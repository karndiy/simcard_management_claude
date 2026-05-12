@echo off
chcp 65001 >nul
echo ============================================
echo   KarnDIY SIM Card Management - Git Setup
echo   Repo: karndiy/simcard_management_claude
echo ============================================
echo.

cd /d "%~dp0"

echo [1/5] Initializing Git repository...
git init -b main 2>nul
if errorlevel 1 (
    git init
    git branch -M main
)

echo.
echo [2/5] Setting git config...
git config user.email "karndiy@gmail.com"
git config user.name "KarnDIY"

echo.
echo [3/5] Adding all files...
git add -A
echo Files staged:
git status --short

echo.
echo [4/5] Creating first commit...
git commit -m "feat: initial commit - SIM Card Management MVP v1.0"

echo.
echo [5/5] Pushing to GitHub...
git remote remove origin 2>nul
git remote add origin https://github.com/karndiy/simcard_management_claude.git
git push -u origin main

echo.
echo ============================================
echo   SUCCESS! Code is now on GitHub
echo   https://github.com/karndiy/simcard_management_claude
echo ============================================
echo.
echo   NEXT STEP: Go to railway.app and deploy!
echo ============================================
pause

@echo off
chcp 65001 >nul
title GitHub 推送工具

echo ========================================
echo   股票复盘系统 - GitHub 推送
echo ========================================
echo.

cd /d "%~dp0"

REM 检查是否安装了Git
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Git
    echo 请先安装 Git: https://git-scm.com/
    pause
    exit /b 1
)

REM 检查是否有远程仓库
echo [1/3] 检查仓库状态...
git remote -v >nul 2>&1
if errorlevel 1 (
    echo [初始化] 初始化Git仓库...
    git init
)

REM 设置远程仓库
echo.
echo [2/3] 设置远程仓库...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/flysky126/stock-review.git

REM 添加所有文件
echo.
echo [3/3] 提交并推送...
echo.

REM 添加gitignore中忽略的文件
git add .gitignore app.py config.py models.py requirements.txt Procfile README.md DEPLOY.md routes/ templates/ build.py build_windows.bat
git commit -m "股票复盘系统 - 初始版本"

echo.
echo ========================================
echo   准备推送到 GitHub
echo ========================================
echo.
echo 请输入你的 GitHub 用户名和密码
echo.

git push -u origin master

if errorlevel 1 (
    echo.
    echo [错误] 推送失败
    echo 如果开启了两步验证，请使用 Personal Access Token
) else (
    echo.
    echo ========================================
    echo   推送成功!
    echo ========================================
    echo.
    echo 仓库地址: https://github.com/flysky126/stock-review
)

pause

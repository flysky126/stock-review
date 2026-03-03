@echo off
chcp 65001 >nul
title 股票复盘系统打包工具
echo ============================================
echo     股票复盘系统 - Windows打包工具
echo ============================================
echo.

cd /d "%~dp0"

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [检查] Python已安装

REM 安装打包依赖
echo.
echo [1/4] 安装打包依赖...
pip install pyinstaller flask flask-sqlalchemy
if errorlevel 1 (
    echo [错误] 安装依赖失败
    pause
    exit /b 1
)

REM 清理旧文件
echo.
echo [2/4] 清理旧文件...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

REM 检查模板目录
echo.
echo [3/4] 检查文件...
if not exist "app.py" (
    echo [错误] 缺少 app.py
    pause
    exit /b 1
)
if not exist "templates" (
    echo [错误] 缺少 templates 目录
    pause
    exit /b 1
)
echo [OK] 文件检查通过

REM 打包
echo.
echo [4/4] 开始打包...
echo.
pyinstaller --name=StockReview --onefile --windowed --add-data="templates;templates" app.py --clean --noconfirm 2>&1

echo.
echo ============================================
if exist "dist\StockReview.exe" (
    echo     打包成功!
    echo ============================================
    echo.
    echo 可执行文件: %cd%\dist\StockReview.exe
    echo.
    echo 提示: 首次运行会在同目录创建数据库文件
) else (
    echo     打包失败!
    echo ============================================
    echo.
    echo 请检查上方错误信息
    echo 或尝试手动运行:
    echo   pyinstaller --name=StockReview --onefile --windowed --add-data="templates;templates" app.py
)
echo.
pause

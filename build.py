#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票复盘系统 - 打包脚本
运行: python build.py
"""

import os
import sys
import subprocess
import shutil

def check_python():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"[错误] 需要 Python 3.8+, 当前版本: {version.major}.{version.minor}")
        return False
    print(f"[OK] Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

def install_deps():
    """安装依赖"""
    print("\n[1/4] 安装依赖...")

    deps = ['pyinstaller', 'flask', 'flask-sqlalchemy']
    for dep in deps:
        try:
            __import__(dep.replace('-', '_'))
            print(f"  {dep}: 已安装")
        except ImportError:
            print(f"  安装 {dep}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])

    print("  依赖安装完成")

def check_files():
    """检查必要文件"""
    print("\n[2/4] 检查文件...")

    required = ['app.py', 'templates', 'models.py', 'routes', 'config.py']
    for f in required:
        if not os.path.exists(f):
            print(f"  [错误] 缺少 {f}")
            return False
        print(f"  {f}: OK")

    return True

def build():
    """打包"""
    print("\n[3/4] 开始打包...")

    # 清理旧文件
    for d in ['dist', 'build']:
        if os.path.exists(d):
            shutil.rmtree(d)

    # 删除旧spec文件
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)

    # PyInstaller命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=StockReview',
        '--onefile',
        '--windowed',
        '--add-data=templates:templates',
        '--clean',
        '--noconfirm',
        'app.py'
    ]

    print(f"  运行命令: {' '.join(cmd)}")

    try:
        subprocess.check_call(cmd, stdout=sys.stdout, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [错误] 打包失败: {e}")
        return False

def main():
    print("=" * 50)
    print("  股票复盘系统 - 打包工具")
    print("=" * 50)

    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if not check_python():
        input("\n按回车退出...")
        sys.exit(1)

    install_deps()

    if not check_files():
        input("\n按回车退出...")
        sys.exit(1)

    if not build():
        input("\n按回车退出...")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  打包完成!")
    print("=" * 50)

    exe_path = os.path.join('dist', 'StockReview.exe')
    if os.path.exists(exe_path):
        print(f"\n可执行文件: {os.path.abspath(exe_path)}")
    else:
        print("\n[错误] 未找到exe文件")

    input("\n按回车退出...")

if __name__ == '__main__':
    main()

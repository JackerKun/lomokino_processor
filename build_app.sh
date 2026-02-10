#!/bin/bash
# Build script for creating standalone application

echo "🔨 开始构建 LomoKino GUI 应用..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  虚拟环境不存在，请先运行: ./install_gui.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Install PyInstaller if not present
echo "📦 安装 PyInstaller..."
pip install pyinstaller

# Clean previous builds
echo "🧹 清理旧的构建文件..."
rm -rf build dist

# Build application
echo "🏗️  构建应用程序..."
pyinstaller lomokino_gui.spec

# Check if build was successful
if [ -d "dist/LomoKinoGUI.app" ]; then
    echo ""
    echo "✅ 构建成功!"
    echo "📱 应用位置: dist/LomoKinoGUI.app"
    echo ""
    echo "你可以:"
    echo "  1. 打开应用: open dist/LomoKinoGUI.app"
    echo "  2. 复制到应用程序文件夹: cp -r dist/LomoKinoGUI.app /Applications/"
else
    echo ""
    echo "❌ 构建失败"
    exit 1
fi

#!/bin/bash
# Install script for LomoKino GUI

echo "🚀 安装 LomoKino GUI 依赖..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  升级 pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 安装依赖包..."
pip install -r requirements_gui.txt

echo ""
echo "✅ 安装完成!"
echo ""
echo "运行 GUI 应用:"
echo "  ./run_gui.sh"
echo ""
echo "或者:"
echo "  source venv/bin/activate"
echo "  python lomokino_gui.py"

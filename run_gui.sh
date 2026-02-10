#!/bin/bash
# Run script for LomoKino GUI

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  虚拟环境不存在，请先运行: ./install_gui.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if PyQt6 is installed
python -c "import PyQt6" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  PyQt6 未安装，请先运行: ./install_gui.sh"
    exit 1
fi

# Run the GUI
echo "🚀 启动 LomoKino GUI..."
python lomokino_gui.py

#!/bin/bash

echo "======================================"
echo "LomoKino Film Strip Processor 安装脚本"
echo "======================================"

# 检查 Python3 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3，请先安装 Python3"
    exit 1
fi

echo "✅ 找到 Python3: $(python3 --version)"

# 创建虚拟环境
echo "📦 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "⚠️  虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo "📥 升级 pip..."
pip install --upgrade pip

# 安装依赖
echo "📥 安装依赖包..."
pip install opencv-python numpy

# 检查安装是否成功
echo "🔍 检查依赖安装..."
python3 -c "import cv2, numpy; print('✅ OpenCV 版本:', cv2.__version__); print('✅ NumPy 版本:', numpy.__version__)"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 安装完成！"
    echo ""
    echo "使用方法:"
    echo "  ./process_lomokino.sh                # 处理所有 jpg 文件"
    echo "  ./process_lomokino.sh 1.jpg          # 处理单个文件"
    echo "  python lomokino_processor.py --help  # 查看详细选项"
    echo ""
    echo "💡 提示: 每次使用前需要激活虚拟环境:"
    echo "  source venv/bin/activate"
else
    echo "❌ 安装失败，请检查错误信息"
    exit 1
fi
#!/bin/bash

# LomoKino Processing Script
# Simple wrapper to process lomokino film strips

echo "======================================"
echo "LomoKino Film Strip Processor"
echo "======================================"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境未找到，请先运行: ./install.sh"
    exit 1
fi

echo "🔄 激活虚拟环境..."
source venv/bin/activate

echo "🎬 开始处理 LomoKino 胶片..."
python lomokino_processor.py "$@"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 处理完成！"
    echo "📁 查看结果: output/ 目录"
    echo "🎥 视频文件: output/*_video.mp4"
    echo "📷 单独帧: output/*_frames/"
else
    echo "❌ 处理失败，请检查错误信息"
fi
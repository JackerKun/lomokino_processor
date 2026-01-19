# LomoKino Film Strip Processor

一个专门处理 LomoKino 胶片条的 Python 工具，能够自动提取胶片中的单独帧并生成视频文件。

## 功能特性

- 🎬 **自动帧检测**: 智能识别胶片条中的单独画面帧
- ✂️ **智能裁切**: 自动去除胶片孔、黑边和多余边距，只保留核心画面内容
- 🎥 **视频生成**: 将提取的帧自动拼接成 MP4 视频文件
- 📷 **批量处理**: 支持同时处理多张胶片图片
- 🔧 **灵活配置**: 支持自定义帧高度、输出目录和视频帧率

## 安装依赖

### 方法一：自动安装（推荐）

运行安装脚本会自动创建虚拟环境并安装所需依赖：

```bash
# 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate
pip install opencv-python numpy
```

### 方法二：手动安装

如果你已有 Python 环境，可以直接安装依赖：

```bash
pip install opencv-python numpy
```

## 快速开始

### 1. 使用便捷脚本（推荐）

```bash
# 处理当前目录下所有 .jpg 文件
./process_lomokino.sh

# 处理指定文件
./process_lomokino.sh 1.jpg

# 指定输出目录
./process_lomokino.sh --output-dir my_videos
```

### 2. 直接使用 Python 脚本

```bash
# 激活虚拟环境
source venv/bin/activate

# 处理所有 jpg 文件
python lomokino_processor.py

# 处理单个文件
python lomokino_processor.py 1.jpg

# 查看所有选项
python lomokino_processor.py --help
```

## 命令行参数

```
usage: lomokino_processor.py [-h] [--output-dir OUTPUT_DIR] [--frame-height FRAME_HEIGHT] [--fps FPS] [input]

参数说明:
  input                 输入图片文件或匹配模式 (默认: *.jpg)
  --output-dir, -o      输出目录 (默认: output)
  --frame-height, -f    手动指定帧高度
  --fps                 视频帧率 (默认: 12)
```

## 使用示例

### 基本用法

```bash
# 处理当前目录所有 jpg 文件
python lomokino_processor.py

# 处理特定文件
python lomokino_processor.py my_film.jpg

# 处理多个文件
python lomokino_processor.py "photo_*.jpg"
```

### 高级用法

```bash
# 自定义输出目录
python lomokino_processor.py --output-dir my_output

# 设置视频帧率为 24fps
python lomokino_processor.py --fps 24

# 手动指定帧高度（当自动检测失败时）
python lomokino_processor.py --frame-height 200

# 组合使用
python lomokino_processor.py 1.jpg 2.jpg --output-dir videos --fps 15
```

## 输出说明

程序会在指定的输出目录（默认为 `output/`）中创建以下文件：

```
output/
├── 1_frames/           # 提取的单独帧图片
│   ├── frame_000.jpg
│   ├── frame_001.jpg
│   └── ...
├── 1_video.mp4         # 生成的视频文件
├── 2_frames/
│   └── ...
└── 2_video.mp4
```

- **`{filename}_frames/`**: 包含从胶片条提取的所有单独帧
- **`{filename}_video.mp4`**: 由提取帧生成的视频文件

## 工作原理

1. **帧检测**: 使用边缘检测和霍夫线变换识别胶片条中的帧分隔线
2. **内容识别**: 分析亮度分布，自动识别每帧中的实际画面边界
3. **智能裁切**: 去除胶片孔、黑边和多余边距，只保留核心内容
4. **视频生成**: 将裁切后的帧按顺序拼接成 MP4 视频

## 支持的格式

- **输入**: JPG/JPEG 图片文件
- **输出**: 
  - 帧图片: JPG 格式
  - 视频: MP4 格式 (H.264 编码)

## 故障排除

### 常见问题

1. **依赖安装失败**
   ```bash
   # macOS 用户如遇到权限问题，使用虚拟环境
   python3 -m venv venv
   source venv/bin/activate
   pip install opencv-python numpy
   ```

2. **帧检测不准确**
   ```bash
   # 手动指定帧高度
   python lomokino_processor.py --frame-height 150
   ```

3. **视频生成失败**
   - 确保提取的帧数量足够（至少1帧）
   - 检查输出目录是否有写入权限

### 调试模式

运行程序时会显示详细信息：
- 检测到的帧数量
- 成功提取的帧数量
- 文件保存路径

## 系统要求

- Python 3.7+
- OpenCV (opencv-python)
- NumPy
- 支持的操作系统: macOS, Linux, Windows

## 作者

LomoKino Film Strip Processor 是一个专门为处理 LomoKino 胶片设计的工具。

## 许可证

本项目采用 MIT 许可证。
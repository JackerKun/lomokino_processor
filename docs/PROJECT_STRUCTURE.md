# 项目文件结构

```
lomokino-processor/
├── lomokino_processor.py      # 核心处理引擎 (命令行版本)
├── lomokino_gui.py            # GUI 应用主程序
├── lomokino_gui.spec          # PyInstaller 打包配置
│
├── README.md                  # 项目主说明文档
├── QUICKSTART.md              # 命令行版本快速开始
├── GUI_README.md              # GUI 版本详细文档
├── GUI_QUICKSTART.md          # GUI 版本快速开始
│
├── requirements_gui.txt       # GUI 版本依赖列表
│
├── Mac/Linux 脚本:
│   ├── install.sh            # 命令行版本安装脚本
│   ├── process_lomokino.sh   # 命令行版本处理脚本
│   ├── install_gui.sh        # GUI 版本安装脚本
│   ├── run_gui.sh            # GUI 版本运行脚本
│   └── build_app.sh          # Mac 应用打包脚本
│
├── Windows 脚本:
│   ├── install_gui.bat       # GUI 版本安装脚本
│   ├── run_gui.bat           # GUI 版本运行脚本
│   └── build_app.bat         # Windows 应用打包脚本
│
├── venv/                     # Python 虚拟环境 (安装后生成)
├── output/                   # 默认输出目录 (运行后生成)
│   ├── *_frames/            # 提取的帧图片
│   └── *_video.mp4          # 生成的视频
├── build/                    # 打包临时文件 (打包后生成)
└── dist/                     # 打包后的应用 (打包后生成)
    ├── LomoKinoGUI.app      # Mac 应用
    └── LomoKinoGUI.exe      # Windows 应用
```

## 文件说明

### 核心程序

| 文件 | 说明 | 用途 |
|------|------|------|
| `lomokino_processor.py` | 核心处理引擎 | 图片处理、帧提取、视频生成 |
| `lomokino_gui.py` | GUI 应用 | 图形界面、用户交互 |

### 文档

| 文件 | 说明 | 适用对象 |
|------|------|----------|
| `README.md` | 项目主文档 | 所有用户 |
| `QUICKSTART.md` | 命令行快速开始 | 命令行用户 |
| `GUI_README.md` | GUI 详细文档 | GUI 用户 |
| `GUI_QUICKSTART.md` | GUI 快速开始 | GUI 新手 |

### Mac/Linux 脚本

| 文件 | 功能 | 命令 |
|------|------|------|
| `install_gui.sh` | 安装 GUI 依赖 | `./install_gui.sh` |
| `run_gui.sh` | 运行 GUI 应用 | `./run_gui.sh` |
| `build_app.sh` | 打包 Mac 应用 | `./build_app.sh` |

### Windows 脚本

| 文件 | 功能 | 命令 |
|------|------|------|
| `install_gui.bat` | 安装 GUI 依赖 | 双击运行 |
| `run_gui.bat` | 运行 GUI 应用 | 双击运行 |
| `build_app.bat` | 打包 Windows 应用 | 双击运行 |

### 配置文件

| 文件 | 说明 |
|------|------|
| `requirements_gui.txt` | GUI 版本 Python 依赖 |
| `lomokino_gui.spec` | PyInstaller 打包配置 |

## 使用流程

### 首次使用 GUI 版本

```bash
# Mac/Linux
./install_gui.sh    # 1. 安装依赖
./run_gui.sh        # 2. 运行应用

# Windows
install_gui.bat     # 1. 安装依赖
run_gui.bat         # 2. 运行应用
```

### 打包独立应用

```bash
# Mac
./build_app.sh
# 结果: dist/LomoKinoGUI.app

# Windows
build_app.bat
# 结果: dist/LomoKinoGUI.exe
```

## 生成的目录

### output/
运行程序后自动创建的输出目录:
- 包含提取的帧图片 (`*_frames/`)
- 包含生成的视频文件 (`*_video.mp4`)

### venv/
Python 虚拟环境目录:
- 包含独立的 Python 依赖
- 避免与系统 Python 冲突

### build/ 和 dist/
打包应用后生成:
- `build/`: 打包临时文件
- `dist/`: 最终的独立应用

## 磁盘空间需求

| 项目 | 空间 |
|------|------|
| 源代码 | ~50 KB |
| 虚拟环境 | ~150 MB |
| 打包应用 | ~100-200 MB |
| 输出视频 | 取决于源图片大小 |

## 清理命令

```bash
# 清理虚拟环境
rm -rf venv

# 清理打包文件
rm -rf build dist

# 清理输出文件
rm -rf output

# 清理所有生成文件
rm -rf venv build dist output
```

## 开发者注意事项

### 修改 GUI 代码后
```bash
# 重新运行应用查看效果
./run_gui.sh

# 或重新打包
./build_app.sh
```

### 添加新依赖
```bash
# 1. 编辑 requirements_gui.txt
echo "new-package>=1.0.0" >> requirements_gui.txt

# 2. 重新安装
./install_gui.sh
```

### 修改打包配置
编辑 `lomokino_gui.spec` 文件,然后重新打包。

# 快速开始指南

5分钟快速上手 LomoKino 胶片处理工具。

## GUI 版本 (推荐新手)

### 第一步: 安装

**Mac/Linux**:
```bash
chmod +x install_gui.sh run_gui.sh
./install_gui.sh
```

**Windows**:
```batch
双击运行 install_gui.bat
```

### 第二步: 启动

**Mac/Linux**:
```bash
./run_gui.sh
```

**Windows**:
```batch
双击运行 run_gui.bat
```

### 第三步: 使用

#### 方式一: 自动检测 (最简单)

1. **添加胶片** - 拖拽或点击"添加胶片"按钮
2. **预览胶片** - 点击列表中的胶片查看预览
3. **提取帧** - 点击"提取所有帧"自动提取
4. **查看结果** - 右侧显示提取的所有帧
5. **删除不需要的帧** - 点击帧右上角的红色 × 按钮 (可选)
6. **生成视频** - 设置 FPS 后点击"生成视频"

#### 方式二: 手动选择框 (更精确)

1. **添加胶片** - 加载你的胶片图片
2. **添加选择框** - 点击 ➕ 按钮
3. **调整选择框**:
   - 拖动内部: 移动位置
   - 拖动边缘/角: 调整大小
4. **复制选择框** - 选中后点击 📋 复制 (保持相同尺寸)
5. **逐个定位** - 移动每个选择框到对应的帧
6. **提取** - 点击 "✂️ 提取" 按钮
7. **生成视频** - 设置 FPS 后点击"生成视频"

### GUI 功能说明

#### 检测参数调节

如果自动检测结果不理想,可以调整:

- **检测灵敏度**:
  - 自动 (默认) - 智能选择
  - 低 (保守) - 只检测明显的分隔线
  - 中 (推荐) - 适合大多数情况
  - 高 (激进) - 检测更多帧

- **最小帧间距**:
  - 0 (自动) - 根据灵敏度自动计算
  - 手动值 - 强制使用指定间距 (像素)

#### 帧管理

- **删除单个帧**: 点击帧右上角的 × 按钮
- **清空所有帧**: 点击 "🧹 清空所有帧" 按钮
- **大图查看**: 双击帧弹出全屏查看窗口
- **键盘导航**: 在大图查看器中使用左右箭头切换

#### 提取模式

- **自动检测模式**: 智能识别帧分隔线
- **手动选择框模式**: 精确控制提取区域
- **混合模式**: 先自动后手动微调

---

## 命令行版本 (高级用户)

### 第一步: 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install opencv-python numpy
```

### 第二步: 准备胶片

将你的 LomoKino 胶片图片 (.jpg 格式) 放在项目目录下

### 第三步: 处理胶片

**处理当前目录所有 .jpg 文件**:
```bash
python lomokino_processor.py
```

**处理单个文件**:
```bash
python lomokino_processor.py my_film.jpg
```

**处理多个文件**:
```bash
python lomokino_processor.py film1.jpg film2.jpg film3.jpg
```

### 高级用法

**自定义输出目录**:
```bash
python lomokino_processor.py --output-dir my_videos my_film.jpg
```

**设置视频帧率**:
```bash
python lomokino_processor.py --fps 24 my_film.jpg
```

**手动指定帧高度** (当自动检测失败时):
```bash
python lomokino_processor.py --frame-height 200 my_film.jpg
```

**组合使用**:
```bash
python lomokino_processor.py --output-dir videos --fps 15 film1.jpg film2.jpg
```

### 命令行参数

```
usage: lomokino_processor.py [-h] [--output-dir DIR] [--frame-height HEIGHT]
                              [--fps FPS] [--min-frame-distance PIXELS]
                              [--detection-sensitivity {auto,low,medium,high}]
                              [input ...]

参数说明:
  input                 输入图片文件或匹配模式 (默认: *.jpg)
  --output-dir, -o      输出目录 (默认: output)
  --frame-height, -f    手动指定帧高度 (像素)
  --fps                 视频帧率 (默认: 12)
  --min-frame-distance  最小帧间距 (像素, 0=自动)
  --detection-sensitivity  检测灵敏度 (auto/low/medium/high)
```

---

## 输出结果

处理完成后,在输出目录中查看结果:

```
output/
├── film1_frames/       # 提取的单独帧
│   ├── frame_000.jpg
│   ├── frame_001.jpg
│   ├── frame_002.jpg
│   └── ...
└── film1_video.mp4     # 生成的视频文件
```

---

## 常见问题

### Q1: 帧检测不准确怎么办?

**GUI版本**:
1. 调整"检测灵敏度" (自动 → 低 或 高)
2. 调整"最小帧间距" (增加或减小)
3. 重新点击"提取所有帧"

或者使用手动选择框模式精确控制

**命令行版本**:
```bash
# 帧数过多,降低灵敏度
python lomokino_processor.py --detection-sensitivity low film.jpg

# 帧数过少,提高灵敏度
python lomokino_processor.py --detection-sensitivity high film.jpg

# 手动设置最小帧间距
python lomokino_processor.py --min-frame-distance 80 film.jpg
```

### Q2: 如何删除不需要的帧?

**GUI版本**:
- 点击帧右上角的红色 × 按钮
- 确认删除

**命令行版本**:
- 进入 `output/film_frames/` 目录
- 手动删除不需要的帧图片
- 重新运行只生成视频 (需手动操作)

### Q3: 视频生成失败?

检查:
- 是否至少提取了 1 帧
- 输出目录是否有写入权限
- 是否安装了 opencv-python

### Q4: 如何提高视频质量?

- 使用高分辨率的源图片
- 选择合适的 FPS:
  - 8-12 FPS: 胶片风格
  - 24-30 FPS: 流畅播放
- 确保提取的帧画面完整

### Q5: 支持批量处理吗?

**GUI版本**:
- 可以添加多张胶片
- 点击"提取所有帧"一次性处理

**命令行版本**:
```bash
python lomokino_processor.py *.jpg
# 或
python lomokino_processor.py film1.jpg film2.jpg film3.jpg
```

---

## 推荐工作流程

### 新手推荐

1. 使用 **GUI 版本**
2. 选择 **自动检测模式**
3. 检查结果后生成视频
4. 如不满意,调整参数重试

### 高级用户推荐

1. 使用 **命令行版本** 批量处理
2. 或使用 **GUI 手动选择框模式** 精确控制
3. 保存最佳参数设置
4. 对相似胶片使用相同设置

---

## 下一步

- 查看 [详细功能说明](docs/) 了解更多
- 阅读 [版本更新日志](docs/CHANGELOG.md) 查看最新改进
- 遇到问题查看 [FAQ 文档](docs/FAQ.md)

---

**就这么简单! 现在开始处理你的胶片吧!** 🎬

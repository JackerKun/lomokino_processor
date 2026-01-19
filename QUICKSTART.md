# 快速开始指南

## 🚀 3 步搞定

### 第一步：安装依赖
```bash
./install.sh
```

### 第二步：放入胶片图片
将你的 LomoKino 胶片图片（.jpg 格式）放在当前目录下

### 第三步：处理胶片
```bash
./process_lomokino.sh
```

## 🎯 就这么简单！

处理完成后，在 `output/` 目录中查看结果：
- `*_video.mp4` - 生成的视频文件
- `*_frames/` - 提取的单独帧

## 💡 更多用法

```bash
# 处理单个文件
./process_lomokino.sh my_film.jpg

# 处理特定文件
./process_lomokino.sh 1.jpg 2.jpg

# 查看帮助
python lomokino_processor.py --help
```

## 🔧 如果遇到问题

1. **权限问题**: `chmod +x *.sh`
2. **依赖问题**: 重新运行 `./install.sh`
3. **Python问题**: 确保安装了 Python 3.7+

搞定！享受你的 LomoKino 视频吧！🎬
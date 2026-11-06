# 第三方组件与分发

应用代码遵循根目录 MIT 许可；第三方许可独立适用。

| 组件 | 用途 | 上游 |
| --- | --- | --- |
| PyQt6 / Qt | 桌面界面 | https://www.riverbankcomputing.com/software/pyqt/ ，https://www.qt.io/licensing/ |
| OpenCV | 图片解码、几何与备用视频编码 | https://github.com/opencv/opencv |
| NumPy | 像素数组 | https://github.com/numpy/numpy |
| imageio-ffmpeg | FFmpeg 可执行文件发现与分发 | https://github.com/imageio/imageio-ffmpeg |
| FFmpeg / libx264 | H.264 视频 | https://ffmpeg.org/legal.html ，https://www.videolan.org/developers/x264.html |
| PyInstaller | 应用打包 | https://pyinstaller.org/en/stable/license.html |

PyQt6 存在 GPL / 商业许可选择，不应将 PyQt6 和 Qt 的许可混为一谈。FFmpeg 构建配置影响其许可；本机 imageio-ffmpeg 0.8.1 的 FFmpeg 9.0 显示 `--enable-gpl`、`--enable-libx264`。公开分发应用时，需要按实际组合履行第三方许可、保留声明和对应源码提供等义务，不能仅附项目 MIT 即认为足够。仓库使用开放源码开发方式；有闭源商业分发需求请先核对相应商业授权。

构建依赖版本会更新，发行前核对实际 wheel 的 license 文件和 FFmpeg `-version` 输出。有关功能和测试的说明不构成法律意见。

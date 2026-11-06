# 4.0 本地验证记录

日期：2026-11-06。环境：macOS ARM64，Python 3.13.2，PyQt6 6.10.2 / Qt 6.10.0，OpenCV 4.13.0，NumPy 2.4.1，imageio-ffmpeg 0.8.1。

- `QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests -v`：25 项通过。
- `venv/bin/python scripts/validate_demo.py`：9/9 文件帧数吻合，共 44 帧。只核对帧数；无实拍逐像素人工标注真值。
- PyInstaller 6.18.0 构建 `dist/LomoKinoGUI.app` 成功，`codesign --verify --deep --strict` 通过。
- 最终应用无界面 `--self-test`：H.264 视频读回 3 帧、6 FPS、240 × 80，同时输出 PNG 与清单。
- 实际 macOS 应用界面：导入 demo/6.jpg、复查状态、逐帧大图切换、识别 / 导出属性、工程保存恢复，以及导出完成状态。导出完成界面报告 4 帧、1080 × 410、12 FPS。
- README、英文 README、快速上手与文档索引的本地链接检查通过；`git diff --check` 无空白错误。

Windows x64 与 macOS Intel 的打包任务已配置，但本次没有在这些原生系统运行或触发 GitHub 构建；后续以 CI 和实际机器验证为准。应用尚未完成 Apple 公证。

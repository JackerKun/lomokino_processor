#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then echo '先运行 ./install_gui.sh 创建虚拟环境' >&2; exit 1; fi
"$PYTHON" -m pip install -r requirements_gui.txt 'pyinstaller>=6.10,<7'
QT_QPA_PLATFORM=offscreen "$PYTHON" -m unittest discover -s tests -v
"$PYTHON" -m PyInstaller --noconfirm lomokino_gui.spec
if [[ "$(uname -s)" == Darwin ]]; then
  codesign --force --deep --sign - dist/LomoKinoGUI.app
  echo '应用已生成：dist/LomoKinoGUI.app（本机架构，临时签名）'
else
  echo '程序已生成：dist/LomoKinoGUI/'
fi

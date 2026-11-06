#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv venv
venv/bin/python -m pip install -r requirements_gui.txt
echo '运行 ./run_gui.sh；测试数据：./run_gui.sh --demo'

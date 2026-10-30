#!/bin/bash
# تشغيل محلي على macOS بنقرة مزدوجة (أول مرة: قد تحتاج: chmod +x run_mac.command)
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv || { echo "يلزم تثبيت Python 3.12 أو أحدث من python.org"; read -r; exit 1; }
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi
./.venv/bin/streamlit run app.py

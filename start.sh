#!/usr/bin/env bash
# Specs-to-Diagrams Agent Launcher
cd "$(dirname "$0")"

echo "=================================================="
echo "  🚀 تشغيل وكيل Specs-to-Diagrams (واجهة المحادثة)"
echo "=================================================="

# تفعيل البيئة الافتراضية
source venv/bin/activate

# فتح المتصفح تلقائياً بعد ثانية واحدة في الخلفية
(sleep 1.5 && xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null) &

# تشغيل الخادم
python app.py

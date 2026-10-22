# 🤖 Specs-to-Diagrams Autonomous Agent
### وكيل ذكي مستقل لتحويل المواصفات التقنية إلى مخططات برمجية مع واجهة محادثة عصرية

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-orange.svg)](https://aistudio.google.com/)
[![Graphviz](https://img.shields.io/badge/Render-Graphviz%20%7C%20Mermaid-green.svg)](https://graphviz.org/)

---

## 📑 الفهرس / Table of Contents
1. [نظرة عامة / Overview](#-نظرة-عامة--overview)
2. [طريقة التشغيل السريعة / Quick Start](#-طريقة-التشغيل-السريعة--quick-start)
3. [التشغيل عبر سطر الأوامر / CLI Usage](#-التشغيل-عبر-سطر-الأوامر--cli-usage)
4. [معمارية النظام ودورة العمل / Architecture](#-معمارية-النظام--architecture)
5. [المتطلبات والتثبيت / Installation](#-المتطلبات-والتثبيت--installation)
6. [هيكل المشروع / Project Structure](#-هيكل-المشروع--project-structure)
7. [English Documentation](#-english-documentation)

---

## 🌟 نظرة عامة / Overview

نظام ذكاء اصطناعي مستقل ومبني على **LangGraph** يقوم باستقبال متطلبات الأنظمة، وهياكل قواعد البيانات، والمواصفات التقنية بصيغة نص حر (سواء بالعربية أو الإنجليزية)، ويقوم تلقائياً بـ:
1. **تحليل المواصفات وتصنيفها:** استخراج الكيانات (Entities)، الخصائص (Attributes)، والعلاقات (Relationships) واختيار نوع المخطط والمحرك الأنسب.
2. **توليد الكود البرمجي للمخطط:** دعم كامل لمحرك **Graphviz (DOT)** و **Mermaid.js**.
3. **التجميع والتصيير (Compilation):** تحويل الكود مباشرة إلى صور عالية الدقة (PNG / SVG).
4. **حلقة تصحيح ذاتية (Self-Correction Loop):** في حال وجود أي خطأ نحوي في الكود، يقوم الوكيل بالتقاط رسالة الخطأ من المترجم وإصلاح الكود تلقائياً وإعادة المحاولة حتى 3 مرات.
5. **واجهة محادثة تفاعلية (Web Chat UI):** واجهة ويب داكنة وأنيقة تتيح لك التحدث مع الوكيل مباشرة كأي Chatbot، ومشاهدة خطوات تفكيره ومخرجات التحليل والمخطط وزر تحميله بضغطة زر.

---

## 🚀 طريقة التشغيل السريعة / Quick Start

### الطريقة الأولى: تشغيل فوري بضغطة زر واحدة (موصى بها) ⚡

قم بفتح الطرفية (Terminal) وشغل السكربت الجاهز:

```bash
git clone https://github.com/Yahya-Studio/Specs-to-Diagrams-Autonomous-Agent.git
cd Specs-to-Diagrams-Autonomous-Agent
./start.sh
```
> **ملاحظة:** سيقوم السكربت تلقائياً بتفعيل البيئة الافتراضية، وتشغيل خادم الويب، وفتح المتصفح فوراً على الرابط: **`http://localhost:5000`**.

---

### الطريقة الثانية: التشغيل اليدوي لواجهة المحادثة 💬

```bash
# 1. الدخول لمجلد المشروع
cd Specs-to-Diagrams-Autonomous-Agent

# 2. تفعيل البيئة الافتراضية
source venv/bin/activate

# 3. تشغيل الخادم
python app.py
```

ثم افتح متصفحك وتوجه إلى:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 💻 التشغيل عبر سطر الأوامر / CLI Usage

إذا كنت تفضل استخدام الطرفية مباشرة بدون واجهة الويب:

### 1. إدخال نص مباشر:
```bash
source venv/bin/activate
python main.py --text "Users, Orders, and Products database schema with relations" --output my_diagram.png --verbose
```

### 2. إدخال نص من ملف:
```bash
python main.py --file specs.txt --output architecture.png
```

### خيارات الـ CLI المتاحة:
- `--text` أو `-t`: نص المتطلبات مباشرة.
- `--file` أو `-f`: مسار ملف نصي يحتوي على المواصفات.
- `--output` أو `-o`: مسار حفظ الصورة الناتجة (الافتراضي: `./output_diagram.png`).
- `--format`: صيغة الصورة (`png` أو `svg`).
- `--verbose` أو `-v`: طباعة تفاصيل كل خطوة والكود المولد في الطرفية.
- `--max-retries`: الحد الأقصى لمحاولات التصحيح الذاتي (الافتراضي: 3).

---

## 🧠 معمارية النظام / Architecture

يعتمد الوكيل على آلة حالات حتمية (Deterministic State Machine) باستخدام **LangGraph**:

```
           [مدخلات المستخدم / User Input]
                         │
                         ▼
        ┌─────────────────────────────────┐
        │     1. Classifier & Analyzer    │ ◄── تحليل النص وتحديد نوع المخطط والمحرك
        └─────────────────────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────┐
        │   2. Diagram Code Generator     │ ◄── توليد كود DOT أو Mermaid
        └─────────────────────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────┐
        │   3. Compiler Sandbox (Tool)    │ ◄── محاولة تجميع الكود لإنتاج الصورة
        └─────────────────────────────────┘
                         │
             ┌───────────┴───────────┐
             │                       │
      [نجاح / Success]        [فشل / Failure]
             │                       │
             ▼                       ▼
           (END)           [محاولات < 3 متبقية؟]
                                     │
                             ┌───────┴───────┐
                             │ نعم           │ لا
                             ▼               ▼
                   ┌──────────────────┐    ┌──────────────────┐
                   │  4. Debugger     │    │ Terminal Failure │
                   └──────────────────┘    └──────────────────┘
                             │                       │
                             └───► (إعادة التوليد)    ▼
                                                   (END)
```

---

## ⚙️ المتطلبات والتثبيت / Installation

إذا كنت تريد إعداد المشروع على جهاز جديد:

### 1. تثبيت أدوات الرسم في النظام:
```bash
# لأنظمة Arch Linux / Manjaro:
sudo pacman -S graphviz

# لأنظمة Ubuntu / Debian:
sudo apt-get install graphviz

# (اختياري) لدعم Mermaid CLI:
npm install -g @mermaid-js/mermaid-cli
```

### 2. إعداد بيئة بايثون وتثبيت المكتبات:
```bash
# إنشاء بيئة افتراضية وتفعيلها
python3 -m venv venv
source venv/bin/activate

# تثبيت متطلبات المشروع
pip install -r requirements.txt
```

### 3. إعداد مفتاح API الخاص بـ Gemini:
انسخ ملف النموذج `.env.example` إلى `.env` وضع فيه مفتاحك الخاص من [Google AI Studio](https://aistudio.google.com/):
```bash
cp .env.example .env
```
محتوى ملف `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

---

## 📁 هيكل المشروع / Project Structure

```
Specs-to-Diagrams-Autonomous-Agent/
├── start.sh              # سكربت تشغيل سريع بضغطة زر
├── app.py                # خادم Flask لواجهة المحادثة التفاعلية
├── main.py               # واجهة سطر الأوامر (CLI Entrypoint)
├── agent.py              # بناء وإدارة دورة العمل عبر LangGraph StateGraph
├── nodes.py              # عقد المعالجة الذكية وقوالب التوجيه (Prompts)
├── tools.py              # أدوات التجميع المستقلة (Graphviz & Mermaid Subprocesses)
├── schemas.py            # هياكل ونماذج البيانات (Pydantic & TypedDict)
├── templates/
│   └── index.html        # واجهة المحادثة العصرية (Chat UI)
├── outputs/              # مجلد حفظ المخططات المولدة تلقائياً
├── requirements.txt      # قائمة تبعيات ومكتبات بايثون
├── .env.example          # نموذج متغيرات البيئة
├── .gitignore            # حماية الأسرار وملفات البيئة
├── LICENSE               # رخصة MIT مفتوحة المصدر
└── README.md             # دليل الاستخدام والتوثيق
```

---

## 🌐 English Documentation

### Overview
**Specs-to-Diagrams Autonomous Agent** is an end-to-end Python system powered by **LangGraph** and **Google Gemini**. It converts unstructured technical requirements, system architectures, or relational database schemas into clean, compiled architectural diagrams with an autonomous self-correction loop.

### Supported Diagram Types
- **ERD (Entity-Relationship Diagrams):** Best for database tables, keys, and cardinalities (rendered with Graphviz).
- **System Architecture:** Components, microservices, and network flows (rendered with Graphviz).
- **Sequence Diagrams:** Interaction flows and API communications (rendered with Mermaid).
- **Flowcharts:** Process flows and decision logic (Graphviz or Mermaid).

### Running the Project
```bash
# Option A: One-click launcher (starts server & opens browser)
./start.sh

# Option B: Manual Web Chat UI
source venv/bin/activate
python app.py
# Access at: http://localhost:5000

# Option C: CLI Execution
python main.py --text "E-commerce database with Users, Orders and Items" --output erd.png
```

### Key Highlights
- **Self-Healing:** Automatically feeds compiler errors back to the Debugger node to patch syntax issues up to 3 retries.
- **Modern Chat Interface:** Real-time thinking steps, diagram lightbox preview, one-click PNG downloads, and source code viewer.
- **Dual Engine Support:** Graphviz DOT engine for crisp relational layouts and Mermaid.js for sequence flows.

---
**رخصة الاستخدام:** MIT License — متاح ومجاني للاستخدام والتطوير.

"""
nodes.py
========
LangGraph node functions and LLM prompt templates for each stage of the
Specs-to-Diagrams autonomous agent pipeline.

دوال عقد LangGraph وقوالب prompts للـ LLM لكل مرحلة من مراحل
خط أنابيب وكيل Specs-to-Diagrams المستقل.
"""

from __future__ import annotations

import json
import os
import re
import time
import textwrap
from pathlib import Path

# Load .env automatically (GOOGLE_API_KEY)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import AgentState, AnalysisResult, DiagramType, Engine
from tools import compile_diagram as _compile_diagram


# ---------------------------------------------------------------------------
# LLM initialisation / تهيئة نموذج اللغة
# ---------------------------------------------------------------------------

def _get_llm(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Return a configured Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",   # lightest model — most available capacity
        temperature=temperature,
        max_tokens=8192,
    )


def _llm_invoke_with_retry(llm, messages, max_attempts: int = 4, base_delay: float = 3.0):
    """Invoke the LLM with automatic exponential-backoff retry on 503 / overload errors.
    
    يستدعي النموذج مع إعادة محاولة تلقائية عند خطأ الحِمل الزائد (503).
    """
    for attempt in range(max_attempts):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            err_str = str(exc)
            is_overload = "503" in err_str or "UNAVAILABLE" in err_str or "overloaded" in err_str.lower()
            if is_overload and attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)   # 3s, 6s, 12s …
                print(f"  ⏳ Model overloaded (503). Retrying in {delay:.0f}s… (attempt {attempt+1}/{max_attempts})")
                time.sleep(delay)
                continue
            raise   # re-raise if not overload or exhausted


# ---------------------------------------------------------------------------
# Helper utilities / مساعدات
# ---------------------------------------------------------------------------

# Matches ```json ... ``` OR ``` ... ```
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.DOTALL)
_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\s*([\s\S]*?)\s*```", re.DOTALL)

# Also matches a bare { ... } JSON object if no fences are found
_BARE_JSON_RE  = re.compile(r"(\{[\s\S]*\})", re.DOTALL)


def _extract_json(text: str) -> str:
    """Robustly strip markdown fences and return a raw JSON string.
    
    Handles:
    - ```json ... ```
    - ``` ... ```
    - Plain JSON with no fences
    - JSON embedded in prose text
    """
    # Try fenced block first
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    # Try bare JSON object
    match = _BARE_JSON_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_code(text: str) -> str:
    """Strip markdown fences (```dot, ```mermaid, etc.) and return raw code."""
    match = _CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _log(step: str, message: str) -> None:
    """Print a formatted progress log line."""
    print(f"\n{'─'*60}")
    print(f"  🔷 [{step}] {message}")
    print(f"{'─'*60}")


def _get_text(response) -> str:
    """Extract plain text from a LangChain response regardless of content format.

    Newer Gemini models via langchain-google-genai return content as a list of
    dicts [{'type': 'text', 'text': '...', 'extras': {...}}] instead of a plain
    string. This helper handles both formats transparently.

    يستخرج النص العادي من استجابة LangChain بغض النظر عن صيغة المحتوى.
    """
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# PROMPTS / القوالب
# ---------------------------------------------------------------------------

ANALYZER_SYSTEM = textwrap.dedent("""
You are a software architect AI specialising in technical diagram design.

Your task is to analyse the user's technical specification text and return a
structured JSON object describing:
  1. The most appropriate diagram type.
  2. The best rendering engine for that diagram type.
  3. All structural entities (tables, services, components, actors…).
  4. All relationships and connections between them.
  5. A brief reasoning for your choices.

DIAGRAM TYPE RULES:
- ERD           → for database schemas, tables, foreign-key relationships.
- ARCHITECTURE  → for system components, microservices, cloud infrastructure.
- SEQUENCE      → for time-ordered message flows between actors/services.
- FLOWCHART     → for decision trees, process flows, algorithms.

ENGINE RULES:
- Use GRAPHVIZ for:  ERD (record shapes are ideal), ARCHITECTURE, FLOWCHART.
- Use MERMAID   for:  SEQUENCE (sequenceDiagram is cleaner), simple FLOWCHART.

RESPOND WITH ONLY VALID JSON — no markdown fences, no explanation outside JSON.

JSON schema to follow exactly:
{
  "diagram_type": "ERD | ARCHITECTURE | SEQUENCE | FLOWCHART",
  "engine": "GRAPHVIZ | MERMAID",
  "title": "<short descriptive title>",
  "reasoning": "<one-sentence explanation>",
  "entities": [
    {
      "name": "<EntityName>",
      "attributes": ["<attr1>", "<attr2>"],
      "description": "<optional short description>"
    }
  ],
  "relationships": [
    {
      "from_entity": "<Source>",
      "to_entity": "<Target>",
      "label": "<label or cardinality>",
      "bidirectional": false
    }
  ]
}
""").strip()


GENERATOR_SYSTEM_GRAPHVIZ = textwrap.dedent("""
You are an expert Graphviz DOT code generator.

Your task: generate syntactically correct, executable Graphviz DOT code
based on the structured JSON specification you receive.

STRICT RULES — follow every rule without exception:
1.  Output ONLY the raw DOT source code. No markdown fences, no explanations,
    no comments outside the DOT code block.
2.  For ERDs: use `record` or `plaintext` shapes with HTML-like labels.
    Use a `<TABLE>` HTML label for each entity to render attribute rows.
    Example entity node:
        Users [shape=none, margin=0, label=<
            <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">
            <TR><TD BGCOLOR="#4A90D9" ALIGN="CENTER"><B><FONT COLOR="white">Users</FONT></B></TD></TR>
            <TR><TD ALIGN="LEFT">id (PK)</TD></TR>
            <TR><TD ALIGN="LEFT">name</TD></TR>
            </TABLE>>];
3.  Always quote node names containing spaces, hyphens, or special characters
    using double quotes: "My Node".
4.  Escape literal double quotes inside labels with \\".
5.  For ARCHITECTURE diagrams: use `digraph` with `rankdir=LR`, cluster
    subgraphs for grouping services.
6.  For FLOWCHART diagrams: use diamond shapes for decisions, box for process
    steps, use `rankdir=TB`.
7.  Always include: `graph [fontname="Helvetica", bgcolor="white"];`
    and `node [fontname="Helvetica"];`
8.  Use descriptive edge labels: `-> [label="1:N"]`.
9.  Ensure the code can be compiled with: `dot -Tpng input.dot -o output.png`

The response must be ONLY the DOT code starting with `digraph` or `graph`.
""").strip()


GENERATOR_SYSTEM_MERMAID = textwrap.dedent("""
You are an expert Mermaid.js diagram code generator.

Your task: generate syntactically correct, executable Mermaid source code
based on the structured JSON specification you receive.

STRICT RULES — follow every rule without exception:
1.  Output ONLY the raw Mermaid source code. No markdown fences, no
    explanations, no extra text.
2.  Use the correct diagram header:
    - ERD       → `erDiagram`
    - Sequence  → `sequenceDiagram`
    - Flowchart → `flowchart TD`
    - Architecture/Class → `classDiagram`
3.  For erDiagram: follow strict Mermaid ERD syntax:
      ENTITY_NAME {
          type attribute_name PK
          type attribute_name FK
      }
      ENTITY ||--o{ OTHER_ENTITY : "label"
4.  For sequenceDiagram: use `participant`, `->>`  for sync messages,
    `-->>` for responses.
5.  For flowchart: use `[Process]`, `{Decision}`, `((Circle))` shapes.
    Quote labels containing special characters.
6.  Entity/node names must NOT contain spaces or special characters.
    Replace spaces with underscores: `Order_Items` not `Order Items`.
7.  Relationships must use valid Mermaid cardinality symbols:
    `||--||`, `||--o{`, `}o--o{`, etc.
8.  Ensure the code can be compiled with: `mmdc -i input.mmd -o output.png`

The response must be ONLY the Mermaid code starting with the diagram keyword.
""").strip()


DEBUGGER_SYSTEM = textwrap.dedent("""
You are an expert diagram code debugger and fixer.

You will receive:
  1. A broken diagram source code (DOT or Mermaid).
  2. The exact compiler error message (stderr output).
  3. The diagram type and engine in use.

Your task: carefully analyse the error, identify the exact cause, and output
a CORRECTED version of the diagram source code.

STRICT RULES:
1.  Output ONLY the corrected raw code — no markdown fences, no explanations.
2.  Fix ALL syntax errors reported in the compiler output.
3.  Common Graphviz fixes:
    - Unquoted special characters: add double quotes around node IDs.
    - Invalid HTML labels: fix unclosed tags, invalid nesting.
    - Missing semicolons after statements.
    - Wrong shape names: use 'record', 'box', 'diamond', 'ellipse', 'none'.
4.  Common Mermaid fixes:
    - Spaces in entity names → replace with underscores.
    - Wrong cardinality symbols → use `||--o{`, `}|--|{` etc.
    - Missing `erDiagram` / `sequenceDiagram` header.
    - Quoted strings in wrong places → remove unnecessary quotes.
5.  Preserve the diagram's full logical content — do not remove entities or
    relationships to make it compile; fix the syntax instead.
6.  If the error is ambiguous, apply all likely fixes simultaneously.
""").strip()


# ---------------------------------------------------------------------------
# NODE 1 — Analyze Specs / تحليل المتطلبات
# ---------------------------------------------------------------------------

def analyze_specs(state: AgentState) -> AgentState:
    """Classify the input text and extract structured entities and relationships.
    
    يصنّف النص المدخَل ويستخرج الكيانات والعلاقات المنظَّمة.
    """
    _log("ANALYZER", "Classifying specification and extracting entities…")

    llm = _get_llm(temperature=0.0)
    input_text: str = state["input_text"]

    messages = [
        SystemMessage(content=ANALYZER_SYSTEM),
        HumanMessage(content=(
            f"Analyse the following technical specification and return the "
            f"structured JSON:\n\n{input_text}"
        )),
    ]

    response = _llm_invoke_with_retry(llm, messages)
    raw_json = _extract_json(_get_text(response))

    try:
        data = json.loads(raw_json)
        analysis = AnalysisResult(**data)
    except (json.JSONDecodeError, ValueError) as exc:
        # The model occasionally wraps output in extra text — try to extract JSON more aggressively
        print(f"  ⚠️  JSON parse note: {exc}. Trying aggressive extraction…")
        # Find the first '{' and last '}' in the raw response
        raw_full = _get_text(response)
        start = raw_full.find("{")
        end   = raw_full.rfind("}") + 1
        if start != -1 and end > start:
            candidate = raw_full[start:end]
            try:
                data = json.loads(candidate)
                analysis = AnalysisResult(**data)
            except Exception:
                raise exc   # give up and raise original
        else:
            raise exc

    print(f"  ✅ Diagram type : {analysis.diagram_type.value}")
    print(f"  ✅ Engine        : {analysis.engine.value}")
    print(f"  ✅ Entities found: {[e.name for e in analysis.entities]}")
    print(f"  ✅ Relationships : {len(analysis.relationships)}")
    print(f"  💡 Reasoning     : {analysis.reasoning}")

    return {
        **state,
        "analysis": analysis,
        "diagram_type": analysis.diagram_type,
        "engine": analysis.engine,
        "attempt": 0,
        "errors": [],
        "success": False,
    }


# ---------------------------------------------------------------------------
# NODE 2 — Generate Code / توليد الكود
# ---------------------------------------------------------------------------

def generate_code(state: AgentState) -> AgentState:
    """Generate diagram source code from the structured analysis.
    
    يولِّد كود المخطط المصدري من التحليل المنظَّم.
    """
    attempt: int = state.get("attempt", 0)
    _log("GENERATOR", f"Generating diagram code (attempt {attempt + 1})…")

    llm = _get_llm(temperature=0.15)
    analysis: AnalysisResult = state["analysis"]
    engine: Engine = state["engine"]

    # Select the appropriate system prompt
    if engine == Engine.GRAPHVIZ:
        system_prompt = GENERATOR_SYSTEM_GRAPHVIZ
    else:
        system_prompt = GENERATOR_SYSTEM_MERMAID

    # Serialise analysis to JSON for the prompt
    analysis_json = analysis.model_dump_json(indent=2)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Generate the diagram code for this specification:\n\n"
            f"```json\n{analysis_json}\n```"
        )),
    ]

    response = _llm_invoke_with_retry(llm, messages)
    raw_code = _extract_code(_get_text(response))

    print(f"  📝 Generated {len(raw_code)} characters of {engine.value} code.")

    return {
        **state,
        "current_code": raw_code,
    }


# ---------------------------------------------------------------------------
# NODE 3 — Compile Diagram / تجميع المخطط
# ---------------------------------------------------------------------------

def compile_diagram_node(state: AgentState, output_path: str) -> AgentState:
    """Attempt to compile the current diagram code into an image.
    
    يحاول تجميع كود المخطط الحالي إلى صورة.
    """
    engine: Engine = state["engine"]
    code: str = state["current_code"]
    attempt: int = state.get("attempt", 0)

    _log("COMPILER", f"Compiling with {engine.value} → {output_path}  (attempt {attempt + 1})…")

    success, message = _compile_diagram(engine.value, code, output_path)

    if success:
        print(f"  ✅ Compilation succeeded! Image saved to: {message}")
        return {
            **state,
            "success": True,
            "output_path": message,
            "final_code": code,
        }
    else:
        print(f"  ❌ Compilation failed:\n{message[:500]}{'…' if len(message) > 500 else ''}")
        errors: list[str] = list(state.get("errors", []))
        errors.append(message)
        return {
            **state,
            "success": False,
            "errors": errors,
            "attempt": attempt + 1,
        }


# ---------------------------------------------------------------------------
# NODE 4 — Debug Code / تصحيح الكود
# ---------------------------------------------------------------------------

def debug_code(state: AgentState) -> AgentState:
    """Ingest the compiler error and broken code; emit a corrected version.
    
    يستوعب خطأ المُجمِّع والكود المعطوب؛ يُصدر إصدارًا مُصحَّحًا.
    """
    attempt: int = state.get("attempt", 0)
    _log("DEBUGGER", f"Attempting self-correction (retry {attempt})…")

    llm = _get_llm(temperature=0.05)
    engine: Engine = state["engine"]
    broken_code: str = state["current_code"]
    errors: list[str] = state.get("errors", [])
    last_error: str = errors[-1] if errors else "Unknown compilation error."
    analysis: AnalysisResult = state["analysis"]

    messages = [
        SystemMessage(content=DEBUGGER_SYSTEM),
        HumanMessage(content=(
            f"Engine: {engine.value}\n"
            f"Diagram type: {analysis.diagram_type.value}\n\n"
            f"=== COMPILER ERROR ===\n{last_error}\n\n"
            f"=== BROKEN CODE ===\n{broken_code}\n\n"
            f"Output the corrected {engine.value} code ONLY."
        )),
    ]

    response = _llm_invoke_with_retry(llm, messages)
    corrected_code = _extract_code(_get_text(response))

    print(f"  🔧 Debugger produced {len(corrected_code)} characters of corrected code.")

    return {
        **state,
        "current_code": corrected_code,
    }


# ---------------------------------------------------------------------------
# NODE 5 — Terminal Failure / فشل نهائي
# ---------------------------------------------------------------------------

def terminal_failure(state: AgentState) -> AgentState:
    """Handle the case where all retries are exhausted.
    
    يتعامل مع الحالة التي تُستنفَد فيها كل المحاولات.
    """
    _log("TERMINAL", "❌ All retry attempts exhausted. Agent failed to compile the diagram.")
    errors: list[str] = state.get("errors", [])
    print(f"\n  📋 Error history ({len(errors)} attempt(s)):")
    for i, err in enumerate(errors, 1):
        print(f"\n  — Attempt {i}:\n{textwrap.indent(err[:300], '    ')}…")

    return {
        **state,
        "success": False,
        "output_path": None,
    }

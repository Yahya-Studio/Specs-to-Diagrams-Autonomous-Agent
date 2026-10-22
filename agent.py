"""
agent.py
========
LangGraph StateGraph construction for the Specs-to-Diagrams autonomous agent.
Implements the deterministic state machine with a self-correction feedback loop.

بناء LangGraph StateGraph لوكيل Specs-to-Diagrams المستقل.
يُنفِّذ آلة الحالات الحتمية مع حلقة تغذية راجعة للتصحيح الذاتي.
"""

from __future__ import annotations

from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from schemas import AgentState
from nodes import (
    analyze_specs,
    compile_diagram_node,
    debug_code,
    generate_code,
    terminal_failure,
)


# ---------------------------------------------------------------------------
# Maximum retry attempts / الحد الأقصى لمحاولات إعادة المحاولة
# ---------------------------------------------------------------------------

MAX_RETRIES: int = 3


# ---------------------------------------------------------------------------
# Conditional routing / التوجيه الشرطي
# ---------------------------------------------------------------------------

def route_after_compile(
    state: AgentState,
) -> Literal["__end__", "debug_code", "terminal_failure"]:
    """Decide the next node after a compilation attempt.
    
    يقرر العقدة التالية بعد محاولة التجميع.

    Returns:
        '__end__'         — compilation succeeded.
        'debug_code'      — compilation failed but retries remain.
        'terminal_failure'— all retries exhausted.
    """
    if state.get("success"):
        return "__end__"

    attempt: int = state.get("attempt", 0)
    if attempt < MAX_RETRIES:
        return "debug_code"

    return "terminal_failure"


# ---------------------------------------------------------------------------
# Graph builder / بناة الرسم البياني
# ---------------------------------------------------------------------------

def build_agent(output_path: str = "./output_diagram.png") -> StateGraph:
    """Construct and compile the LangGraph StateGraph.
    
    يُنشئ ويُجمِّع LangGraph StateGraph.

    The graph follows this flow:
    
        START
          │
          ▼
      analyze_specs
          │
          ▼
      generate_code ◄────────────────┐
          │                          │
          ▼                          │
      compile_diagram                │
          │                          │
          ├── success ──► END        │
          │                          │
          ├── failure + retries ──► debug_code
          │                          │
          └── failure + no retries ──► terminal_failure ──► END

    Args:
        output_path: Destination path for the compiled image file.

    Returns:
        A compiled LangGraph runnable.
    """
    # Bind the output path into the compile node so the graph API stays clean
    compile_node = partial(compile_diagram_node, output_path=output_path)

    # ── Build graph ─────────────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("analyze_specs", analyze_specs)
    graph.add_node("generate_code", generate_code)
    graph.add_node("compile_diagram", compile_node)
    graph.add_node("debug_code", debug_code)
    graph.add_node("terminal_failure", terminal_failure)

    # Set entry point
    graph.set_entry_point("analyze_specs")

    # Fixed edges
    graph.add_edge("analyze_specs", "generate_code")
    graph.add_edge("generate_code", "compile_diagram")
    graph.add_edge("debug_code", "generate_code")   # After debugging, re-generate
    graph.add_edge("terminal_failure", END)

    # Conditional edge after compilation
    graph.add_conditional_edges(
        "compile_diagram",
        route_after_compile,
        {
            "__end__": END,
            "debug_code": "debug_code",
            "terminal_failure": "terminal_failure",
        },
    )

    return graph.compile()


# ---------------------------------------------------------------------------
# Public run function / دالة التشغيل العامة
# ---------------------------------------------------------------------------

def run_agent(
    input_text: str,
    output_path: str = "./output_diagram.png",
) -> AgentState:
    """Run the full Specs-to-Diagrams agent on the given input text.
    
    يُشغِّل وكيل Specs-to-Diagrams الكامل على النص المُدخَل.

    Args:
        input_text:  Free-form technical specification text.
        output_path: Path where the output image will be saved.

    Returns:
        The final AgentState after the graph has completed execution.
    """
    agent = build_agent(output_path=output_path)

    initial_state: AgentState = {
        "input_text": input_text,
        "analysis": None,
        "current_code": None,
        "diagram_type": None,
        "engine": None,
        "attempt": 0,
        "errors": [],
        "output_path": None,
        "success": False,
        "final_code": None,
    }

    final_state = agent.invoke(initial_state)
    return final_state

"""
schemas.py
==========
Data models and state definitions for the Specs-to-Diagrams Agent.
نماذج البيانات وتعريفات الحالة لوكيل Specs-to-Diagrams.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from typing_extensions import TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations / التعدادات
# ---------------------------------------------------------------------------

class DiagramType(str, Enum):
    """Type of diagram to generate / نوع المخطط المراد توليده."""

    ERD = "ERD"                          # Entity-Relationship Diagram
    ARCHITECTURE = "ARCHITECTURE"        # System / Component Architecture
    SEQUENCE = "SEQUENCE"                # Sequence / Interaction Diagram
    FLOWCHART = "FLOWCHART"              # Process Flowchart


class Engine(str, Enum):
    """Rendering engine to use / محرك الرسم المستخدم."""

    GRAPHVIZ = "GRAPHVIZ"   # Generates .dot files → compiled with `dot`
    MERMAID = "MERMAID"     # Generates .mmd files → compiled with `mmdc`


# ---------------------------------------------------------------------------
# Analysis Result / نتيجة التحليل
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    """A structural entity extracted from the specification text.
    
    كيان هيكلي مستخرج من نص المتطلبات.
    """

    name: str = Field(description="Entity / table / service name")
    attributes: list[str] = Field(
        default_factory=list,
        description="List of attributes, columns, or properties",
    )
    description: Optional[str] = Field(
        default=None,
        description="Short description of the entity",
    )


class Relationship(BaseModel):
    """A directed relationship between two entities.
    
    علاقة موجَّهة بين كيانَين.
    """

    from_entity: str = Field(description="Source entity name")
    to_entity: str = Field(description="Target entity name")
    label: str = Field(description="Relationship label / cardinality (e.g., 'has many', '1:N')")
    bidirectional: bool = Field(
        default=False,
        description="Whether the relationship is bidirectional",
    )


class AnalysisResult(BaseModel):
    """Structured output from the Classifier & Analyzer node.
    
    الخرج المنظَّم من عقدة التصنيف والتحليل.
    """

    diagram_type: DiagramType = Field(
        description="Best-fit diagram type for the given specification"
    )
    engine: Engine = Field(
        description="Best-fit rendering engine"
    )
    entities: list[Entity] = Field(
        default_factory=list,
        description="Structural entities / tables / services extracted from the text",
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Connections and relationships between entities",
    )
    reasoning: str = Field(
        description="Brief explanation of why this diagram type and engine were chosen",
    )
    title: str = Field(
        default="Generated Diagram",
        description="Suggested title for the diagram",
    )


# ---------------------------------------------------------------------------
# LangGraph Agent State / حالة وكيل LangGraph
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """The shared state object that flows through all LangGraph nodes.
    
    كائن الحالة المشتركة الذي يتدفق عبر جميع عقد LangGraph.
    """

    # Input / المدخل
    input_text: str
    """The raw specification text provided by the user."""

    # Analysis / التحليل
    analysis: Optional[AnalysisResult]
    """Structured analysis output from the analyzer node."""

    # Code generation / توليد الكود
    current_code: Optional[str]
    """Most recently generated diagram source code (DOT or MMD)."""

    diagram_type: Optional[DiagramType]
    """Diagram type decided during analysis."""

    engine: Optional[Engine]
    """Rendering engine decided during analysis."""

    # Execution state / حالة التنفيذ
    attempt: int
    """Current retry attempt count (starts at 0)."""

    errors: list[str]
    """Accumulated error messages from failed compilation attempts."""

    # Output / المخرجات
    output_path: Optional[str]
    """Absolute path to the successfully compiled image file."""

    success: bool
    """True if compilation succeeded, False otherwise."""

    final_code: Optional[str]
    """The final diagram source code that produced the successful image."""

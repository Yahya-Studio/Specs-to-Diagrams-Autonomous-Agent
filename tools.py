"""
tools.py
========
Safe subprocess wrappers for compiling diagram source code into images.
أغلفة subprocess آمنة لتجميع كود المخطط المصدري إلى صور.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Availability checks / فحص التوفر
# ---------------------------------------------------------------------------

def _check_tool(name: str, install_hint: str) -> str:
    """Raise a clear RuntimeError if a CLI tool is not found on PATH.
    
    يرفع RuntimeError واضحًا إذا لم يُوجد أداة CLI في PATH.
    """
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(
            f"\n❌ Required tool '{name}' not found on PATH.\n"
            f"📦 Install it with:\n    {install_hint}\n"
            f"Then make sure it is accessible from your terminal."
        )
    return path


# ---------------------------------------------------------------------------
# Graphviz compiler / مُجمِّع Graphviz
# ---------------------------------------------------------------------------

def compile_graphviz(
    dot_code: str,
    output_path: str,
    output_format: str = "png",
) -> tuple[bool, str]:
    """Compile a Graphviz DOT source string into an image file.

    يُجمِّع سلسلة كود Graphviz DOT إلى ملف صورة.

    Args:
        dot_code:      Raw DOT language source code.
        output_path:   Absolute or relative destination path for the output image.
        output_format: Output format — 'png' or 'svg' (default: 'png').

    Returns:
        A tuple ``(success: bool, message: str)``.
        On success: ``(True, resolved_output_path)``
        On failure: ``(False, detailed_error_message)``
    """
    try:
        _check_tool(
            "dot",
            "Linux/macOS: sudo apt-get install graphviz  OR  brew install graphviz\n"
            "    Windows: https://graphviz.org/download/",
        )
    except RuntimeError as exc:
        return False, str(exc)

    output_path = str(Path(output_path).resolve())

    # Write source to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".dot",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(dot_code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["dot", f"-T{output_format}", tmp_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and Path(output_path).exists():
            return True, output_path

        # Build a rich error message
        error_parts = [
            f"Graphviz compilation failed (exit code {result.returncode}).",
        ]
        if result.stderr.strip():
            error_parts.append(f"STDERR:\n{result.stderr.strip()}")
        if result.stdout.strip():
            error_parts.append(f"STDOUT:\n{result.stdout.strip()}")
        error_parts.append(f"\nBroken DOT source:\n{dot_code}")

        return False, "\n".join(error_parts)

    except subprocess.TimeoutExpired:
        return False, "Graphviz compilation timed out after 60 seconds."
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error during Graphviz compilation: {exc}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Mermaid compiler / مُجمِّع Mermaid
# ---------------------------------------------------------------------------

def compile_mermaid(
    mermaid_code: str,
    output_path: str,
    output_format: str = "png",
) -> tuple[bool, str]:
    """Compile a Mermaid source string into an image file via the mmdc CLI.

    يُجمِّع كود Mermaid إلى ملف صورة عبر أداة mmdc.

    Args:
        mermaid_code:  Raw Mermaid diagram source code.
        output_path:   Absolute or relative destination path for the output image.
        output_format: Output format — 'png' or 'svg' (default: 'png').

    Returns:
        A tuple ``(success: bool, message: str)``.
        On success: ``(True, resolved_output_path)``
        On failure: ``(False, detailed_error_message)``
    """
    try:
        _check_tool(
            "mmdc",
            "npm install -g @mermaid-js/mermaid-cli\n"
            "    (Requires Node.js ≥ 18. After install, run: mmdc --version)",
        )
    except RuntimeError as exc:
        return False, str(exc)

    output_path = str(Path(output_path).resolve())

    # Write source to a temporary .mmd file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(mermaid_code)
        tmp_path = tmp.name

    try:
        cmd = [
            "mmdc",
            "--input", tmp_path,
            "--output", output_path,
            "--outputFormat", output_format,
            "--quiet",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # mmdc can be slow on first run (Puppeteer startup)
        )

        if result.returncode == 0 and Path(output_path).exists():
            return True, output_path

        # Build a rich error message
        error_parts = [
            f"Mermaid compilation failed (exit code {result.returncode}).",
        ]
        if result.stderr.strip():
            error_parts.append(f"STDERR:\n{result.stderr.strip()}")
        if result.stdout.strip():
            error_parts.append(f"STDOUT:\n{result.stdout.strip()}")
        error_parts.append(f"\nBroken Mermaid source:\n{mermaid_code}")

        return False, "\n".join(error_parts)

    except subprocess.TimeoutExpired:
        return False, (
            "Mermaid compilation timed out after 120 seconds.\n"
            "This may happen on the first run while Puppeteer downloads Chromium.\n"
            "Try running 'mmdc --version' manually to trigger the download."
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error during Mermaid compilation: {exc}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Unified dispatcher / موزِّع موحَّد
# ---------------------------------------------------------------------------

def compile_diagram(
    engine: str,
    source_code: str,
    output_path: str,
    output_format: str = "png",
) -> tuple[bool, str]:
    """Route compilation to the correct backend based on the engine name.

    يُوجِّه التجميع إلى الواجهة الخلفية الصحيحة بناءً على اسم المحرك.

    Args:
        engine:        'GRAPHVIZ' or 'MERMAID' (case-insensitive).
        source_code:   Raw diagram source code.
        output_path:   Destination path for the compiled image.
        output_format: 'png' or 'svg'.

    Returns:
        ``(True, output_path)`` on success or ``(False, error_message)`` on failure.
    """
    engine_upper = engine.upper()

    if engine_upper == "GRAPHVIZ":
        return compile_graphviz(source_code, output_path, output_format)
    elif engine_upper == "MERMAID":
        return compile_mermaid(source_code, output_path, output_format)
    else:
        return False, f"Unknown engine '{engine}'. Supported: GRAPHVIZ, MERMAID."

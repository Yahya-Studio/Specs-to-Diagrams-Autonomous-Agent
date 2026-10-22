"""
main.py
=======
CLI entrypoint for the Specs-to-Diagrams Autonomous Agent.
Supports text input directly via --text or from a file via --file.

نقطة دخول CLI لوكيل Specs-to-Diagrams المستقل.
يدعم إدخال النص مباشرةً عبر --text أو من ملف عبر --file.

Usage / الاستخدام:
    python main.py --text "Your specification here" --output my_diagram.png
    python main.py --file specs.txt --output my_diagram.png --verbose

Sample e-commerce run / تشغيل نموذجي لـ e-commerce:
    python main.py \\
        --text "E-commerce system: Users table (id, name, email, created_at). \\
                Orders table (id, user_id, total, status, created_at). \\
                OrderItems table (id, order_id, product_id, quantity, price). \\
                Payments table (id, order_id, amount, method, status). \\
                Users place many Orders. Orders contain many OrderItems. \\
                Each Order has one Payment." \\
        --output ecommerce_erd.png
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import time
from pathlib import Path

# Load .env file automatically — must happen before any API key check
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# ---------------------------------------------------------------------------
# ANSI colour helpers / مساعدات الألوان
# ---------------------------------------------------------------------------

def _c(code: str, text: str) -> str:
    """Wrap text in an ANSI colour code if stdout is a terminal."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(t: str) -> str:  return _c("32", t)
def _red(t: str) -> str:    return _c("31", t)
def _cyan(t: str) -> str:   return _c("36", t)
def _yellow(t: str) -> str: return _c("33", t)
def _bold(t: str) -> str:   return _c("1", t)


# ---------------------------------------------------------------------------
# Banner / شعار
# ---------------------------------------------------------------------------

BANNER = r"""
 ____                           _          ____  _                                    
/ ___| _ __   ___  ___  ___    | |_ ___   |  _ \(_) __ _  __ _ _ __ __ _ _ __ ___  
\___ \| '_ \ / _ \/ __|/ __|   | __/ _ \  | | | | |/ _` |/ _` | '__/ _` | '_ ` _ \ 
 ___) | |_) |  __/ (__  \__ \  | || (_) | | |_| | | (_| | (_| | | | (_| | | | | | |
|____/| .__/ \___|\___|_|___/   \__\___/  |____/|_|\__,_|\__, |_|  \__,_|_| |_| |_|
      |_|                                                 |___/                       
          🤖  Specs-to-Diagrams Autonomous Agent  |  Powered by Gemini + LangGraph
"""


# ---------------------------------------------------------------------------
# Argument parser / مُحلِّل الوسيطات
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specs-to-diagrams",
        description=textwrap.dedent("""
            🤖 Specs-to-Diagrams Autonomous Agent
            Converts free-form technical text into compiled architectural diagrams.
            Supports ERD, Architecture, Sequence, and Flowchart diagram types.
            Rendering engines: Graphviz (dot) and Mermaid (mmdc).
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              # Direct text input
              python main.py --text "Users, Orders, Products tables with relationships"

              # From a specification file
              python main.py --file my_specs.txt --output diagram.png

              # E-commerce ERD with verbose logging
              python main.py --file ecommerce.txt --output erd.png --verbose
        """),
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text", "-t",
        type=str,
        metavar="TEXT",
        help="Specification text provided directly as a string argument.",
    )
    input_group.add_argument(
        "--file", "-f",
        type=str,
        metavar="FILE",
        help="Path to a plain-text file containing the specification.",
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./output_diagram.png",
        metavar="PATH",
        help="Destination path for the output image file (default: ./output_diagram.png).",
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["png", "svg"],
        default="png",
        help="Output image format (default: png). Note: passed to the output filename.",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose debug information including generated code.",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        metavar="N",
        help="Maximum number of self-correction retry attempts (default: 3).",
    )

    return parser


# ---------------------------------------------------------------------------
# Validation helpers / مساعدات التحقق
# ---------------------------------------------------------------------------

def _validate_api_key() -> None:
    """Ensure GOOGLE_API_KEY is set in the environment."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print(_red("\n❌ GOOGLE_API_KEY environment variable is not set."))
        print(_yellow(
            "\nSet it with:\n"
            "  export GOOGLE_API_KEY='your-api-key-here'   # Linux/macOS\n"
            "  set GOOGLE_API_KEY=your-api-key-here         # Windows CMD\n"
            "\nGet your API key from: https://aistudio.google.com/app/apikey\n"
        ))
        sys.exit(1)


def _resolve_output_path(output_arg: str, fmt: str) -> str:
    """Resolve and validate the output file path."""
    path = Path(output_arg)

    # If user passed a path without extension, append format
    if not path.suffix:
        path = path.with_suffix(f".{fmt}")

    # If extension doesn't match requested format, warn but keep the user's choice
    if path.suffix.lstrip(".").lower() != fmt and fmt != "png":
        print(_yellow(f"⚠️  Output extension '{path.suffix}' differs from --format '{fmt}'."))

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    return str(path.resolve())


def _read_input_text(args: argparse.Namespace) -> str:
    """Read specification text from --text or --file."""
    if args.text:
        return args.text.strip()

    file_path = Path(args.file)
    if not file_path.exists():
        print(_red(f"\n❌ Specification file not found: {file_path}"))
        sys.exit(1)
    if not file_path.is_file():
        print(_red(f"\n❌ Path is not a file: {file_path}"))
        sys.exit(1)

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        print(_red(f"\n❌ Specification file is empty: {file_path}"))
        sys.exit(1)

    print(_cyan(f"📄 Loaded specification from: {file_path}"))
    return text


# ---------------------------------------------------------------------------
# Results printer / طابع النتائج
# ---------------------------------------------------------------------------

def _print_results(final_state: dict, verbose: bool, elapsed: float) -> None:
    """Print a summary of the agent's execution results."""
    print(f"\n{'═'*60}")
    print(_bold("  📊 AGENT EXECUTION SUMMARY / ملخص تنفيذ الوكيل"))
    print(f"{'═'*60}\n")

    success: bool = final_state.get("success", False)
    attempt: int = final_state.get("attempt", 0)
    errors: list = final_state.get("errors", [])

    analysis = final_state.get("analysis")
    if analysis:
        print(f"  🔍 Diagram type  : {_cyan(analysis.diagram_type.value)}")
        print(f"  ⚙️  Engine        : {_cyan(analysis.engine.value)}")
        print(f"  📌 Title         : {analysis.title}")
        print(f"  🏗️  Entities      : {len(analysis.entities)}")
        print(f"  🔗 Relationships : {len(analysis.relationships)}")

    print(f"  🔄 Attempts      : {attempt}")
    print(f"  ⏱️  Time elapsed  : {elapsed:.2f}s")

    if success:
        output_path = final_state.get("output_path", "")
        print(f"\n  {_green('✅ SUCCESS!')} Diagram compiled successfully.")
        print(f"  📁 Output image  : {_green(output_path)}")

        if verbose:
            final_code = final_state.get("final_code", "")
            print(f"\n  📝 Final source code ({len(final_code)} chars):")
            print("  " + "─"*56)
            for line in final_code.splitlines():
                print(f"    {line}")
            print("  " + "─"*56)
    else:
        print(f"\n  {_red('❌ FAILED.')} The agent could not compile the diagram.")
        print(f"  Total errors recorded: {len(errors)}")

        if verbose and errors:
            print(f"\n  Last error:")
            last_err = errors[-1] if errors else ""
            for line in last_err[:800].splitlines():
                print(f"    {_red(line)}")

        print(_yellow(
            "\n  💡 Tips:\n"
            "     1. Ensure Graphviz is installed: sudo apt-get install graphviz\n"
            "     2. Ensure Mermaid CLI is installed: npm install -g @mermaid-js/mermaid-cli\n"
            "     3. Try simplifying the specification text.\n"
            "     4. Use --verbose for detailed error output.\n"
        ))

    print(f"\n{'═'*60}\n")


# ---------------------------------------------------------------------------
# Main entrypoint / نقطة الدخول الرئيسية
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Print banner
    print(_cyan(BANNER))

    # Validate prerequisites
    _validate_api_key()

    # Read input
    input_text = _read_input_text(args)
    output_path = _resolve_output_path(args.output, args.format)

    print(_bold(f"\n📋 Specification preview ({min(len(input_text), 200)} chars):"))
    print(f"   {input_text[:200]}{'…' if len(input_text) > 200 else ''}")
    print(f"\n🎯 Output destination: {_cyan(output_path)}")
    print(f"🔁 Max retries: {args.max_retries}\n")

    # Patch MAX_RETRIES if user specified a custom value
    import agent as agent_module
    agent_module.MAX_RETRIES = args.max_retries

    # Run the agent
    from agent import run_agent

    start_time = time.time()
    try:
        final_state = run_agent(
            input_text=input_text,
            output_path=output_path,
        )
    except KeyboardInterrupt:
        print(_yellow("\n\n⚠️  Interrupted by user."))
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        print(_red(f"\n❌ Unexpected error: {exc}"))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - start_time
    _print_results(final_state, verbose=args.verbose, elapsed=elapsed)

    sys.exit(0 if final_state.get("success") else 1)


if __name__ == "__main__":
    main()

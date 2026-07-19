import sys
import copy
import resource
import signal
from typing import List, Dict, Any

EXECUTION_TIMEOUT_SECONDS = 10
MAX_STEPS = 500         # Stop recording after this many steps to prevent giant outputs
IGNORED_VARS = {"__builtins__", "__doc__", "__name__", "__package__", "__loader__", "__spec__"}


class ExecutionTimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise ExecutionTimeoutError("Code execution exceeded time limit")


def _is_serializable(value) -> bool:
    """Check if a value can be safely JSON-serialized for the frontend."""
    try:
        import json
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def _safe_copy(value) -> Any:
    """Deep copy a value if possible; otherwise convert to a string representation."""
    try:
        return copy.deepcopy(value)
    except Exception:
        return repr(value)


def trace_code(code: str) -> List[Dict[str, Any]]:
    """
    Execute code under a tracing hook and return a list of step dicts.

    Each step dict contains:
      - line (int): the line number about to be executed
      - variables (dict): snapshot of all local variables at this point
      - event (str): 'line', 'call', or 'return'
      - output (str): any print() output from this step
    """
    steps: List[Dict[str, Any]] = []
    captured_output = []
    local_vars: Dict[str, Any] = {}

    # Determine up front (via AST, before any execution) whether this code
    # defines any functions at all. This must be known BEFORE tracing
    # starts, not inferred dynamically during the trace: the module frame
    # emits 'line' events for statements like `result = two_sum(...)` at
    # the point the call is *about* to happen, while `two_sum` already
    # exists as a module-level local — before any function frame has been
    # entered. A dynamic "have we seen a function frame yet" flag would
    # still be False at that moment, letting that event slip through with
    # the function object itself sitting in its variable snapshot.
    try:
        import ast
        has_function_defs = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(ast.parse(code))
        )
    except SyntaxError:
        # If the code doesn't even parse, let exec() raise and report the
        # syntax error below as before; tracing behavior here doesn't matter.
        has_function_defs = False

    def tracer(frame, event, arg):
        if len(steps) >= MAX_STEPS:
            return None

        if event not in ("line", "return"):
            return tracer

        # Only trace the top-level executed code, not library internals
        if frame.f_code.co_filename != "<string>":
            return tracer

        # Skip the module-level frame entirely whenever the submitted code
        # defines at least one function — the module frame's f_locals are
        # top-level globals (function objects from `def`, module-scope
        # assignments like `result = ...`), not the algorithm's actual
        # working state, and a function object isn't deepcopy-able so
        # _safe_copy() falls back to repr(), producing values like
        # "<function two_sum at 0x7fa...>" in the Variables panel.
        #
        # Code with no function definitions at all (plain top-level
        # statements, no `def` anywhere) has no other frame to trace, so
        # in that case the module frame is kept and this never skips.
        if frame.f_code.co_name == "<module>" and has_function_defs:
            return tracer

        snapshot = {}
        for key, val in frame.f_locals.items():
            if key in IGNORED_VARS:
                continue
            copied = _safe_copy(val)
            snapshot[key] = copied if _is_serializable(copied) else repr(copied)

        steps.append({
            "line": frame.f_lineno,
            "variables": snapshot,
            "event": event,
            "return_value": repr(arg) if event == "return" else None,
        })
        return tracer

    # Capture print() output by redirecting stdout
    import io
    import builtins
    original_print = builtins.print
    output_lines = []

    def capturing_print(*args, **kwargs):
        line = " ".join(str(a) for a in args)
        output_lines.append(line)
        original_print(*args, **kwargs)

    builtins.print = capturing_print

    # Set a wall-clock timeout so infinite loops can't hang the worker
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(EXECUTION_TIMEOUT_SECONDS)

    sys.settrace(tracer)
    error = None

    try:
        compiled = compile(code, "<string>", "exec")
        exec(compiled, {}, local_vars)
    except ExecutionTimeoutError:
        error = f"Execution timed out after {EXECUTION_TIMEOUT_SECONDS} seconds"
    except SyntaxError as e:
        error = f"Syntax error on line {e.lineno}: {e.msg}"
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
    finally:
        sys.settrace(None)
        signal.alarm(0)
        builtins.print = original_print

    if error:
        steps.append({
            "line": None,
            "variables": {},
            "event": "error",
            "error": error,
        })

    # Attach print output to the last step
    if output_lines and steps:
        steps[-1]["output"] = "\n".join(output_lines)

    return steps
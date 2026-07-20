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
      - event (str): 'line', 'call', 'return', 'error', or 'truncated'
      - output (str): any print() output from this step

    NOTE ON MAX_STEPS: once the cap is hit, a single synthetic
    {"event": "truncated"} step is appended and tracing is switched off
    for the remainder of execution (see the tracer() closure below).
    Returning None from a trace function only stops *tracing* -- the
    code keeps running to completion untraced, including whatever
    'return' event would otherwise have been captured. Without the
    truncated marker, a long-running loop would previously just stop
    accumulating steps with no signal to the caller that anything was
    cut short, and no narrated return value, since that final 'return'
    event silently never reaches the tracer. Downstream (narration_builder.py,
    manim_renderer.py) can look for this event to tell the person the
    trace was cut off, instead of the video just quietly ending.
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
            # Only append the marker once, right on the transition into
            # "we've hit the cap" -- every subsequent tracer call (for
            # this frame or any new one) would otherwise re-enter this
            # branch and keep appending duplicates.
            if not steps or steps[-1].get("event") != "truncated":
                steps.append({
                    "line": None,
                    "variables": {},
                    "event": "truncated",
                })
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
        # NOTE: a single dict, used for both globals and locals, is
        # deliberate and load-bearing -- not a simplification. Passing
        # two SEPARATE dicts here (e.g. exec(compiled, {}, local_vars))
        # is a classic exec() gotcha: top-level code then behaves as if
        # it's running inside a function body, so `def factorial(n): ...`
        # binds the name `factorial` into the locals dict, while the
        # function object's own __globals__ points at the (different,
        # empty) globals dict. The first top-level call to factorial(5)
        # still works, but the moment factorial calls ITSELF from inside
        # its own body, that lookup goes through __globals__ and finds
        # nothing there -- a NameError on the exact name that's clearly
        # defined right above it. This breaks any submission with
        # recursion, or with one top-level function calling another.
        # Using one shared dict for both matches how a real module
        # actually executes (a module's __dict__ serves as both its
        # globals and where top-level names land), which is why this
        # only ever shows up under exec() with mismatched dicts and
        # never when just running the same code as a normal script.
        exec(compiled, local_vars)
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
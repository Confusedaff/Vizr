from typing import List, Dict, Any, Tuple


def build_narration_lines(steps: List[Dict[str, Any]], code: str = "") -> List[Tuple[int, str]]:
    """
    Convert the list of execution trace steps into narration lines, each
    tagged with the index of the step it describes.

    Returns a list of (step_index, text) tuples rather than one joined
    string. step_index refers to the position in `steps` -- the same
    index the Manim renderer iterates over -- so the renderer can attach
    each narration clip's audio to the exact animation beat for that
    step via Scene.add_sound(), instead of narrating on a separate,
    unsynchronized timeline.

    step_index of -1 is the intro line (played at the very start) and
    -2 is the outro line (played at the very end). These are two
    distinct sentinels, not one value reused for both, because the
    renderer builds a dict keyed by step_index -- reusing one value
    for both would make the outro silently overwrite the intro's
    entry in that dict.

    Kept intentionally terse: only narrate steps where something
    meaningfully changed, matching when the renderer's array/variable
    animations actually update, rather than describing every traced
    line regardless of whether anything visually changed.
    """
    result: List[Tuple[int, str]] = [(-1, "Let's walk through this algorithm.")]

    prev_vars = {}

    for i, step in enumerate(steps):
        variables = step.get("variables", {})
        event = step.get("event", "line")
        output = step.get("output")
        error = step.get("error")

        if error:
            result.append((i, f"The execution hit an error: {error}"))
            break

        if event == "return":
            return_val = step.get("return_value")
            result.append((i, f"The function returns {return_val}."))
            continue

        changed = []
        for key, val in variables.items():
            if key not in prev_vars or prev_vars[key] != val:
                changed.append((key, val))

        if changed:
            key, val = changed[0]
            if isinstance(val, list):
                text = f"Now tracking a list of {len(val)} items."
            elif isinstance(val, int):
                text = f"{key} becomes {val}."
            else:
                text = f"{key} updates."
            result.append((i, text))

        prev_vars = dict(variables)

        if output:
            result.append((i, f"Output: {output}"))

    result.append((-2, "That's the full walkthrough."))
    return result

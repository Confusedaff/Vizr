from typing import List, Dict, Any, Tuple
import ast


def _speakable(value_repr: str) -> str:
    """
    Convert a repr()-formatted value (as produced by tracer.py's
    `return_value` field) into TTS-safe spoken phrasing.

    Without this, narration text like "The function returns [0, 1]."
    hands the TTS model literal Python syntax — brackets, quote marks,
    comma-separated tokens — that it was never trained on natural
    prose to pronounce. Tacotron2-family models degrade badly on
    inputs like this: dropped syllables, mumbling, or unintelligible
    output, often worse on the tokens near the end of the utterance
    once the model has drifted off-distribution. Since almost every
    algorithm ends in a `return`, this line plays on nearly every
    rendered video, right as it's wrapping up.

    Reparses the repr string back into a real value via
    ast.literal_eval (safe: evaluates only literal structures, never
    arbitrary code) and re-describes it in words. Falls back to the
    raw repr string unchanged if it isn't a parseable literal, so a
    custom object's __repr__ output still gets spoken as something
    rather than silently dropped.
    """
    try:
        value = ast.literal_eval(value_repr)
    except (ValueError, SyntaxError):
        return value_repr

    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return "an empty list"
        if len(value) <= 4:
            return "the list " + ", ".join(str(v) for v in value)
        return f"a list of {len(value)} items"
    if isinstance(value, dict):
        if len(value) == 0:
            return "an empty dictionary"
        entry_word = "entry" if len(value) == 1 else "entries"
        return f"a dictionary with {len(value)} {entry_word}"
    if isinstance(value, str):
        return value  # plain text content, no surrounding quote characters
    return str(value)  # int, float, etc. — already speakable as-is


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
            result.append((i, f"The function returns {_speakable(return_val)}."))
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

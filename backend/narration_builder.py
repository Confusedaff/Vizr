from typing import List, Dict, Any


def build_narration_script(steps: List[Dict[str, Any]], code: str = "") -> str:
    """
    Convert the list of execution trace steps into a natural-language
    narration script for the TTS engine.
    """
    lines = [
        "Welcome to the algorithm visualization.",
        "Let's walk through this code step by step.",
        f"The algorithm has {len(steps)} execution steps in total.",
    ]

    prev_vars = {}

    for i, step in enumerate(steps):
        line_num = step.get("line")
        variables = step.get("variables", {})
        event = step.get("event", "line")
        output = step.get("output")
        error = step.get("error")

        if error:
            lines.append(f"The execution encountered an error: {error}")
            break

        if event == "return":
            return_val = step.get("return_value")
            lines.append(f"Step {i + 1}. The function returns the value {return_val}.")
            continue

        step_desc = f"Step {i + 1}. We are now on line {line_num}."

        # Describe variable changes since the last step
        changed = []
        for key, val in variables.items():
            if key not in prev_vars or prev_vars[key] != val:
                changed.append((key, val))

        if changed:
            for key, val in changed[:3]:    # Describe at most 3 changes per step
                if isinstance(val, list):
                    step_desc += f" The list {key} now has {len(val)} elements."
                elif isinstance(val, dict):
                    step_desc += f" The dictionary {key} now has {len(val)} entries."
                elif isinstance(val, int):
                    step_desc += f" {key} is now {val}."
                else:
                    step_desc += f" {key} changed."

        lines.append(step_desc)
        prev_vars = dict(variables)

        if output:
            lines.append(f"The program printed: {output}")

    lines.append("The visualization is now complete.")
    return " ".join(lines)
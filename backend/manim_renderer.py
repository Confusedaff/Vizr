import os
import re
import ast
import shutil
import tempfile
import glob
from manim import *
from typing import List, Dict, Any, Optional

MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")

# Minimum time to hold on a step even if it has no narration, so fast
# loops don't flash by unreadably. Narrated steps use the clip's real
# duration instead (see construct(), narration handling below).
MIN_STEP_HOLD = 0.4

# ── Palette pulled directly from the app's own design tokens (App.css) ──
# Kept as plain hex strings (not Manim's built-in BLUE/YELLOW/RED/GRAY) so
# the rendered video reads as part of the same product as the surrounding
# UI chrome, rather than a generic Manim tutorial embedded in it.
BG = "#0f1419"              # --bg
SURFACE = "#161d29"         # --surface
SURFACE_RAISED = "#1c2433"  # --surface-raised
BORDER = "#2a3444"          # --border
ACCENT = "#f5c542"          # --accent
SUCCESS = "#4fb0a5"         # --success
DANGER = "#f0716b"          # --danger
TEXT_PRIMARY = "#e8ecf1"    # --text-primary
TEXT_SECONDARY = "#8593a8"  # --text-secondary
TEXT_TERTIARY = "#5b6577"   # --text-tertiary

# Colors cycled across simultaneously-highlighted array indices (e.g. a
# binary search's low/mid/high all live at once). Reuses the app's three
# semantic colors rather than inventing a fourth hue that isn't part of
# its actual palette; if a fourth index is ever live at once this just
# cycles back to ACCENT, which is a reasonable fallback for a case that's
# rare in practice (most traced algorithms track at most 2-3 indices).
INDEX_HIGHLIGHT_COLORS = [ACCENT, SUCCESS, DANGER]

# "standard" is the default so behavior doesn't change unless a caller
# explicitly opts into a slower, crisper render.
QUALITY_MAP = {
    "standard": "medium_quality",   # 720p30 — good balance of speed vs quality
    "high": "high_quality",         # 1080p60 — slower, crisper; opt-in
}

# Both are used consistently for every text mobject in the scene so the
# video reads as one deliberate typeface choice rather than mixed fonts.
# Space Grotesk (the app's --font-display) isn't packaged for Debian/Ubuntu
# and pulling arbitrary font files at build time isn't reliable, so this
# uses --font-mono everywhere instead of trying to match --font-display too.
FONT_MONO = "JetBrains Mono"

# Roughly bounds how big the code panel is allowed to get before its font
# shrinks further. Without a cap, a long submission would either overflow
# the frame or become illegibly tiny — see _fit_code_panel().
CODE_PANEL_MAX_WIDTH = 6.4
CODE_PANEL_MAX_HEIGHT = 6.4


def _extract_title(code: str) -> str:
    """
    Best-effort label for the scene title: the first function name
    defined in the submitted code (most traced submissions are a single
    function), falling back to a generic label for plain top-level
    scripts with no function at all. This never raises -- a submission
    that fails to parse here will already have been caught and reported
    as a syntax error by tracer.py before rendering ever starts, so this
    function only needs a safe fallback, not full error handling.
    """
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
    except SyntaxError:
        pass
    return "Algorithm Visualization"


def _fit_code_panel(code_obj: "Code") -> None:
    """
    Scale the Code mobject to fit within CODE_PANEL_MAX_WIDTH x
    CODE_PANEL_MAX_HEIGHT, using whichever dimension is more constraining.
    A plain scale_to_fit_width() alone would let a long submission (many
    lines, short width) overflow past the bottom of the frame.
    """
    width_scale = CODE_PANEL_MAX_WIDTH / code_obj.width
    height_scale = CODE_PANEL_MAX_HEIGHT / code_obj.height
    code_obj.scale(min(width_scale, height_scale))


class AlgorithmScene(Scene):
    """
    Manim scene that animates a traced Python algorithm execution,
    with narration audio embedded directly into the same render via
    Scene.add_sound() — rather than generated as a separate audio file
    on an independent timeline. This guarantees the two can't drift
    apart the way two separately-generated, separately-timed files can.

    Layout is a two-column split: the submitted source code (with a
    highlight box tracking the active line) on the left, and a
    variables panel / array visualization / step counter stacked on
    the right — rather than showing only a disconnected "Line N" badge
    with no code actually visible, which was the previous behavior.
    """

    def __init__(
        self,
        steps: List[Dict],
        job_id: str,
        code: str = "",
        narration_by_step: Optional[Dict[int, tuple]] = None,
        **kwargs,
    ):
        """
        narration_by_step: dict mapping step index -> (clip_path, duration_seconds).
        Index -1 is reserved for intro/outro narration, played at the very
        start/end of the scene rather than tied to a specific step.
        Pass None (or omit) to render with no audio at all.
        """
        self.steps = steps
        self.job_id = job_id
        self.code = code
        self.narration_by_step = narration_by_step or {}
        super().__init__(**kwargs)

    def _play_narration_if_any(self, step_index: int) -> float:
        """
        If step_index has a narration clip, attach it via add_sound() and
        return its duration so the caller can extend self.wait() to match.
        Returns 0.0 if there's no narration for this step.
        """
        entry = self.narration_by_step.get(step_index)
        if not entry:
            return 0.0
        clip_path, duration = entry
        if clip_path and os.path.exists(clip_path):
            self.add_sound(clip_path)
            return duration
        return 0.0

    def _find_array_var_name(self) -> Optional[str]:
        """
        Scan every step for the first variable whose value is a list, and
        use that variable's name for the array visualization for the
        whole scene. Generalizes the previous behavior of only ever
        looking for a variable literally named "nums" — most real
        submissions won't happen to use that exact name (arr, values,
        lst, a, ...), and this way any single-list-variable algorithm
        gets its array drawn regardless of what the person called it.
        Stabilizes on the FIRST list variable found so the visualization
        doesn't flip to a different array mid-video if a second list
        variable appears later (e.g. a `seen` dict-of-lists elsewhere).
        """
        for step in self.steps:
            for key, val in step.get("variables", {}).items():
                if isinstance(val, list):
                    return key
        return None

    def construct(self):
        array_var_name = self._find_array_var_name()

        # ── Left column: the actual submitted source, with a highlight
        # box that will Transform between lines as execution proceeds ──
        code_obj = Code(
            code_string=self.code if self.code.strip() else "# (no code)",
            language="python",
            formatter_style="one-dark",
            background="window",
            add_line_numbers=True,
            background_config={
                "stroke_color": BORDER,
                "fill_color": SURFACE,
                "corner_radius": 0.12,
                "stroke_width": 1,
            },
            paragraph_config={
                "font": FONT_MONO,
                "font_size": 20,
                "line_spacing": 0.55,
                # Manim's ligature-splitting workaround (its default) relies
                # on a 1:1 rendered-glyph-to-character mapping to slice the
                # highlighted HTML back into individually addressable
                # per-line/per-character mobjects. JetBrains Mono ships its
                # own programming ligatures (->, ==, !=, ...), and the two
                # mechanisms disagree on glyph counts, raising an
                # IndexError deep in Paragraph's char-splitting -- turning
                # ligatures back on (i.e. NOT disabling them) sidesteps the
                # conflict entirely, and looks perfectly fine for a code
                # display where ligatures are normal and expected.
                "disable_ligatures": False,
            },
        )
        _fit_code_panel(code_obj)
        code_obj.to_corner(UL, buff=0.5)
        self.add(code_obj)

        num_code_lines = len(code_obj.code_lines)

        # ── Right column: title, variables panel, array, step counter ──
        title = Text(
            _extract_title(self.code), font=FONT_MONO, font_size=24,
            color=TEXT_PRIMARY, weight=BOLD,
        )
        title.to_corner(UR, buff=0.5)

        step_label = Text("Step 0", font=FONT_MONO, font_size=13, color=TEXT_TERTIARY)
        step_label.to_corner(DR, buff=0.4)

        current_var_box = self._make_var_display({})
        current_var_box.next_to(title, DOWN, buff=0.5, aligned_edge=RIGHT)

        # Intro narration, if any, plays right at the start.
        intro_duration = self._play_narration_if_any(-1)
        self.play(Write(title), FadeIn(current_var_box), Write(step_label))
        self.wait(max(0.3, intro_duration))

        current_array_mob = None   # Persists across steps so it can be Transformed, not recreated
        current_highlight = None   # The moving box tracking the active source line

        for i, step in enumerate(self.steps):
            event = step.get("event")

            if event == "truncated":
                self._show_truncated_note()
                break

            if event == "error":
                self._show_error(step.get("error", "Unknown error"))
                break

            # Update step counter
            new_step_label = Text(f"Step {i + 1} / {len(self.steps)}", font=FONT_MONO, font_size=13, color=TEXT_TERTIARY)
            new_step_label.to_corner(DR, buff=0.4)
            self.play(Transform(step_label, new_step_label), run_time=0.2)

            # Move the highlight box to the current line, if it's a real,
            # in-range line number (return/error-only steps may carry no
            # line at all).
            line_num = step.get("line")
            if line_num and 1 <= line_num <= num_code_lines:
                target_line = code_obj.code_lines[line_num - 1]
                new_highlight = SurroundingRectangle(
                    target_line, color=ACCENT, buff=0.06, stroke_width=2, corner_radius=0.05,
                )
                if current_highlight is None:
                    current_highlight = new_highlight
                    self.play(FadeIn(current_highlight), run_time=0.2)
                else:
                    self.play(Transform(current_highlight, new_highlight), run_time=0.25)

            # Update variable display
            variables = step.get("variables", {})
            if variables:
                new_var_box = self._make_var_display(variables)
                new_var_box.next_to(title, DOWN, buff=0.5, aligned_edge=RIGHT)
                self.play(Transform(current_var_box, new_var_box), run_time=0.4)

            # Animate the array if this scene found a list-typed variable
            # anywhere in the trace and it's present in this step. Reuse
            # one persistent mobject and Transform into the new state each
            # step, instead of fading a fresh one in and out.
            if array_var_name and array_var_name in variables and isinstance(variables[array_var_name], list):
                highlighted_indices = self._highlighted_indices(variables, variables[array_var_name])
                new_array_mob = self._make_array(variables[array_var_name], highlighted_indices)
                new_array_mob.next_to(current_var_box, DOWN, buff=0.6, aligned_edge=RIGHT)

                if current_array_mob is None:
                    current_array_mob = new_array_mob
                    self.play(FadeIn(current_array_mob), run_time=0.3)
                else:
                    self.play(Transform(current_array_mob, new_array_mob), run_time=0.4)
            elif current_array_mob is not None:
                self.play(FadeOut(current_array_mob), run_time=0.2)
                current_array_mob = None

            # Narration for this step: attach the audio here, at the same
            # point its corresponding visuals just played, then hold the
            # frame at least as long as the clip takes to finish speaking.
            # This is the actual sync mechanism — the wait length is driven
            # by the real clip duration, not a guessed constant, so video
            # and audio can't end up mismatched in total length.
            narration_duration = self._play_narration_if_any(i)
            self.wait(max(MIN_STEP_HOLD, narration_duration))

        if current_array_mob is not None:
            self.play(FadeOut(current_array_mob), run_time=0.2)

        # Outro narration, if any, plays at the very end.
        outro_duration = self._play_narration_if_any(-2)
        self.wait(max(1.0, outro_duration))

    def _highlighted_indices(self, variables: dict, array: list) -> Dict[int, str]:
        """
        Map array index -> highlight color, for every OTHER int-valued
        variable currently in scope whose value is a valid index into
        the array. Generalizes the previous behavior of only ever
        highlighting a variable literally named "i" — this way a
        two-pointer or binary-search style algorithm (low/mid/high, or
        left/right) gets every live index highlighted, not just one.
        Colors are assigned in the (stable) order variables appear in
        the snapshot dict, cycling through INDEX_HIGHLIGHT_COLORS.
        """
        result: Dict[int, str] = {}
        color_i = 0
        for key, val in variables.items():
            if isinstance(val, bool):
                continue  # bool is a subclass of int; not a meaningful index
            if isinstance(val, int) and 0 <= val < len(array):
                result[val] = INDEX_HIGHLIGHT_COLORS[color_i % len(INDEX_HIGHLIGHT_COLORS)]
                color_i += 1
        return result

    def _make_var_display(self, variables: dict) -> VGroup:
        """Render a neat variable panel."""
        lines = [Text("Variables", font=FONT_MONO, font_size=15, color=ACCENT, weight=BOLD)]
        for key, val in list(variables.items())[:8]:   # Show at most 8 vars
            display = f"{key} = {repr(val)}"
            if len(display) > 40:
                display = display[:37] + "..."
            lines.append(Text(display, font=FONT_MONO, font_size=13, color=TEXT_PRIMARY))

        group = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        bg = RoundedRectangle(
            corner_radius=0.12, width=group.width + 0.6, height=group.height + 0.5,
            color=BORDER, fill_color=SURFACE_RAISED, fill_opacity=1, stroke_width=1,
        )
        bg.move_to(group)
        return VGroup(bg, group)

    def _make_array(self, values: list, highlighted_indices: Dict[int, str]) -> VGroup:
        """
        Render an array of numbered boxes. Highlighted indices (per
        _highlighted_indices) get their assigned color at full opacity;
        everything else is drawn dimmed, so the eye is drawn to whatever
        the algorithm is actually comparing/touching this step instead of
        every box reading with equal visual weight.
        """
        boxes = []
        for idx, val in enumerate(values[:12]):    # Show at most 12 elements
            is_highlighted = idx in highlighted_indices
            color = highlighted_indices.get(idx, BORDER)
            square = RoundedRectangle(
                corner_radius=0.06, width=0.62, height=0.62,
                color=color, fill_color=SURFACE_RAISED,
                fill_opacity=1 if is_highlighted else 0.55,
                stroke_width=2 if is_highlighted else 1,
            )
            display_val = str(val)
            if len(display_val) > 6:
                display_val = display_val[:5] + "…"
            label = Text(
                display_val, font=FONT_MONO, font_size=16,
                color=TEXT_PRIMARY if is_highlighted else TEXT_SECONDARY,
            )
            label.move_to(square.get_center())
            index_label = Text(str(idx), font=FONT_MONO, font_size=11, color=TEXT_TERTIARY)
            index_label.next_to(square, DOWN, buff=0.08)
            boxes.append(VGroup(square, label, index_label))

        return VGroup(*boxes).arrange(RIGHT, buff=0.1)

    def _show_error(self, message: str):
        """Display an error message at the end, styled to match the app's danger color."""
        display_message = message if len(message) <= 60 else message[:57] + "..."
        error_text = Text(f"Error: {display_message}", font=FONT_MONO, font_size=16, color=DANGER)
        error_text.move_to(ORIGIN)
        self.play(Write(error_text))
        self.wait(2)

    def _show_truncated_note(self):
        """
        Shown when tracer.py's MAX_STEPS cap was hit. Previously this case
        wasn't distinguished at all -- the video would just stop, with no
        explanation and no narrated return value (see tracer.py's
        "truncated" event docs). This makes the cutoff visible on-screen
        instead of leaving it silent.
        """
        note = Text(
            "Showing a partial trace — this run is longer than we can fully visualize.",
            font=FONT_MONO, font_size=16, color=TEXT_SECONDARY,
        )
        note.width = min(note.width, 11)
        note.move_to(ORIGIN)
        self.play(FadeIn(note))
        self.wait(2)


def render_scene(
    steps: List[Dict],
    job_id: str,
    code: str = "",
    narration_by_step: Optional[Dict[int, tuple]] = None,
    quality: str = "standard",
):
    """
    Entry point called by the Celery worker.
    Renders the AlgorithmScene — now with narration audio embedded
    directly in the output — and saves the single combined MP4 to
    MEDIA_PATH. There is no separate audio file anymore: Manim's own
    SceneFileWriter muxes the added sounds into the same .mp4 container
    as part of its normal combine step.

    quality: "standard" (720p30, default) or "high" (1080p60, slower).
    Falls back to "standard" for any unrecognized value rather than
    raising, since a render job failing outright over a bad quality
    string would be a worse failure mode than silently using the default.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config.media_dir = tmpdir
        config.quality = QUALITY_MAP.get(quality, QUALITY_MAP["standard"])
        config.verbosity = "ERROR"
        config.disable_caching = True
        config.background_color = BG

        scene = AlgorithmScene(steps, job_id, code=code, narration_by_step=narration_by_step)
        scene.render()

        candidates = glob.glob(os.path.join(tmpdir, "videos", "**", "*.mp4"), recursive=True)
        if not candidates:
            raise FileNotFoundError(
                f"Manim did not produce any .mp4 output under: {os.path.join(tmpdir, 'videos')}"
            )
        output_path = candidates[0]

        destination = os.path.join(MEDIA_PATH, f"{job_id}.mp4")
        shutil.move(output_path, destination)

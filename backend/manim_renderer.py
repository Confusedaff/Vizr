import os
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


class AlgorithmScene(Scene):
    """
    Manim scene that animates a traced Python algorithm execution,
    with narration audio embedded directly into the same render via
    Scene.add_sound() — rather than generated as a separate audio file
    on an independent timeline. This guarantees the two can't drift
    apart the way two separately-generated, separately-timed files can.
    """

    def __init__(
        self,
        steps: List[Dict],
        job_id: str,
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

    def construct(self):
        # Intro narration, if any, plays right at the start.
        intro_duration = self._play_narration_if_any(-1)

        # Title
        title = Text("Algorithm Visualization", font_size=28, color=BLUE)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(max(0.3, intro_duration))

        # Variables display panel — shows variable names and values
        var_display = self._make_var_display({})
        var_display.to_edge(LEFT).shift(DOWN * 0.5)
        self.play(FadeIn(var_display))

        # Step counter
        step_label = Text("Step: 0", font_size=18, color=GRAY)
        step_label.to_corner(DR)
        self.play(Write(step_label))

        current_var_box = var_display
        current_array_mob = None   # Persists across steps so it can be Transformed, not recreated

        for i, step in enumerate(self.steps):
            if step.get("event") == "error":
                self._show_error(step.get("error", "Unknown error"))
                break

            # Update step counter
            new_step_label = Text(f"Step: {i + 1} / {len(self.steps)}", font_size=18, color=GRAY)
            new_step_label.to_corner(DR)
            self.play(Transform(step_label, new_step_label), run_time=0.2)

            # Update variable display
            variables = step.get("variables", {})
            if variables:
                new_var_box = self._make_var_display(variables)
                new_var_box.to_edge(LEFT).shift(DOWN * 0.5)
                self.play(Transform(current_var_box, new_var_box), run_time=0.4)

            # Line highlight annotation
            line_num = step.get("line")
            if line_num:
                line_text = Text(f"Line {line_num}", font_size=16, color=YELLOW)
                line_text.to_corner(UR)
                self.play(FadeIn(line_text), run_time=0.2)
                self.wait(0.5)
                self.play(FadeOut(line_text), run_time=0.2)

            # Animate array if 'nums' variable is present in this step.
            # Reuse one persistent mobject and Transform into the new state
            # each step, instead of fading a fresh one in and out.
            if "nums" in variables and isinstance(variables["nums"], list):
                new_array_mob = self._make_array(
                    variables["nums"],
                    highlight_index=variables.get("i")
                )
                new_array_mob.move_to(ORIGIN + UP * 0.5)

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

    def _make_var_display(self, variables: dict) -> VGroup:
        """Render a neat variable panel."""
        lines = [Text("Variables", font_size=16, color=BLUE_B)]
        for key, val in list(variables.items())[:8]:   # Show at most 8 vars
            display = f"{key} = {repr(val)}"
            if len(display) > 40:
                display = display[:37] + "..."
            lines.append(Text(display, font_size=13, color=WHITE))

        group = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        bg = SurroundingRectangle(group, color=DARK_GRAY, fill_opacity=0.3, buff=0.2)
        return VGroup(bg, group)

    def _make_array(self, nums: list, highlight_index=None) -> VGroup:
        """Render an array of numbered boxes."""
        boxes = []
        for idx, val in enumerate(nums[:12]):    # Show at most 12 elements
            square = Square(side_length=0.7, color=BLUE if idx != highlight_index else YELLOW)
            label = Text(str(val), font_size=18)
            label.move_to(square.get_center())
            index_label = Text(str(idx), font_size=12, color=GRAY)
            index_label.next_to(square, DOWN, buff=0.1)
            boxes.append(VGroup(square, label, index_label))

        return VGroup(*boxes).arrange(RIGHT, buff=0.08)

    def _show_error(self, message: str):
        """Display a red error message at the end."""
        error_text = Text(f"Error: {message}", font_size=16, color=RED)
        error_text.move_to(ORIGIN)
        self.play(Write(error_text))
        self.wait(2)


def render_scene(steps: List[Dict], job_id: str, narration_by_step: Optional[Dict[int, tuple]] = None):
    """
    Entry point called by the Celery worker.
    Renders the AlgorithmScene — now with narration audio embedded
    directly in the output — and saves the single combined MP4 to
    MEDIA_PATH. There is no separate audio file anymore: Manim's own
    SceneFileWriter muxes the added sounds into the same .mp4 container
    as part of its normal combine step.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config.media_dir = tmpdir
        config.quality = "medium_quality"    # 720p30 — good balance of speed vs quality
        config.verbosity = "ERROR"
        config.disable_caching = True

        scene = AlgorithmScene(steps, job_id, narration_by_step=narration_by_step)
        scene.render()

        candidates = glob.glob(os.path.join(tmpdir, "videos", "**", "*.mp4"), recursive=True)
        if not candidates:
            raise FileNotFoundError(
                f"Manim did not produce any .mp4 output under: {os.path.join(tmpdir, 'videos')}"
            )
        output_path = candidates[0]

        destination = os.path.join(MEDIA_PATH, f"{job_id}.mp4")
        shutil.move(output_path, destination)

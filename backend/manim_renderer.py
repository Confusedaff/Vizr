import os
import shutil
import tempfile
from manim import *
from typing import List, Dict, Any

MEDIA_PATH = os.getenv("MEDIA_PATH", "/app/media")


class AlgorithmScene(Scene):
    """
    Manim scene that animates a traced Python algorithm execution.
    Receives a list of step dicts from the tracer and renders them
    as an MP4 video file.
    """

    def __init__(self, steps: List[Dict], job_id: str, **kwargs):
        self.steps = steps
        self.job_id = job_id
        super().__init__(**kwargs)

    def construct(self):
        # Title
        title = Text("Algorithm Visualization", font_size=28, color=BLUE)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.3)

        # Variables display panel — shows variable names and values
        var_display = self._make_var_display({})
        var_display.to_edge(LEFT).shift(DOWN * 0.5)
        self.play(FadeIn(var_display))

        # Step counter
        step_label = Text("Step: 0", font_size=18, color=GRAY)
        step_label.to_corner(DR)
        self.play(Write(step_label))

        current_var_box = var_display

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

            # Animate array if 'nums' variable is present in this step
            if "nums" in variables and isinstance(variables["nums"], list):
                array_mob = self._make_array(
                    variables["nums"],
                    highlight_index=variables.get("i")
                )
                array_mob.move_to(ORIGIN + UP * 0.5)
                self.play(FadeIn(array_mob), run_time=0.3)
                self.wait(0.4)
                self.play(FadeOut(array_mob), run_time=0.2)

        self.wait(1)

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


def render_scene(steps: List[Dict], job_id: str):
    """
    Entry point called by the Celery worker.
    Renders the AlgorithmScene and saves the MP4 to MEDIA_PATH.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config.media_dir = tmpdir
        config.quality = "medium_quality"    # 720p30 — good balance of speed vs quality
        config.verbosity = "ERROR"
        config.disable_caching = True

        scene = AlgorithmScene(steps, job_id)
        scene.render()

        # Find the output MP4 and move it to the shared media folder
        output_path = os.path.join(
            tmpdir, "videos", "AlgorithmScene", "720p30", "AlgorithmScene.mp4"
        )

        if not os.path.exists(output_path):
            raise FileNotFoundError(
                f"Manim did not produce an output file at: {output_path}"
            )

        destination = os.path.join(MEDIA_PATH, f"{job_id}.mp4")
        shutil.move(output_path, destination)
from __future__ import annotations

import math
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import font

from acquisition.simulator import EEGSimulator
from config import PipelineConfig, SPELLER_FREQS, SPELLER_SYMBOLS
from realtime.pipeline import PipelineResult, RealtimePipeline


BG = "#0f1419"
SURFACE = "#171f27"
SURFACE_2 = "#1f2933"
TEXT = "#f6f8fb"
MUTED = "#9aa7b5"
AMBER = "#f4c542"
GREEN = "#2f9e64"
ORANGE = "#b86b31"
GRID_GAP = 12
GRID_ROWS = 5
GRID_COLS = 6
MAX_GRID_WIDTH = 1380
DWELL_TICKS = 9
REPEAT_COOLDOWN_TICKS = 18
MIN_COMMIT_SCORE = 0.65
MIN_COMMIT_MARGIN = 0.035
FLICKER_LOW = 108
FLICKER_HIGH = 178


@dataclass(frozen=True)
class StimulusTarget:
    label: str
    freq: float
    row: int
    col: int


@dataclass
class SessionStats:
    started_at: float | None = None
    decisions: int = 0
    correct_decisions: int = 0
    rejected_decisions: int = 0
    typed_commands: int = 0

    def reset(self) -> None:
        self.started_at = time.perf_counter()
        self.decisions = 0
        self.correct_decisions = 0
        self.rejected_decisions = 0
        self.typed_commands = 0


class SSVEPSpellerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SSVEP Realtime Speller")
        self.root.geometry("1240x820")
        self.root.minsize(1120, 760)
        self.root.configure(bg=BG)

        self.targets = self._build_targets()
        self.config = PipelineConfig(
            window_sec=1.5,
            target_freqs=tuple(target.freq for target in self.targets),
            labels=tuple(target.label for target in self.targets),
            decision_history=4,
            decision_min_votes=3,
        )
        self.source = EEGSimulator(
            fs=self.config.fs,
            channels=self.config.channels,
            target_freq=self.targets[0].freq,
            seed=42,
        )
        self.pipeline = RealtimePipeline(config=self.config, source=self.source)

        self.output = ""
        self.focus_index = 0
        self.commit_cooldown = 0
        self.dwell_label: str | None = None
        self.dwell_count = 0
        self.locked_label: str | None = None
        self.running = False
        self.last_scores: list[float] = []
        self.stats = SessionStats()
        self.canvas_items: list[dict[str, int]] = []
        self.score_rows: list[dict[str, int]] = []

        self.status_var = tk.StringVar(value="Ready")
        self.target_var = tk.StringVar(value="")
        self.decoded_var = tk.StringVar(value="Waiting")
        self.commit_var = tk.StringVar(value="Hold target to type")
        self.quality_var = tk.StringVar(value="Confidence idle")
        self.metrics_var = tk.StringVar(value="CPM 0.0 | Acc -- | ITR --")
        self.output_var = tk.StringVar(value="")
        self.placeholder_var = tk.StringVar(value="Decoded text appears here")
        self.lock_var = tk.StringVar(value="No lock")

        self._build_ui()
        self._select_target(0)
        self._draw_stimuli()
        self._set_static_stimuli()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<space>", lambda _: self.toggle())
        self.root.bind("<Left>", lambda _: self._move_focus(-1))
        self.root.bind("<Right>", lambda _: self._move_focus(1))
        self.root.bind("<Up>", lambda _: self._move_focus(-GRID_COLS))
        self.root.bind("<Down>", lambda _: self._move_focus(GRID_COLS))
        self.root.bind("<Return>", lambda _: self._select_target(self.focus_index))

    def _build_targets(self) -> list[StimulusTarget]:
        return [
            StimulusTarget(label=label, freq=freq, row=index // GRID_COLS, col=index % GRID_COLS)
            for index, (label, freq) in enumerate(zip(SPELLER_SYMBOLS, SPELLER_FREQS))
        ]

    def _build_ui(self) -> None:
        title_font = font.Font(family="Helvetica", size=24, weight="bold")
        subtitle_font = font.Font(family="Helvetica", size=12)
        output_font = font.Font(family="Helvetica", size=34, weight="bold")

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=26, pady=(20, 12))

        title_area = tk.Frame(header, bg=BG)
        title_area.pack(side="left")
        tk.Label(title_area, text="SSVEP Speller", bg=BG, fg=TEXT, font=title_font).pack(anchor="w")
        tk.Label(
            title_area,
            text="Simulated EEG + realtime CCA decoding",
            bg=BG,
            fg=MUTED,
            font=subtitle_font,
        ).pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(header, bg=BG)
        controls.pack(side="right")
        self.start_button = self._control_button(controls, "Start", GREEN, self.toggle)
        self.start_button.pack(side="left", padx=(0, 10))
        self._control_button(controls, "Reset", "#35404c", self.reset_text).pack(side="left")

        output_frame = tk.Frame(self.root, bg=SURFACE, padx=20, pady=16)
        output_frame.pack(fill="x", padx=26, pady=(0, 18))
        tk.Label(
            output_frame,
            textvariable=self.placeholder_var,
            bg=SURFACE,
            fg="#566475",
            anchor="w",
            font=("Helvetica", 13),
        ).pack(fill="x")
        self.output_label = tk.Label(
            output_frame,
            textvariable=self.output_var,
            anchor="w",
            bg=SURFACE,
            fg=TEXT,
            font=output_font,
            height=2,
            justify="left",
        )
        self.output_label.pack(fill="x", pady=(4, 0))
        output_frame.bind(
            "<Configure>",
            lambda event: self.output_label.configure(wraplength=max(200, event.width - 40)),
        )

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 26))

        grid_shell = tk.Frame(body, bg=BG)
        grid_shell.pack(side="left", fill="both", expand=True)
        grid_shell.rowconfigure(0, weight=1)
        grid_shell.columnconfigure(0, weight=1)

        self.stimulus_canvas = tk.Canvas(grid_shell, bg=BG, highlightthickness=0)
        self.stimulus_canvas.grid(row=0, column=0, sticky="nsew")
        self.stimulus_canvas.bind("<Configure>", lambda _: self._draw_stimuli())
        self.stimulus_canvas.bind("<Button-1>", self._on_canvas_click)

        panel = tk.Frame(body, bg=SURFACE, width=330, padx=20, pady=20)
        panel.pack(side="right", fill="y", padx=(22, 0))
        panel.pack_propagate(False)

        self._metric(panel, "Simulated gaze", self.target_var)
        self._metric(panel, "Decoded command", self.decoded_var)
        self._metric(panel, "Typing gate", self.commit_var, value_size=15)
        self._build_dwell_meter(panel)
        self._metric(panel, "Repeat lock", self.lock_var, value_size=13)
        self._metric(panel, "Decision quality", self.quality_var, value_size=14)
        self._metric(panel, "Session metrics", self.metrics_var, value_size=13)
        self._metric(panel, "Pipeline latency", self.status_var, value_size=17)

        tk.Frame(panel, bg="#2c3742", height=1).pack(fill="x", pady=(8, 18))
        tk.Label(
            panel,
            text="Top CCA candidates",
            bg=SURFACE,
            fg=TEXT,
            anchor="w",
            font=("Helvetica", 14, "bold"),
        ).pack(fill="x", pady=(0, 10))

        self.score_canvas = tk.Canvas(panel, bg=SURFACE, highlightthickness=0, height=230)
        self.score_canvas.pack(fill="x")
        self._draw_empty_scores()

    def _build_dwell_meter(self, parent: tk.Widget) -> None:
        self.dwell_canvas = tk.Canvas(parent, bg=SURFACE, highlightthickness=0, height=12)
        self.dwell_canvas.pack(fill="x", pady=(0, 10))
        self._render_dwell_meter(0.0)

    def _control_button(self, parent: tk.Widget, text: str, color: str, command) -> tk.Label:
        button = tk.Label(
            parent,
            text=text,
            bg=color,
            fg="#ffffff",
            width=10,
            padx=8,
            pady=8,
            font=("Helvetica", 12, "bold"),
            cursor="hand2",
        )
        button.bind("<Button-1>", lambda _: command())
        return button

    def _metric(self, parent: tk.Widget, label: str, variable: tk.StringVar, value_size: int = 18) -> None:
        tk.Label(
            parent,
            text=label,
            bg=SURFACE,
            fg=MUTED,
            anchor="w",
            font=("Helvetica", 12),
        ).pack(fill="x")
        tk.Label(
            parent,
            textvariable=variable,
            bg=SURFACE,
            fg=TEXT,
            anchor="w",
            font=("Helvetica", value_size, "bold"),
        ).pack(fill="x", pady=(3, 10))

    def _draw_stimuli(self) -> None:
        canvas = self.stimulus_canvas
        canvas.delete("all")
        self.canvas_items.clear()

        available_width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        width = min(available_width, MAX_GRID_WIDTH)
        x_offset = (available_width - width) / 2
        cell_w = (width - GRID_GAP * (GRID_COLS + 1)) / GRID_COLS
        cell_h = (height - GRID_GAP * (GRID_ROWS + 1)) / GRID_ROWS

        for index, target in enumerate(self.targets):
            x1 = x_offset + GRID_GAP + target.col * (cell_w + GRID_GAP)
            y1 = GRID_GAP + target.row * (cell_h + GRID_GAP)
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            rect = canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#eceff2",
                outline=AMBER if index == self.focus_index else "#2c3540",
                width=4 if index == self.focus_index else 1,
            )
            symbol = canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=self._symbol_text(target.label),
                fill="#10151a",
                font=("Helvetica", self._cell_symbol_size(cell_w), "bold"),
            )
            self.canvas_items.append({"rect": rect, "symbol": symbol})
        if not self.running:
            self._set_static_stimuli()

    def _cell_symbol_size(self, cell_w: float) -> int:
        return max(24, min(42, int(cell_w / 3.6)))

    def _symbol_text(self, label: str) -> str:
        if label == "SPACE":
            return "SPACE"
        return label

    def _draw_empty_scores(self) -> None:
        self.score_canvas.delete("all")
        self.score_canvas.create_text(
            0,
            10,
            text="Start decoding to populate scores",
            anchor="nw",
            fill=MUTED,
            font=("Helvetica", 12),
        )

    def _select_target(self, index: int) -> None:
        self.focus_index = index % len(self.targets)
        target = self.targets[self.focus_index]
        self.source.set_target_frequency(target.freq)
        self.target_var.set(f"{target.label}  {target.freq:.1f}Hz")
        self.locked_label = None
        self.lock_var.set("No lock")
        self._reset_dwell()
        self._update_selection_outline()
        if not self.running:
            self._set_static_stimuli()

    def _update_selection_outline(self) -> None:
        if not self.canvas_items:
            return
        for index, items in enumerate(self.canvas_items):
            selected = index == self.focus_index
            self.stimulus_canvas.itemconfigure(
                items["rect"],
                outline=AMBER if selected else "#2c3540",
                width=4 if selected else 1,
            )

    def _on_canvas_click(self, event: tk.Event) -> None:
        available_width = max(self.stimulus_canvas.winfo_width(), 1)
        height = max(self.stimulus_canvas.winfo_height(), 1)
        width = min(available_width, MAX_GRID_WIDTH)
        x_offset = (available_width - width) / 2
        cell_w = (width - GRID_GAP * (GRID_COLS + 1)) / GRID_COLS
        cell_h = (height - GRID_GAP * (GRID_ROWS + 1)) / GRID_ROWS
        local_x = event.x - x_offset
        if local_x < 0 or local_x > width:
            return
        col = int((local_x - GRID_GAP) // (cell_w + GRID_GAP))
        row = int((event.y - GRID_GAP) // (cell_h + GRID_GAP))
        if not 0 <= row < GRID_ROWS or not 0 <= col < GRID_COLS:
            return
        x_in = (local_x - GRID_GAP) % (cell_w + GRID_GAP)
        y_in = (event.y - GRID_GAP) % (cell_h + GRID_GAP)
        if x_in > cell_w or y_in > cell_h:
            return
        index = row * GRID_COLS + col
        if index < len(self.targets):
            self._select_target(index)

    def _move_focus(self, delta: int) -> None:
        self._select_target(self.focus_index + delta)

    def toggle(self) -> None:
        if self.running:
            self.running = False
            self.source.stop()
            self.start_button.configure(text="Start", bg=GREEN)
            self.status_var.set("Paused")
            self.decoded_var.set("Paused")
            self.quality_var.set("Paused")
            self._reset_dwell()
            self._set_static_stimuli()
            return

        self.running = True
        self.stats.reset()
        self.pipeline.source.start()
        self.start_button.configure(text="Pause", bg=ORANGE)
        self.status_var.set("Running")
        self.decoded_var.set("Buffering")
        self.quality_var.set("Waiting for window")
        self.metrics_var.set("CPM 0.0 | Acc -- | ITR --")
        self._decode_loop()
        self._stimulus_loop()

    def reset_text(self) -> None:
        self.output = ""
        self.output_var.set("")
        self.placeholder_var.set("Decoded text appears here")
        self.commit_cooldown = 0
        self.locked_label = None
        self.lock_var.set("No lock")
        self._reset_dwell()
        self.stats.reset()
        self.metrics_var.set("CPM 0.0 | Acc -- | ITR --")

    def _decode_loop(self) -> None:
        if not self.running:
            return

        result = self.pipeline.step()
        if result is not None:
            self._render_result(result)
            quality = self._decision_quality(result)
            self._update_stats(result)
            if quality["accepted"]:
                self._commit_result(result.label)
            else:
                self.stats.rejected_decisions += 1
                self._reset_dwell(f"Hold: {quality['reason']}")
            self._render_metrics()
        else:
            self.status_var.set("Buffering")

        self.root.after(int(self.config.step_sec * 1000), self._decode_loop)

    def _stimulus_loop(self) -> None:
        if not self.running:
            self._set_static_stimuli()
            return
        if not self.canvas_items:
            self._draw_stimuli()

        now = self.root.tk.call("clock", "milliseconds") / 1000.0
        for index, (target, items) in enumerate(zip(self.targets, self.canvas_items)):
            brightness = 0.5 + 0.5 * math.sin(2 * math.pi * target.freq * now)
            value = int(FLICKER_LOW + brightness * (FLICKER_HIGH - FLICKER_LOW))
            fill = f"#{value:02x}{value:02x}{value:02x}"
            text_color = "#0b1015" if value > 145 else "#f8fafc"
            if index == self.focus_index and value <= 145:
                text_color = AMBER
            self.stimulus_canvas.itemconfigure(items["rect"], fill=fill)
            self.stimulus_canvas.itemconfigure(items["symbol"], fill=text_color)

        if self.running:
            self.root.after(16, self._stimulus_loop)

    def _set_static_stimuli(self) -> None:
        if not self.canvas_items:
            return
        for index, items in enumerate(self.canvas_items):
            selected = index == self.focus_index
            fill = "#2a3037" if selected else "#3b424b"
            text_color = AMBER if selected else "#d6dde5"
            self.stimulus_canvas.itemconfigure(items["rect"], fill=fill)
            self.stimulus_canvas.itemconfigure(items["symbol"], fill=text_color)

    def _render_result(self, result: PipelineResult) -> None:
        score = result.scores[result.stable_prediction]
        self.decoded_var.set(f"{result.label}  {score:.3f}")
        self.status_var.set(f"{result.latency_ms:.1f} ms")
        self.last_scores = result.scores
        self._render_scores(result)

    def _decision_quality(self, result: PipelineResult) -> dict[str, object]:
        ranked = sorted(
            enumerate(result.scores),
            key=lambda item: item[1],
            reverse=True,
        )
        top_index, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        stable_score = result.scores[result.stable_prediction]
        margin = top_score - second_score

        if result.stable_prediction != top_index:
            reason = f"unstable top {self.targets[top_index].label}"
            accepted = False
        elif stable_score < MIN_COMMIT_SCORE:
            reason = f"score {stable_score:.3f}"
            accepted = False
        elif margin < MIN_COMMIT_MARGIN:
            reason = f"margin {margin:.3f}"
            accepted = False
        else:
            reason = f"score {stable_score:.3f}, margin {margin:.3f}"
            accepted = True

        self.quality_var.set(("OK " if accepted else "Blocked ") + reason)
        return {
            "accepted": accepted,
            "reason": reason,
            "top_index": top_index,
            "top_score": top_score,
            "margin": margin,
        }

    def _render_scores(self, result: PipelineResult) -> None:
        canvas = self.score_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 290)
        rows = sorted(
            enumerate(result.scores),
            key=lambda item: item[1],
            reverse=True,
        )[:6]
        max_score = max((score for _, score in rows), default=1.0)

        y = 2
        for rank, (index, score) in enumerate(rows, start=1):
            target = self.targets[index]
            selected = index == result.stable_prediction
            color = AMBER if selected else "#63758a"
            label = f"{rank}. {target.label}  {target.freq:.1f}Hz"
            canvas.create_text(0, y + 6, text=label, anchor="nw", fill=TEXT, font=("Helvetica", 12, "bold"))
            canvas.create_text(
                width - 2,
                y + 6,
                text=f"{score:.3f}",
                anchor="ne",
                fill=TEXT,
                font=("Helvetica", 12, "bold"),
            )
            bar_y = y + 30
            canvas.create_rectangle(0, bar_y, width, bar_y + 8, fill="#26313c", outline="")
            canvas.create_rectangle(
                0,
                bar_y,
                max(4, width * score / max_score),
                bar_y + 8,
                fill=color,
                outline="",
            )
            y += 38

    def _update_stats(self, result: PipelineResult) -> None:
        self.stats.decisions += 1
        target_label = self.targets[self.focus_index].label
        if result.label == target_label:
            self.stats.correct_decisions += 1

    def _render_metrics(self) -> None:
        elapsed = self._elapsed_minutes()
        cpm = self.stats.typed_commands / elapsed if elapsed > 0 else 0.0
        accuracy = self.stats.correct_decisions / self.stats.decisions if self.stats.decisions else 0.0
        itr = self._itr_bits_per_minute(accuracy, max(elapsed, 1e-6))
        acc_text = f"{accuracy * 100:.1f}%" if self.stats.decisions else "--"
        itr_text = f"{itr:.1f}" if self.stats.decisions else "--"
        self.metrics_var.set(f"CPM {cpm:.1f} | Acc {acc_text} | ITR {itr_text} bpm")

    def _elapsed_minutes(self) -> float:
        if self.stats.started_at is None:
            return 0.0
        return max((time.perf_counter() - self.stats.started_at) / 60.0, 0.0)

    def _itr_bits_per_minute(self, accuracy: float, elapsed_minutes: float) -> float:
        if self.stats.decisions == 0 or self.stats.typed_commands == 0:
            return 0.0
        classes = len(self.targets)
        p = min(max(accuracy, 1e-6), 1.0 - 1e-6)
        bits = (
            math.log2(classes)
            + p * math.log2(p)
            + (1 - p) * math.log2((1 - p) / (classes - 1))
        )
        return max(0.0, bits * self.stats.typed_commands / elapsed_minutes)

    def _commit_result(self, label: str) -> None:
        if label == self.locked_label:
            self._reset_dwell(f"Locked {label}")
            self.lock_var.set(f"{label} typed, re-select to repeat")
            return

        if label != self.dwell_label:
            self.dwell_label = label
            self.dwell_count = 1
            self.commit_cooldown = 0
            self._update_commit_progress()
            return

        self.dwell_count += 1

        if self.commit_cooldown > 0:
            self.commit_cooldown -= 1
            self.commit_var.set(f"Cooling {self.commit_cooldown}")
            return

        if self.dwell_count < DWELL_TICKS:
            self._update_commit_progress()
            return

        if label == "SPACE":
            self.output += " "
        elif label == "DEL":
            self.output = self.output[:-1]
        elif label == "CLR":
            self.output = ""
        elif label == "SEND":
            self.status_var.set("Message ready")
        else:
            self.output += label

        self.placeholder_var.set("")
        self.output_var.set(self.output)
        self.dwell_count = 0
        self.commit_cooldown = REPEAT_COOLDOWN_TICKS
        self.locked_label = label
        self.lock_var.set(f"{label} typed, re-select to repeat")
        self.stats.typed_commands += 1
        self.commit_var.set(f"Typed {label}")
        self._render_dwell_meter(1.0)

    def _reset_dwell(self, message: str = "Hold target to type") -> None:
        self.dwell_label = None
        self.dwell_count = 0
        self.commit_var.set(message)
        self._render_dwell_meter(0.0)

    def _update_commit_progress(self) -> None:
        if not self.dwell_label:
            self.commit_var.set("Hold target to type")
            self._render_dwell_meter(0.0)
            return
        ratio = min(1.0, self.dwell_count / DWELL_TICKS)
        progress = int(ratio * 100)
        self.commit_var.set(f"{self.dwell_label} {progress}%")
        self._render_dwell_meter(ratio)

    def _render_dwell_meter(self, ratio: float) -> None:
        if not hasattr(self, "dwell_canvas"):
            return
        canvas = self.dwell_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 280)
        canvas.create_rectangle(0, 2, width, 10, fill="#26313c", outline="")
        canvas.create_rectangle(
            0,
            2,
            width * max(0.0, min(1.0, ratio)),
            10,
            fill=AMBER,
            outline="",
        )

    def close(self) -> None:
        self.running = False
        self.source.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SSVEPSpellerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

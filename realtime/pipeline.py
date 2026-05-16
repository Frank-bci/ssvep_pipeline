import time
from dataclasses import dataclass

from acquisition.simulator import EEGSimulator

from acquisition.base import EEGSource
from processing.buffer import RingBuffer
from processing.filter import BandpassFilter

from decoder.cca import CCAClassifier

from realtime.decision import DecisionSmoother

from config import PipelineConfig


@dataclass(frozen=True)
class PipelineResult:
    raw_prediction: int
    stable_prediction: int
    label: str
    scores: list[float]
    latency_ms: float
    sample_index: int


class RealtimePipeline:

    def __init__(self, config: PipelineConfig | None = None, source: EEGSource | None = None):
        self.config = config or PipelineConfig()

        self.source = source or EEGSimulator(
            fs=self.config.fs,
            channels=self.config.channels,
            target_freq=self.config.target_freqs[1],
        )

        self.buffer = RingBuffer(
            channels=self.config.channels,
            size=self.config.window_size,
        )

        self.filter = BandpassFilter(
            fs=self.config.fs,
            low=self.config.bandpass_low,
            high=self.config.bandpass_high,
        )

        self.decoder = CCAClassifier(
            freqs=self.config.target_freqs,
            fs=self.config.fs,
            win_size=self.config.window_size,
            harmonics=self.config.harmonics,
        )

        self.smoother = DecisionSmoother(
            size=self.config.decision_history,
            min_votes=self.config.decision_min_votes,
        )

    def step(self) -> PipelineResult | None:
        started_at = time.perf_counter()
        chunk = self.source.read_chunk(self.config.step_size)
        self.buffer.append(chunk.data)
        if not self.buffer.ready:
            return None

        window = self.buffer.get()
        filtered = self.filter.apply(window)
        pred, scores = self.decoder.predict(filtered)
        stable_pred = self.smoother.update(pred)
        return PipelineResult(
            raw_prediction=pred,
            stable_prediction=stable_pred,
            label=self.config.labels[stable_pred],
            scores=scores,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            sample_index=chunk.sample_index,
        )

    def run(self, max_iterations: int | None = None):
        self.source.start()
        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                result = self.step()
                if result is not None:
                    score_text = ", ".join(
                        f"{freq:g}Hz={score:.3f}"
                        for freq, score in zip(self.config.target_freqs, result.scores)
                    )
                    print(
                        f"Prediction: {result.label} "
                        f"(raw={self.config.labels[result.raw_prediction]}) | "
                        f"Scores: {score_text} | "
                        f"Latency: {result.latency_ms:.1f} ms"
                    )
                iteration += 1
                time.sleep(self.config.step_sec)
        except KeyboardInterrupt:
            print("Stopped realtime pipeline.")
        finally:
            self.source.stop()

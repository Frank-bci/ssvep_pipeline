from dataclasses import dataclass

FS = 250

WINDOW_SEC = 1.0
STEP_SEC = 0.1

WINDOW_SIZE = int(FS * WINDOW_SEC)
STEP_SIZE = int(FS * STEP_SEC)

CHANNELS = 3

TARGET_FREQS = [8, 10, 12]

CHANNEL_NAMES = ["O1", "Oz", "O2"]

LABELS = ["LEFT", "CENTER", "RIGHT"]

SPELLER_SYMBOLS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ("SPACE", "DEL", "CLR", "SEND")
SPELLER_FREQS = tuple(8.0 + 0.3 * index for index in range(len(SPELLER_SYMBOLS)))


@dataclass(frozen=True)
class PipelineConfig:
    fs: int = FS
    window_sec: float = WINDOW_SEC
    step_sec: float = STEP_SEC
    channels: int = CHANNELS
    target_freqs: tuple[float, ...] = tuple(TARGET_FREQS)
    labels: tuple[str, ...] = tuple(LABELS)
    channel_names: tuple[str, ...] = tuple(CHANNEL_NAMES)
    harmonics: int = 2
    bandpass_low: float = 5.0
    bandpass_high: float = 45.0
    decision_history: int = 5
    decision_min_votes: int = 3

    @property
    def window_size(self) -> int:
        return int(self.fs * self.window_sec)

    @property
    def step_size(self) -> int:
        return int(self.fs * self.step_sec)

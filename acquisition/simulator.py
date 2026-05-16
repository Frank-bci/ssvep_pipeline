from __future__ import annotations

import time
from collections.abc import Sequence

import numpy as np

from acquisition.base import EEGChunk, EEGSource


class EEGSimulator(EEGSource):
    def __init__(
        self,
        fs: int = 250,
        channels: int = 3,
        target_freq: float = 10.0,
        channel_weights: Sequence[float] | None = None,
        noise_uv: float = 4.0,
        ssvep_uv: float = 25.0,
        alpha_uv: float = 8.0,
        seed: int | None = 42,
    ):
        self.fs = fs
        self.channels = channels
        self.target_freq = target_freq
        self.noise_uv = noise_uv
        self.ssvep_uv = ssvep_uv
        self.alpha_uv = alpha_uv
        self.rng = np.random.default_rng(seed)
        self.sample_index = 0
        self.started = False
        if channel_weights is None:
            self.channel_weights = np.linspace(0.75, 1.0, channels)
        else:
            weights = np.asarray(channel_weights, dtype=float)
            if weights.shape != (channels,):
                raise ValueError("channel_weights must match channel count")
            self.channel_weights = weights

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def set_target_frequency(self, freq: float) -> None:
        self.target_freq = freq

    def set_amplitude(self, ssvep_uv: float) -> None:
        self.ssvep_uv = ssvep_uv

    def read_chunk(self, samples: int) -> EEGChunk:
        if not self.started:
            self.start()
        start_index = self.sample_index
        data = self.generate_chunk(samples)
        chunk = EEGChunk(
            data=data,
            timestamp=time.time(),
            sample_index=start_index,
        )
        return chunk

    def generate_chunk(self, samples: int = 25) -> np.ndarray:
        absolute_samples = np.arange(self.sample_index, self.sample_index + samples)
        t = absolute_samples / self.fs

        eeg = self.rng.normal(0.0, self.noise_uv, size=(self.channels, samples))
        alpha = self.alpha_uv * np.sin(2 * np.pi * 10.0 * t + 0.3)
        ssvep = self.ssvep_uv * np.sin(2 * np.pi * self.target_freq * t)
        harmonic = 0.45 * self.ssvep_uv * np.sin(2 * np.pi * self.target_freq * 2 * t)
        common_signal = alpha + ssvep + harmonic

        eeg += self.channel_weights[:, None] * common_signal[None, :]
        self.sample_index += samples
        return eeg

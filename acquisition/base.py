from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EEGChunk:
    data: np.ndarray
    timestamp: float
    sample_index: int


class EEGSource(ABC):
    @abstractmethod
    def start(self) -> None:
        """Allocate resources and begin streaming."""

    @abstractmethod
    def read_chunk(self, samples: int) -> EEGChunk:
        """Return EEG data shaped as channels x samples."""

    @abstractmethod
    def stop(self) -> None:
        """Release resources."""


from __future__ import annotations

from acquisition.base import EEGChunk, EEGSource


class OpenBCIReader(EEGSource):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def start(self) -> None:
        raise NotImplementedError(
            "OpenBCI/BrainFlow source is intentionally a drop-in adapter. "
            "Install hardware settings here without changing realtime.pipeline."
        )

    def read_chunk(self, samples: int) -> EEGChunk:
        raise NotImplementedError("OpenBCI source is not configured yet")

    def stop(self) -> None:
        return None

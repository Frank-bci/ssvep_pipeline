import numpy as np


class RingBuffer:

    def __init__(self, channels, size):

        self.channels = channels
        self.size = size
        self.buffer = np.zeros((channels, size))
        self.samples_seen = 0

    def append(self, data):
        if data.ndim != 2:
            raise ValueError("data must be shaped as channels x samples")
        if data.shape[0] != self.channels:
            raise ValueError(f"expected {self.channels} channels, got {data.shape[0]}")

        n = data.shape[1]
        if n > self.size:
            data = data[:, -self.size:]
            n = self.size

        self.buffer = np.roll(self.buffer, -n, axis=1)
        self.buffer[:, -n:] = data
        self.samples_seen += n

    def get(self):

        return self.buffer.copy()

    @property
    def ready(self):
        return self.samples_seen >= self.size

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def bandpass(data,
             fs=250,
             low=5,
             high=40,
             order=4):

    nyq = fs / 2

    sos = butter(
        order,
        [low / nyq, high / nyq],
        btype='band',
        output="sos",
    )

    return sosfiltfilt(sos, data, axis=1)


class BandpassFilter:
    def __init__(self, fs=250, low=5, high=45, order=4):
        nyq = fs / 2
        if not 0 < low < high < nyq:
            raise ValueError("bandpass limits must satisfy 0 < low < high < fs/2")
        self.sos = butter(order, [low / nyq, high / nyq], btype="band", output="sos")

    def apply(self, data: np.ndarray) -> np.ndarray:
        return sosfiltfilt(self.sos, data, axis=1)

import numpy as np

from sklearn.cross_decomposition import CCA


class CCAClassifier:

    def __init__(self,
                 freqs,
                 fs,
                 win_size,
                 harmonics=2):

        self.freqs = list(freqs)
        self.fs = fs
        self.win_size = win_size
        self.harmonics = harmonics

        self.t = np.arange(win_size) / fs
        self.references = {
            freq: self.create_reference(freq)
            for freq in self.freqs
        }

    def create_reference(self, freq):

        refs = []

        for h in range(1, self.harmonics + 1):

            refs.append(
                np.sin(2 * np.pi * freq * h * self.t)
            )

            refs.append(
                np.cos(2 * np.pi * freq * h * self.t)
            )

        return np.array(refs).T

    def predict(self, eeg):

        if eeg.shape[1] != self.win_size:
            raise ValueError(f"expected window size {self.win_size}, got {eeg.shape[1]}")

        X = eeg.T

        scores = []

        for freq in self.freqs:

            Y = self.references[freq]

            cca = CCA(n_components=1)

            cca.fit(X, Y)

            X_c, Y_c = cca.transform(X, Y)

            corr = np.corrcoef(
                X_c[:, 0],
                Y_c[:, 0]
            )[0, 1]

            scores.append(float(abs(corr)))

        pred = int(np.argmax(scores))

        return pred, scores

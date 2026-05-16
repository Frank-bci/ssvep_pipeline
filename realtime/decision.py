from collections import deque
from collections import Counter


class DecisionSmoother:

    def __init__(self, size=5, min_votes=3):

        self.history = deque(maxlen=size)
        self.min_votes = min_votes
        self.last_stable = None

    def update(self, pred):

        self.history.append(pred)

        winner, votes = Counter(self.history).most_common(1)[0]
        if votes >= self.min_votes:
            self.last_stable = winner
        if self.last_stable is None:
            self.last_stable = pred
        return self.last_stable

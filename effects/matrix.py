import random
from effects.base import PiEffect


class EffectMatrix(PiEffect):
    """Matrix-style rain drops falling from edges to center."""
    name = "matrix"

    def __init__(self):
        super().__init__()
        self.hue = 120  # green
        self.spawn_chance = 15  # percent per frame
        self.trail_len = 15
        self._drops_left = []   # [(position, speed)]
        self._drops_right = []
        self._trail = None

    def next_frame(self, num_leds):
        if self._trail is None or len(self._trail) != num_leds:
            self._trail = [0] * num_leds

        half = num_leds // 2

        # Fade trail
        for i in range(num_leds):
            self._trail[i] = max(0, self._trail[i] - 18)

        # Spawn new drops from left edge
        if random.randint(0, 99) < self.spawn_chance:
            speed = random.uniform(1.5, 4.0)
            self._drops_left.append([0.0, speed])

        # Spawn new drops from right edge
        if random.randint(0, 99) < self.spawn_chance:
            speed = random.uniform(1.5, 4.0)
            self._drops_right.append([float(num_leds - 1), speed])

        # Move left drops (toward center)
        alive = []
        for drop in self._drops_left:
            pos = int(drop[0])
            if 0 <= pos < num_leds:
                self._trail[pos] = 253
            drop[0] += drop[1]
            if drop[0] < half + 10:
                alive.append(drop)
        self._drops_left = alive

        # Move right drops (toward center)
        alive = []
        for drop in self._drops_right:
            pos = int(drop[0])
            if 0 <= pos < num_leds:
                self._trail[pos] = 253
            drop[0] -= drop[1]
            if drop[0] > half - 10:
                alive.append(drop)
        self._drops_right = alive

        return [min(253, v) for v in self._trail]

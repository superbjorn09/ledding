import random
import numpy
from effects.base import PiEffect


class EffectMatrix(PiEffect):
    """Matrix-style rain drops falling from edges to center."""
    name = "matrix"

    def __init__(self):
        super().__init__()
        self.hue = 120
        self.spawn_chance = 15
        self.trail_len = 15
        self._drops_left = []
        self._drops_right = []
        self._trail = None

    def next_frame(self, num_leds):
        if self._trail is None or len(self._trail) != num_leds:
            self._trail = numpy.zeros(num_leds, dtype=numpy.int32)

        half = num_leds // 2

        # Fade trail
        self._trail = numpy.maximum(0, self._trail - 18)

        # Spawn drops
        if random.randint(0, 99) < self.spawn_chance:
            self._drops_left.append([0.0, random.uniform(1.5, 4.0)])
        if random.randint(0, 99) < self.spawn_chance:
            self._drops_right.append([float(num_leds - 1), random.uniform(1.5, 4.0)])

        # Move left drops
        alive = []
        for drop in self._drops_left:
            pos = int(drop[0])
            if 0 <= pos < num_leds:
                self._trail[pos] = 253
            drop[0] += drop[1]
            if drop[0] < half + 10:
                alive.append(drop)
        self._drops_left = alive

        # Move right drops
        alive = []
        for drop in self._drops_right:
            pos = int(drop[0])
            if 0 <= pos < num_leds:
                self._trail[pos] = 253
            drop[0] -= drop[1]
            if drop[0] > half - 10:
                alive.append(drop)
        self._drops_right = alive

        return numpy.clip(self._trail, 0, 253).tolist()

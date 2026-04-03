import numpy
from effects.base import PiEffect


class EffectFire(PiEffect):
    """Fire simulation with flickering flames rising from edges to center."""
    name = "fire"

    def __init__(self):
        super().__init__()
        self.hue = 15
        self.cooling = 55
        self.sparking = 120
        self._heat = None

    def next_frame(self, num_leds):
        half = num_leds // 2
        if self._heat is None or len(self._heat) != half:
            self._heat = numpy.zeros(half, dtype=numpy.int32)

        heat = self._heat
        max_cool = ((self.cooling * 10) // half) + 2

        # Cool down
        heat -= numpy.random.randint(0, max(max_cool, 1), size=half)
        numpy.clip(heat, 0, 255, out=heat)

        # Heat rises (drift upward)
        heat[3:] = (heat[2:-1] + heat[1:-2] + heat[1:-2]) // 3

        # Random sparks at the base
        if numpy.random.randint(0, 256) < self.sparking:
            y = numpy.random.randint(0, min(8, half))
            heat[y] = min(255, int(heat[y]) + numpy.random.randint(160, 256))

        levels = numpy.clip(heat, 0, 253)

        # Mirror: flames from both edges toward center
        return levels[::-1].tolist() + levels.tolist()

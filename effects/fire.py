import random
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
            self._heat = [0] * half

        heat = self._heat

        # Cool down
        for i in range(half):
            heat[i] = max(0, heat[i] - random.randint(0, ((self.cooling * 10) // half) + 2))

        # Heat rises (drift upward)
        for i in range(half - 1, 2, -1):
            heat[i] = (heat[i - 1] + heat[i - 2] + heat[i - 2]) // 3

        # Random sparks at the base
        if random.randint(0, 255) < self.sparking:
            y = random.randint(0, min(7, half - 1))
            heat[y] = min(255, heat[y] + random.randint(160, 255))

        # Map heat to brightness
        levels = [min(253, h) for h in heat]

        # Mirror: flames from both edges toward center
        return list(reversed(levels)) + levels

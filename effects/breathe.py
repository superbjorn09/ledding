import math
import time
from effects.base import PiEffect


class EffectBreathe(PiEffect):
    """Slow breathing pulse on all LEDs."""
    name = "breathe"

    def __init__(self):
        super().__init__()
        self.hue = 200
        self.speed = 1.0  # breaths per second (actually half-cycles)

    def next_frame(self, num_leds):
        t = time.time() * self.speed
        # Smooth sine breathing curve
        val = (math.sin(t * math.pi) * 0.5 + 0.5) ** 2
        brightness = int(val * 253)
        return [brightness] * num_leds

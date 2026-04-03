import time
from effects.base import PiEffect


class EffectStrobe(PiEffect):
    """Stroboscope flashes at configurable rate."""
    name = "strobe"

    def __init__(self):
        super().__init__()
        self.rate = 5.0
        self.on = False
        self.last_toggle = 0
        self.hue = 0  # white/red

    def next_frame(self, num_leds):
        now = time.time()
        interval = 1.0 / (self.rate * 2)
        if now - self.last_toggle >= interval:
            self.on = not self.on
            self.last_toggle = now
        return [253 if self.on else 0] * num_leds

import random
from effects.base import PiEffect, MAX_BRIGHTNESS


class EffectSparkle(PiEffect):
    """Random sparkles appearing and fading out."""
    name = "sparkle"

    def __init__(self):
        super().__init__()
        self.sparkles = {}
        self.spawn_rate = 8
        self.max_life = 15
        self.hue = 50
        self.auto_color = True

    def next_frame(self, num_leds):
        frame = [0] * num_leds

        for _ in range(self.spawn_rate):
            idx = random.randint(0, num_leds - 1)
            if idx not in self.sparkles:
                self.sparkles[idx] = self.max_life

        updated = {}
        for idx, life in self.sparkles.items():
            if idx < num_leds:
                brightness = int(MAX_BRIGHTNESS * (life / self.max_life))
                frame[idx] = max(frame[idx], brightness)
            remaining = life - 1
            if remaining > 0:
                updated[idx] = remaining
        self.sparkles = updated

        return frame

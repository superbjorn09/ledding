import random
import math
import time
from effects.base import PiEffect


class EffectTwinkle(PiEffect):
    """Stars that slowly pulse in and out, like a night sky."""
    name = "twinkle"

    def __init__(self):
        super().__init__()
        self.hue = 220
        self.density = 40  # number of active stars
        self._stars = {}  # {index: (birth_time, frequency)}

    def next_frame(self, num_leds):
        now = time.time()
        frame = [0] * num_leds

        # Spawn stars to maintain density
        while len(self._stars) < self.density:
            idx = random.randint(0, num_leds - 1)
            if idx not in self._stars:
                freq = random.uniform(0.5, 2.0)
                self._stars[idx] = (now + random.uniform(0, 3), freq)

        # Render and cull dead stars
        dead = []
        for idx, (birth, freq) in self._stars.items():
            age = now - birth
            if age > 3.0 / freq:
                dead.append(idx)
                continue
            # Pulse: smooth rise and fall
            phase = age * freq * math.pi
            val = max(0, math.sin(phase))
            if idx < num_leds:
                frame[idx] = int(val * 253)
        for idx in dead:
            del self._stars[idx]

        return frame

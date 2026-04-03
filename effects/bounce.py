import math
from effects.base import PiEffect


class EffectBounce(PiEffect):
    """A ball bouncing between the ends with gravity and damping."""
    name = "bounce"

    def __init__(self):
        super().__init__()
        self.hue = 60
        self.size = 8
        self._pos = 0.0
        self._vel = 0.0
        self._gravity = 0.3
        self._damping = 0.9
        self._launched = False

    def next_frame(self, num_leds):
        frame = [0] * num_leds

        if not self._launched:
            self._vel = 8.0
            self._pos = 0.0
            self._launched = True

        # Physics
        self._vel += self._gravity
        self._pos += self._vel

        # Bounce off far end
        if self._pos >= num_leds - 1:
            self._pos = num_leds - 1
            self._vel = -abs(self._vel) * self._damping

        # Bounce off near end
        if self._pos <= 0:
            self._pos = 0
            self._vel = abs(self._vel) * self._damping

        # Re-launch if stopped
        if abs(self._vel) < 0.5 and self._pos >= num_leds - 3:
            self._launched = False

        # Draw ball
        center = int(self._pos)
        for i in range(self.size):
            idx = center - self.size // 2 + i
            if 0 <= idx < num_leds:
                dist = abs(i - self.size // 2) / (self.size // 2)
                frame[idx] = int(253 * (1.0 - dist * 0.5))

        return frame

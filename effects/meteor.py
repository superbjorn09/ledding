import random
from effects.base import PiEffect


class EffectMeteor(PiEffect):
    """Meteor with a randomly fading trail."""
    name = "meteor"

    def __init__(self):
        super().__init__()
        self.pos = 0
        self.speed = 2
        self.size = 10
        self.trail = None
        self.hue = 15  # orange

    def next_frame(self, num_leds):
        if self.trail is None or len(self.trail) != num_leds:
            self.trail = [0] * num_leds

        for j in range(num_leds):
            if random.randint(0, 9) > 5:
                self.trail[j] = max(0, self.trail[j] - 64)

        for j in range(self.size):
            idx = self.pos - j
            if 0 <= idx < num_leds:
                self.trail[idx] = 253

        self.pos += self.speed
        if self.pos >= num_leds + num_leds:
            self.pos = 0
            self.trail = [0] * num_leds

        return list(self.trail)

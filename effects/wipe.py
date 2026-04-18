from effects.base import PiEffect


class EffectWipe(PiEffect):
    """Color wipe sweeping across the strip."""
    name = "wipe"

    def __init__(self):
        super().__init__()
        self.hue = 0
        self.speed = 5.0
        self._pos = 0.0
        self._on = True  # True = wiping on, False = wiping off

    def next_frame(self, num_leds):
        frame = [0] * num_leds
        pos = int(self._pos)

        if self._on:
            for i in range(min(pos, num_leds)):
                frame[i] = 253
        else:
            for i in range(min(pos, num_leds), num_leds):
                frame[i] = 253

        self._pos += self.speed

        if self._pos >= num_leds:
            self._pos = 0.0
            self._on = not self._on

        return frame

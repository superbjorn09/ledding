from effects.base import PiEffect


class EffectComet(PiEffect):
    """Two comets traveling toward center, flash on collision."""
    name = "comet"

    def __init__(self):
        super().__init__()
        self.hue = 270
        self.speed = 4.0
        self.tail_len = 25
        self._pos = 0.0
        self._flash = 0

    def next_frame(self, num_leds):
        frame = [0] * num_leds
        mid = num_leds // 2

        # Flash on collision
        if self._flash > 0:
            val = int(253 * (self._flash / 8))
            frame = [val] * num_leds
            self._flash -= 1
            if self._flash <= 0:
                self._pos = 0.0
            return frame

        pos = int(self._pos)

        # Left comet (moving right from 0 toward mid)
        for i in range(self.tail_len):
            idx = pos - i
            if 0 <= idx < num_leds:
                brightness = int(253 * (1.0 - i / self.tail_len))
                frame[idx] = max(frame[idx], brightness)

        # Right comet (moving left from end toward mid)
        for i in range(self.tail_len):
            idx = (num_leds - 1 - pos) + i
            if 0 <= idx < num_leds:
                brightness = int(253 * (1.0 - i / self.tail_len))
                frame[idx] = max(frame[idx], brightness)

        self._pos += self.speed

        # Collision at center
        if pos >= mid:
            self._flash = 8

        return frame

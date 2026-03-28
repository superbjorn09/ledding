#ifndef FASTLED_H_MOCK
#define FASTLED_H_MOCK

#include <cstdint>

// --- CHSV ---
struct CHSV {
	uint8_t h, s, v;
	CHSV() : h(0), s(0), v(0) {}
	CHSV(uint8_t hue, uint8_t sat, uint8_t val) : h(hue), s(sat), v(val) {}
};

// --- CRGB ---
struct CRGB {
	uint8_t r;
	uint8_t g;
	uint8_t b;

	enum HTMLColorCode : uint32_t {
		Black    = 0x000000,
		Red      = 0xFF0000,
		Green    = 0x008000,
		Blue     = 0x0000FF,
		White    = 0xFFFFFF,
		Yellow   = 0xFFFF00,
		DeepPink = 0xFF1493,
	};

	CRGB() : r(0), g(0), b(0) {}

	CRGB(uint8_t red, uint8_t grn, uint8_t blu) : r(red), g(grn), b(blu) {}

	CRGB(uint32_t colorcode)
		: r((colorcode >> 16) & 0xFF)
		, g((colorcode >> 8) & 0xFF)
		, b(colorcode & 0xFF) {}

	CRGB(HTMLColorCode colorcode) : CRGB(static_cast<uint32_t>(colorcode)) {}

	CRGB& operator=(uint32_t colorcode) {
		r = (colorcode >> 16) & 0xFF;
		g = (colorcode >> 8) & 0xFF;
		b = colorcode & 0xFF;
		return *this;
	}

	CRGB& operator+=(const CRGB& rhs) {
		uint16_t tr = r + rhs.r; r = (tr > 255) ? 255 : tr;
		uint16_t tg = g + rhs.g; g = (tg > 255) ? 255 : tg;
		uint16_t tb = b + rhs.b; b = (tb > 255) ? 255 : tb;
		return *this;
	}

	CRGB& operator+=(const CHSV& rhs) {
		// Simplified: treat value as red channel contribution
		uint16_t tr = r + rhs.v; r = (tr > 255) ? 255 : tr;
		return *this;
	}

	void setRGB(uint8_t red, uint8_t grn, uint8_t blu) {
		r = red; g = grn; b = blu;
	}

	void setHSV(uint8_t hue, uint8_t sat, uint8_t val) {
		// Simplified: store val in r for testing
		(void)hue; (void)sat;
		r = val; g = 0; b = 0;
	}

	void fadeToBlackBy(uint8_t fadeBy) {
		r = (r > fadeBy) ? r - fadeBy : 0;
		g = (g > fadeBy) ? g - fadeBy : 0;
		b = (b > fadeBy) ? b - fadeBy : 0;
	}
};

// --- CFastLED ---
class CFastLED {
	uint8_t _brightness = 200;
public:
	uint8_t getBrightness() const { return _brightness; }
	void setBrightness(uint8_t b) { _brightness = b; }
	void show() {}
	void clear() {}
};

extern CFastLED FastLED;

// --- Free functions ---
inline void fill_solid(CRGB* leds, int count, CRGB color) {
	for (int i = 0; i < count; i++) {
		leds[i] = color;
	}
}

inline void fadeToBlackBy(CRGB* leds, int count, uint8_t fadeBy) {
	for (int i = 0; i < count; i++) {
		leds[i].fadeToBlackBy(fadeBy);
	}
}

#endif /* FASTLED_H_MOCK */

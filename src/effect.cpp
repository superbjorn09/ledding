#include "config.h"
#include "globals.h"

#include "effect.h"

void Effect::nextColor() {
}
void Effect::prevColor() {
}
void Effect::incIntensity() {
}
void Effect::decIntensity() {
}

/*********************** Effect Bolt *************************/
void EffectBolt::configure(uint16_t startled, int8_t speed, CRGB color, uint16_t delay = 0) {

	this->idx = startled;
	this->speed = speed;
	this->color = color;
	this->delay = delay;

	Serial.printf("Configure led: %d, speed: %d, delay: %d\n", idx, this->speed, this->delay);
}


bool EffectBolt::calcNextFrame() {

	if (delay) {
		fadeToBlackBy(leds, NUM_LEDS, 32);
		delay--;
		return true;
	}

	int BOLT_LEN = 20;

	/* first LED is fractional */
	int ledpos = idx / 32;
	int frac = idx % 32;

	if (frac == 0) {
//		leds[ledpos] += CHSV(0, 255, 255);
		for (int i = 0; i <= ledpos; i++) {
			leds[i] += CHSV(0, 255, 255);
		}
	} else {
		leds[ledpos + 1] += CHSV(0, 255, LIN_EYE[frac]);
	}

#if 0
	if (speed > 0) {
		for (int j = idx; j < idx + speed && j < NUM_LEDS; j+=2) {
			leds[j] += color;
		}
	} else {
		for (int j = idx + speed; j < idx && j >= 0; j+=2) {
			leds[j] += color;
		}
	}
#endif

	idx += speed;

//	if ((speed > 0 && idx >= NUM_LEDS) || (speed < 0 && idx <= 0)) {
//		speed *= -1;
//	}
	/* send next bolt in same direction */
	if (speed > 0 && idx >= (NUM_LEDS - 1) * 32) {
		Serial.println("Start from beginning");
		fill_solid(leds, NUM_LEDS, CRGB::Black);
		idx = 0;
		if (++coloridx >= COLOR_PALETTE_SIZE) {
			coloridx = 0;
		}
		this->color = COLOR_PALETTE[coloridx];
		delay = 8;
	}

//	fadeToBlackBy(leds, NUM_LEDS, 32);
	return true;
}

void EffectBolt::incIntensity() {
	speed += 8;
}

void EffectBolt::decIntensity() {
	speed -= 8;
}

/*********************** Effect Static *************************/
void EffectStatic::configure(CRGB color) {
	this->color[0] = color;
	for (int i = 1; i < SUBMODE_COUNT; i++) {
		this->color[i] = COLOR_PALETTE[(coloridx + i) % COLOR_PALETTE_SIZE];
	}
	draw = true;
}

bool EffectStatic::calcNextFrame() {
	if (!draw) {
		return false;
	}

	switch (submodeidx) {
		/* single color on all LEDs */
		case 0:
		default:
			for (int i = 0; i < NUM_LEDS; i++) {
				leds[i] = color[0];
			}
			break;

		/* use two colors alternatingly */
		case 1: {
			for (int i = 0; i < NUM_LEDS - 1 ; i += 2) {
				leds[i] = color[0];
				leds[i + 1] = color[1];
			}
			break;

		}
		/* use three colors alternatingly */
		case 2:
			for (int i = 0; i < NUM_LEDS - 2 ; i += 3) {
				leds[i] = color[0];
				leds[i + 1] = color[1];
				leds[i + 2] = color[2];
			}
			break;
	}

	draw = false;
	return true;
}

void EffectStatic::nextColor() {
	if (++coloridx >= COLOR_PALETTE_SIZE) {
		coloridx = 0;
	}
	for (int i = 0; i < SUBMODE_COUNT; i++) {
		color[i] = COLOR_PALETTE[(coloridx + i) % COLOR_PALETTE_SIZE];
	}
	draw = true;
}

void EffectStatic::prevColor() {
	if (--coloridx <= 0) {
		coloridx = COLOR_PALETTE_SIZE - 1;
	}
	for (int i = 0; i < SUBMODE_COUNT; i++) {
		color[i] = COLOR_PALETTE[modulo(coloridx - i, COLOR_PALETTE_SIZE)];
	}
	draw = true;
}

void EffectStatic::incIntensity() {
	if (++submodeidx >= SUBMODE_COUNT) {
		submodeidx = 0;
	}
	draw = true;
}

void EffectStatic::decIntensity() {
	if (--submodeidx <= 0) {
		submodeidx = SUBMODE_COUNT - 1;
	}
	draw = true;
}

/*********************** Effect Arc *************************/
void EffectArc::configure(CRGB color1, CRGB color2) {
	this->color1 = color1;
	this->color2 = color2;
}

#define ARC_INITIAL_PAUSE 10
#define ARC_NUMBER 50
#define ARC_PAUSE 15
bool EffectArc::calcNextFrame() {
	if (delay) {
		delay--;
		return false;
	}


	for (int i = ARC_INITIAL_PAUSE; i < ARC_NUMBER + ARC_INITIAL_PAUSE; i++) {
		leds[i] = switchColor ? color2 : color1;
	}
	for (int i = ARC_INITIAL_PAUSE + ARC_NUMBER + ARC_PAUSE;
		i < ARC_NUMBER * 2 + ARC_INITIAL_PAUSE + ARC_PAUSE;
		i++
	) {
		leds[i] = switchColor ? color1 : color2;
	}

	switchColor = !switchColor;
	delay = random(100, 1000);
	return true;
}

/*********************** Effect Sound *************************/
void EffectSound::configure(CRGB color) {
	this->color = color;

	is_new_color = true;
}

bool EffectSound::calcNextFrame() {
	for (int i = 0; i < NUM_LEDS; i++) {
		if (Serial2.available()) {
			uint8_t value = Serial2.read();
			if (value == 0xFE) {
				/* command prefix — skip, handled by handleSerialCommands() */
				continue;
			}
			if (value == 255) {
				currentLED = 0;
				/*  Keep this for Peak Output
				peak = Serial2.read();
				fadeToBlackBy(leds, NUM_LEDS, 192);
				uint8_t counter_peak = 0;
				while ( peak > 0 ) {
				leds[counter_peak].setRGB(255, 0, 0);
				counter_peak++;
				peak--;
				leds[counter_peak].setRGB(255, 0, 0);
				}
				*/

				Serial2.write(84);
				return true;
			}
            leds[currentLED].setRGB(value, 0, 0);
			currentLED++;
		}
	}
	return false;
}

/*********************** Effect Strobe *************************/
void EffectStrobe::configure(CRGB color) { //, uint8_t count, uint8_t flashDelay, uint16_t endPause) {
	this->color = color;
}

bool EffectStrobe::calcNextFrame() {
    count++;
    Serial.println(count);
    if ( count >= 200 ) {
        count = 0;
		this->color = COLOR_PALETTE[random(COLOR_PALETTE_SIZE)];
        return false;
    }
    if ( count >= 100 ) {
		fill_solid(leds, NUM_LEDS, CRGB::Black);
        return true;
    }
    if ( count % 6 >= 3) {
		fill_solid(leds, NUM_LEDS, color);
        return true;
    }
    if ( count % 6 <= 3 ) {
		fill_solid(leds, NUM_LEDS, CRGB::Black);
        return true;
    }
    return false;
}

/*********************** Effect Sparkle *************************/
void EffectSparkle::configure(CRGB color, bool soft) {
	this->color = color;
	this->soft = soft;

	if (soft) {
		for (int i = 0; i < CNT; i++) {
			count[i] = random(50) * -1;
		}
	}
}

bool EffectSparkle::calcNextFrame() {
	/* catch a mode change */
	if (draw) {
		fill_solid(leds, NUM_LEDS, CRGB::Black);
		for (int i = 0; i < NUM_LEDS; i++) {
			leds[i] += CRGB(50, 0, 0);
		}
		draw = false;
	}

	if (soft) {
		for (int i = 0; i < CNT; i++) {
			count[i]++;
			if (count[i] < 0) {
				Serial.printf("WAIT %d\n", pixel[i]);
				/* wait for this sparkle */
				continue;
			}
			if (count[i] == 0) {
				pixel[i] = random(NUM_LEDS);
				continue;
			}
			if (count[i] < 64) {
				Serial.printf("LIGHT UP %d\n", pixel[i]);
				/* slowly light it up */
				leds[pixel[i]].setHSV(170, 255, count[i] * 4);
				continue;
			}
			if (count[i] < 128) {
				Serial.printf("DIM %d\n", pixel[i]);
				/* slowly dim it down */
				leds[pixel[i]].setHSV(170, 255, (127 - count[i]) * 4);
				continue;
			}
			
			Serial.printf("KILL %d\n", pixel[i]);
			/* sparkle gone, schedule next */
			leds[pixel[i]] = 0;
			leds[pixel[i]] = CRGB(50, 0, 0);
			count[i] = random(50) * -1;
		}


	/* !soft */
	} else {
		if ( count[0] == 0 ) {
			pixel[0] = random(NUM_LEDS);
			leds[pixel[0]] = color;
			count[0]++;
			return true;
		}
		if ( count[0] >= 1 ) {
			leds[pixel[0]] = CRGB::Black;
			count[0] = 0;
			return true;
		}
	}
}

/*********************** Effect MeteorRain *************************/
void EffectMeteor::configure(CRGB color) {
    this->color = color;
}

bool EffectMeteor::calcNextFrame() {
    if ( i < NUM_LEDS + NUM_LEDS ) {
        for ( int j = 0; j < NUM_LEDS; j++ ) {
            if ( random(10) > 5 ) {
                leds[j].fadeToBlackBy(64);
            }
        }

        for ( int j = 0; j < 10; j++ ) {
            if (( i-j < NUM_LEDS) && ( i-j >= 0 )) {
                leds[i-j] = CRGB::Green;
            }
        }
        i++;
        delay(30);
        return true;
    } else {
        i = 0;
		fill_solid(leds, NUM_LEDS, CRGB::Black);
        return true;
    }
}

/* Ledding - a fancy LED project */

#include <Arduino.h>
#include <FastLED.h>
#include <config.h>

/* include global instances of leds, animator, buttons, ota and effects */
#include "globals.h"
#include "serial_cmd.h"

void setupMaite() {
	animator.mode = Animator::ANIMATOR_CONSTANT;
}

void setupThias() {
	animator.mode = Animator::ANIMATOR_CONSTANT;
}

#ifdef CONF_PARTYRAUM
void setupPartyraum() {
	/* setup connection to RPi */
    Serial2.begin(115200, SERIAL_8N1, SERIAL_TO_RPI_RXD2, SERIAL_TO_RPI_TXD2);

	/* setup partyraum specifc effects */
	arcEffect.configure(CRGB::Blue, CRGB::Green);
	animator.addEffect(Animator::ANIMATOR_ARC, &arcEffect);
	soundEffect.configure(CRGB::Red);
	animator.addEffect(Animator::ANIMATOR_SOUND, &soundEffect);

	animator.mode = Animator::ANIMATOR_SOUND;

	pinMode(STATUS_LED_1, OUTPUT);
	pinMode(STATUS_LED_2, OUTPUT);
	pinMode(STATUS_LED_3, OUTPUT);
	pinMode(STATUS_LED_4, OUTPUT);

	digitalWrite(STATUS_LED_1, LOW);
	digitalWrite(STATUS_LED_2, LOW);
	digitalWrite(STATUS_LED_3, LOW);
	digitalWrite(STATUS_LED_4, LOW);
}
#endif /* CONF_PARTYRAUM */

void setup() {
	FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(leds, NUM_LEDS);
	FastLED.setBrightness(DEF_GLOBAL_BRIGHTNESS);
	FastLED.setDither();
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    FastLED.show();

	pinMode(BUILTIN_LED, OUTPUT);

#ifdef SERIAL_PRINT
	Serial.begin(115200);
#endif

	/* setup common effects */
	staticEffect.configure(CRGB::DeepPink);
	animator.addEffect(Animator::ANIMATOR_CONSTANT, &staticEffect);
	boltEffect.configure(0, 2, CRGB::Red, 10);
	animator.addEffect(Animator::ANIMATOR_BOLT, &boltEffect);
	strobeEffect.configure(CRGB::White);//, 3, 50, 1000);
	animator.addEffect(Animator::ANIMATOR_STROBE, &strobeEffect);
	sparkleEffect.configure(CRGB::White, true);
	animator.addEffect(Animator::ANIMATOR_SPARKLE, &sparkleEffect);
	meteorEffect.configure(CRGB::Blue);
	animator.addEffect(Animator::ANIMATOR_METEOR, &meteorEffect);

	/* setup specifics for individual installation */
#ifdef CONF_MAITE
	setupMaite();
#elif CONF_THIAS
	setupThias();
#elif CONF_PARTYRAUM
	setupPartyraum();
#endif

#ifdef DEV_MODE
	/* turn on builtin LED */
	digitalWrite(BUILTIN_LED, HIGH);
#endif

	ota.init();
}


void loop() {
	ota.handleOta();

#ifdef CONF_PARTYRAUM
	handleSerialCommands();
#endif

	EVERY_N_MILLISECONDS(REDRAW_RESOLUTION) {
		animator.redraw();
	}

	EVERY_N_MILLISECONDS(BUTTON_CHECK_RES) {
		buttons.handleButtons();
	}
}

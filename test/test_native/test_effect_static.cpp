#include <unity.h>
#include "globals.h"

// --- EffectStatic tests ---

static void test_calcNextFrame_returns_true_when_draw(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	// configure() sets draw = true
	TEST_ASSERT_TRUE(es.calcNextFrame());
}

static void test_calcNextFrame_returns_false_after_draw(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	es.calcNextFrame();  // consumes draw
	TEST_ASSERT_FALSE(es.calcNextFrame());
}

static void test_nextColor_cycles(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	es.calcNextFrame();  // consume initial draw

	es.nextColor();
	TEST_ASSERT_TRUE(es.calcNextFrame());  // draw was set

	// Cycle through all colors and back
	for (int i = 0; i < COLOR_PALETTE_SIZE - 1; i++) {
		es.nextColor();
	}
	// Should be back at original color index
	TEST_ASSERT_TRUE(es.calcNextFrame());
}

static void test_prevColor_cycles(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	es.calcNextFrame();

	es.prevColor();
	TEST_ASSERT_TRUE(es.calcNextFrame());
}

static void test_incIntensity_cycles_submodes(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	es.calcNextFrame();

	// submode starts at 0, cycle: 0 -> 1 -> 2 -> 0
	es.incIntensity();
	TEST_ASSERT_TRUE(es.calcNextFrame());  // draw was set

	es.incIntensity();
	TEST_ASSERT_TRUE(es.calcNextFrame());

	es.incIntensity();  // wraps back to 0
	TEST_ASSERT_TRUE(es.calcNextFrame());
}

static void test_decIntensity_cycles_submodes(void) {
	EffectStatic es;
	es.configure(CRGB::DeepPink);
	es.calcNextFrame();

	// submode 0, decrement wraps to SUBMODE_COUNT - 1 = 2
	es.decIntensity();
	TEST_ASSERT_TRUE(es.calcNextFrame());
}

void run_effect_static_tests(void) {
	RUN_TEST(test_calcNextFrame_returns_true_when_draw);
	RUN_TEST(test_calcNextFrame_returns_false_after_draw);
	RUN_TEST(test_nextColor_cycles);
	RUN_TEST(test_prevColor_cycles);
	RUN_TEST(test_incIntensity_cycles_submodes);
	RUN_TEST(test_decIntensity_cycles_submodes);
}

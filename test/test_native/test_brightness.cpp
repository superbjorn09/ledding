#include <unity.h>
#include "globals.h"

// --- increaseBrightness / decreaseBrightness tests ---

static void test_increase_small_step(void) {
	// brightness < 16: step +1
	FastLED.setBrightness(10);
	increaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(11, FastLED.getBrightness());
}

static void test_increase_medium_step(void) {
	// brightness 16..31: step +2
	FastLED.setBrightness(20);
	increaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(22, FastLED.getBrightness());
}

static void test_increase_large_step(void) {
	// brightness 32..238: step +16
	FastLED.setBrightness(100);
	increaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(116, FastLED.getBrightness());
}

static void test_increase_caps_at_255(void) {
	FastLED.setBrightness(250);
	increaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(255, FastLED.getBrightness());
}

static void test_increase_already_max(void) {
	FastLED.setBrightness(255);
	increaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(255, FastLED.getBrightness());
}

static void test_decrease_large_step(void) {
	// brightness >= 32: step -16
	FastLED.setBrightness(100);
	decreaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(84, FastLED.getBrightness());
}

static void test_decrease_medium_step(void) {
	// brightness 16..31: step -2
	FastLED.setBrightness(20);
	decreaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(18, FastLED.getBrightness());
}

static void test_decrease_small_step(void) {
	// brightness 1..15: step -1
	FastLED.setBrightness(5);
	decreaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(4, FastLED.getBrightness());
}

static void test_decrease_stays_at_zero(void) {
	FastLED.setBrightness(0);
	decreaseBrightness();
	TEST_ASSERT_EQUAL_UINT8(0, FastLED.getBrightness());
}

static void test_increase_decrease_symmetry(void) {
	// From a value in the large-step range, increase then decrease
	// should return to the same value
	FastLED.setBrightness(64);
	increaseBrightness();   // 64 + 16 = 80
	decreaseBrightness();   // 80 - 16 = 64
	TEST_ASSERT_EQUAL_UINT8(64, FastLED.getBrightness());
}

void run_brightness_tests(void) {
	RUN_TEST(test_increase_small_step);
	RUN_TEST(test_increase_medium_step);
	RUN_TEST(test_increase_large_step);
	RUN_TEST(test_increase_caps_at_255);
	RUN_TEST(test_increase_already_max);
	RUN_TEST(test_decrease_large_step);
	RUN_TEST(test_decrease_medium_step);
	RUN_TEST(test_decrease_small_step);
	RUN_TEST(test_decrease_stays_at_zero);
	RUN_TEST(test_increase_decrease_symmetry);
}

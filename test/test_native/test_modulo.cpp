#include <unity.h>
#include "globals.h"

// --- modulo() tests ---

static void test_modulo_positive(void) {
	TEST_ASSERT_EQUAL(2, modulo(7, 5));
}

static void test_modulo_negative_dividend(void) {
	TEST_ASSERT_EQUAL(4, modulo(-1, 5));
	TEST_ASSERT_EQUAL(2, modulo(-3, 5));
}

static void test_modulo_zero(void) {
	TEST_ASSERT_EQUAL(0, modulo(0, 5));
}

static void test_modulo_exact_multiple(void) {
	TEST_ASSERT_EQUAL(0, modulo(10, 5));
	TEST_ASSERT_EQUAL(0, modulo(-10, 5));
}

void run_modulo_tests(void) {
	RUN_TEST(test_modulo_positive);
	RUN_TEST(test_modulo_negative_dividend);
	RUN_TEST(test_modulo_zero);
	RUN_TEST(test_modulo_exact_multiple);
}

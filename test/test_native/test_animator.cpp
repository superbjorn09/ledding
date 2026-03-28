#include <unity.h>
#include "globals.h"

// --- Animator nextMode / prevMode tests ---

static void test_nextMode_skips_nullptr(void) {
	Animator a;
	Effect e1, e2;

	// Register effects at slots 0 and 3 only
	a.addEffect(Animator::ANIMATOR_CONSTANT, &e1);
	a.addEffect(Animator::ANIMATOR_SOUND, &e2);
	a.mode = Animator::ANIMATOR_CONSTANT;

	a.nextMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_SOUND, a.mode);
}

static void test_nextMode_wraps_around(void) {
	Animator a;
	Effect e1, e2;

	a.addEffect(Animator::ANIMATOR_CONSTANT, &e1);
	a.addEffect(Animator::ANIMATOR_BOLT, &e2);
	a.mode = Animator::ANIMATOR_BOLT;

	a.nextMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_CONSTANT, a.mode);
}

static void test_prevMode_wraps_around(void) {
	Animator a;
	Effect e1, e2;

	a.addEffect(Animator::ANIMATOR_CONSTANT, &e1);
	a.addEffect(Animator::ANIMATOR_BOLT, &e2);
	a.mode = Animator::ANIMATOR_CONSTANT;

	a.prevMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_BOLT, a.mode);
}

static void test_prevMode_skips_nullptr(void) {
	Animator a;
	Effect e1, e2;

	// Register at slots 0 and 5
	a.addEffect(Animator::ANIMATOR_CONSTANT, &e1);
	a.addEffect(Animator::ANIMATOR_SPARKLE, &e2);
	a.mode = Animator::ANIMATOR_CONSTANT;

	a.prevMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_SPARKLE, a.mode);
}

static void test_single_effect_stays(void) {
	Animator a;
	Effect e1;

	a.addEffect(Animator::ANIMATOR_ARC, &e1);
	a.mode = Animator::ANIMATOR_ARC;

	a.nextMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_ARC, a.mode);

	a.prevMode();
	TEST_ASSERT_EQUAL(Animator::ANIMATOR_ARC, a.mode);
}

static void test_nextMode_sets_draw(void) {
	Animator a;
	Effect e1, e2;

	a.addEffect(Animator::ANIMATOR_CONSTANT, &e1);
	a.addEffect(Animator::ANIMATOR_BOLT, &e2);
	a.mode = Animator::ANIMATOR_CONSTANT;

	e2.draw = false;
	a.nextMode();
	TEST_ASSERT_TRUE(e2.draw);
}

void run_animator_tests(void) {
	RUN_TEST(test_nextMode_skips_nullptr);
	RUN_TEST(test_nextMode_wraps_around);
	RUN_TEST(test_prevMode_wraps_around);
	RUN_TEST(test_prevMode_skips_nullptr);
	RUN_TEST(test_single_effect_stays);
	RUN_TEST(test_nextMode_sets_draw);
}

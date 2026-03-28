#include <unity.h>

// Test group runners declared in each test file
extern void run_modulo_tests(void);
extern void run_animator_tests(void);
extern void run_effect_static_tests(void);
extern void run_brightness_tests(void);

void setUp(void) {}
void tearDown(void) {}

int main(int argc, char** argv) {
	(void)argc;
	(void)argv;

	UNITY_BEGIN();

	run_modulo_tests();
	run_animator_tests();
	run_effect_static_tests();
	run_brightness_tests();

	return UNITY_END();
}

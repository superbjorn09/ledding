#ifndef BUTTONS_H_BUNPSFAL
#define BUTTONS_H_BUNPSFAL

#include "config.h"

/*! \brief Manage all configured buttons
 *
 * For the touch buttons, we use some special handling due to some false positives
 * i.e. some bogus activations even though the button was not touched:
 * Each button has to be below TOUCH_BUTTON_THRESHOLD in two consecutive readings to be considered activated
 *
 * After activating a button, it has a cooldown of 5 * BUTTON_CHECK_RES
 */
class Buttons {
public:
	explicit Buttons();

	void handleButtons();

private:
	uint8_t buttons[TOUCH_BUTTON_COUNT] = {
		BUTTON_BRT_INC,
		BUTTON_BRT_DEC,
		BUTTON_MODE_NEXT,
		BUTTON_MODE_PREV,
		BUTTON_COLOR_NEXT,
		BUTTON_COLOR_PREV,
		BUTTON_INTENSITY_INC,
		BUTTON_INTENSITY_DEC,
	};

	enum BUTTON_STATE {
		UNPRESSED, /* when button was not pressed at all */
		PREPRESSED,/* first stage of button press, but not considered active yet due to bogus reads */
		PRESSED_0, /* button is considered pressed, related action is executed */
		PRESSED_1, /* button is still pressed but we don't want to toggle so fast, stage 1 */
		PRESSED_2, /* button is still pressed but we don't want to toggle so fast, stage 2 */
	};

	/*! \brief Remember the intermediate buttons states */
	BUTTON_STATE button_states[TOUCH_BUTTON_COUNT] = {UNPRESSED};

	/*! \brief Activate the associated action
	 *
	 * \param button_pin the button define
	 */
	void activate(uint8_t button_pin);
};

#endif /* end of include guard: BUTTONS_H_BUNPSFAL */

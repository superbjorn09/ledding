#ifndef ANIMATOR_H
#define ANIMATOR_H

#include "effect.h"

/*! \brief This class handles the animations on the LED stripes
 *
 * It is responsible for the maintaining the currently active mode and forwards
 * button pressed events to the active effect
 */
class Animator {
public:
	enum AnimatorMode {
		ANIMATOR_CONSTANT,
		ANIMATOR_BOLT,
		ANIMATOR_SERIAL,
	};
	static const int ANIMATOR_MODE_SIZE = 3;

	explicit Animator();

	/*! \brief Calculate next step on the currently active mode */
	void runStateMachine();

	/*! \brief Add the effect for the given mode
	 *
	 * Calling multiple time will replace the old value
	 */
	void addEffect(AnimatorMode mode, Effect* effect);

	/*! \brief Switch to the next AnimatorMode */
	void nextMode();
	/*! \brief Switch to the previous AnimatorMode */
	void prevMode();

	/*! \brief Switch to the next color for the currently active mode */
	void nextColor();
	/*! \brief Switch to the previous color for the currently active mode */
	void prevColor();

	/*! \brief Increase the intensity of the currently active mode */
	void incIntensity();
	/*! \brief Decrease the intensity of the currently active mode */
	void decIntensity();

	/* currently active mode */
	AnimatorMode mode = ANIMATOR_CONSTANT;

private:
	Effect* effects[ANIMATOR_MODE_SIZE] = {nullptr};
	uint16_t idx = 0;
};

#endif /* end of include guard: ANIMATOR_H */

#include "serial_cmd.h"
#include "globals.h"

void handleSerialCommands() {
    if (!Serial2.available())
        return;

    if (Serial2.peek() != CMD_PREFIX)
        return;

    /* consume the prefix byte */
    Serial2.read();

    /* wait briefly for the command byte to arrive */
    unsigned long start = millis();
    while (!Serial2.available()) {
        if (millis() - start > 10)
            return;
    }

    uint8_t cmd = Serial2.read();

    switch (cmd) {
        case CMD_NEXT_MODE:      animator.nextMode();      break;
        case CMD_PREV_MODE:      animator.prevMode();      break;
        case CMD_NEXT_COLOR:     animator.nextColor();     break;
        case CMD_PREV_COLOR:     animator.prevColor();     break;
        case CMD_INC_INTENSITY:  animator.incIntensity();  break;
        case CMD_DEC_INTENSITY:  animator.decIntensity();  break;
        case CMD_INC_BRIGHTNESS: increaseBrightness();     break;
        case CMD_DEC_BRIGHTNESS: decreaseBrightness();     break;
    }
}

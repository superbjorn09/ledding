#ifndef SERIAL_CMD_H
#define SERIAL_CMD_H

#include <Arduino.h>

#define CMD_PREFIX 0xFE

#define CMD_NEXT_MODE       0x01
#define CMD_PREV_MODE       0x02
#define CMD_NEXT_COLOR      0x03
#define CMD_PREV_COLOR      0x04
#define CMD_INC_INTENSITY   0x05
#define CMD_DEC_INTENSITY   0x06
#define CMD_INC_BRIGHTNESS  0x07
#define CMD_DEC_BRIGHTNESS  0x08

/*! \brief Check Serial2 for command prefix (0xFE) and execute commands.
 *
 * Non-blocking: returns immediately if no data or no command prefix.
 * Only consumes the 0xFE prefix + command byte, leaves FFT data untouched.
 */
void handleSerialCommands();

#endif /* SERIAL_CMD_H */

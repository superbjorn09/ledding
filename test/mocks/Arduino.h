#ifndef ARDUINO_H_MOCK
#define ARDUINO_H_MOCK

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

// Arduino constants
#define LOW  0
#define HIGH 1
#define INPUT        0
#define OUTPUT       1
#define INPUT_PULLUP 2

#ifdef __cplusplus

// Serial mock
class SerialMock {
public:
	void begin(long baud) { (void)baud; }
	void printf(const char* fmt, ...) { (void)fmt; }
	void println(const char* s) { (void)s; }
	void println(int v) { (void)v; }
	void println() {}
	int available() { return 0; }
	int read() { return 0; }
	size_t write(uint8_t v) { (void)v; return 1; }
};

extern SerialMock Serial;
extern SerialMock Serial2;

// Arduino functions
inline void delay(unsigned long ms) { (void)ms; }
inline long random(long max) { return max > 0 ? rand() % max : 0; }
inline long random(long min, long max) { return max > min ? min + rand() % (max - min) : min; }
inline unsigned long millis() { return 0; }
inline void pinMode(uint8_t pin, uint8_t mode) { (void)pin; (void)mode; }
inline int digitalRead(uint8_t pin) { (void)pin; return LOW; }
inline int touchRead(uint8_t pin) { (void)pin; return 100; }

#endif /* __cplusplus */

#endif /* ARDUINO_H_MOCK */

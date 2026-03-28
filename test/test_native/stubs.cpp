/**
 * Stubs for symbols needed by the production source files
 * but whose implementations live in excluded translation units
 * (main.cpp, ota.cpp, buttons.cpp).
 */

#include <Arduino.h>
#include <FastLED.h>
#include "buttons.h"
#include "effect.h"

// Global mock instances declared extern in mock headers
SerialMock Serial;
SerialMock Serial2;
CFastLED FastLED;

// Buttons constructor (defined in excluded buttons.cpp)
Buttons::Buttons() {}

// Effect base class virtual (not defined in effect.cpp)
bool Effect::calcNextFrame() { return false; }

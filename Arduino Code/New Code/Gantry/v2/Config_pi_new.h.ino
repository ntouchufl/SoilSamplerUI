#ifndef Config_pi_H
#define Config_pi_H
#include <Arduino.h>
#include <AccelStepper.h>

struct Point { float x; float y; };

#define M1_STEP_PIN 8
#define M1_DIR_PIN 9
#define M1_ENABLE_PIN 15
#define M2_STEP_PIN 12
#define M2_DIR_PIN 13
#define M2_ENABLE_PIN 16
#define X_MIN_PIN 6
#define X_MAX_PIN 7
#define Y_MIN_PIN 3
#define Y_MAX_PIN 4
#define GREEN_LIGHT_PIN 14

#define MIXER_DONE_PIN 17
#define CAMERA_DONE_PIN 18
#define SCOOPER_DONE_PIN 19

// --- GLOBAL MOTION CONSTANTS ---
const float RES = 20.0;
const float MAX_SPD = 10000.0;
const float HOMING_SPD = 1000.0;
const float ACCEL = 7000.0;
const float BRAKE_ACCEL = 7000.0;
const float BACKUP_DIST = 5.0;

// --- SOFT LIMITS (mm from origin at X-MIN/Y-MIN backoff) ---
const float AXIS_X_MAX_MM = 800.0;
const float AXIS_Y_MAX_MM = 1750.0;

// Global State
extern AccelStepper m1, m2;
extern bool isRunning, motorsEnabled;
extern bool emergencyHomingNeeded;  

const int TUBE_COUNT = 40;
const int SAMPLE_COUNT = 40;
const int TOTAL_POINTS = 80;

extern const Point tubeList[TUBE_COUNT];
extern const Point sampleList[SAMPLE_COUNT];

// Prototypes
void executeCmd(String cmd);
void moveGantry(float tx, float ty);
void multiToolSequence(float sampleX, float sampleY);
void physicsHome();
void emergencyHome();
void setMotors(bool on);
void waitForMotors();
void checkLimits();
void globalInterrupt();

#endif
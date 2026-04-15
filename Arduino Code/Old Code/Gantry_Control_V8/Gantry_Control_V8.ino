#include "Config_V8.h"  
AccelStepper m1(AccelStepper::DRIVER, M1_STEP_PIN, M1_DIR_PIN);
AccelStepper m2(AccelStepper::DRIVER, M2_STEP_PIN, M2_DIR_PIN);  
bool isRunning = false, dryRun = false, infiniteLoop = false, monitorActive = false, motorsEnabled = false, manualWaiting = false;
bool emergencyHomingNeeded = false;
bool regularMode = false;
int currentSample = 0;
unsigned long lastDiagTime = 0;
unsigned long sequenceStartTime = 0;
unsigned long pausedTime = 0;

const Point tubeList[TUBE_COUNT] = {
{107.5,100.0},{162.5,100.0},{217.5,100.0},{272.5,100.0},{327.5,100.0},{382.5,100.0},{437.5,100.0},{492.5,100.0},
{107.5,155.0},{162.5,155.0},{217.5,155.0},{272.5,155.0},{327.5,155.0},{382.5,155.0},{437.5,155.0},{492.5,155.0},
{107.5,210.0},{162.5,210.0},{217.5,210.0},{272.5,210.0},{327.5,210.0},{382.5,210.0},{437.5,210.0},{492.5,210.0},
{107.5,265.0},{162.5,265.0},{217.5,265.0},{272.5,265.0},{327.5,265.0},{382.5,265.0},{437.5,265.0},{492.5,265.0},
{107.5,320.0},{162.5,320.0},{217.5,320.0},{272.5,320.0},{327.5,320.0},{382.5,320.0},{437.5,320.0},{492.5,320.0}
};  
const Point sampleList[SAMPLE_COUNT] = {
{50.0,450.0},{105.6,450.0},{161.1,450.0},{216.7,450.0},{272.2,450.0},{327.8,450.0},{383.3,450.0},{438.9,450.0},{494.4,450.0},{550.0,450.0},
{50.0,522.4},{105.6,522.4},{161.1,522.4},{216.7,522.4},{272.2,522.4},{327.8,522.4},{383.3,522.4},{438.9,522.4},{494.4,522.4},{550.0,522.4},
{50.0,594.8},{105.6,594.8},{161.1,594.8},{216.7,594.8},{272.2,594.8},{327.8,594.8},{383.3,594.8},{438.9,594.8},{494.4,594.8},{550.0,594.8},
{50.0,667.2},{105.6,667.2},{161.1,667.2},{216.7,667.2},{272.2,667.2},{327.8,667.2},{383.3,667.2},{438.9,667.2},{494.4,667.2},{550.0,667.2}
};  
void setup() {
Serial.begin(115200);
pinMode(M1_ENABLE_PIN, OUTPUT); pinMode(M2_ENABLE_PIN, OUTPUT);
pinMode(X_MIN_PIN, INPUT_PULLUP); pinMode(X_MAX_PIN, INPUT_PULLUP);
pinMode(Y_MIN_PIN, INPUT_PULLUP); pinMode(Y_MAX_PIN, INPUT_PULLUP);
pinMode(GREEN_LIGHT_PIN, OUTPUT);
pinMode(SAMPLE_READY_PIN, INPUT);
m1.setMaxSpeed(MAX_SPD); m2.setMaxSpeed(MAX_SPD);
m1.setAcceleration(ACCEL); m2.setAcceleration(ACCEL);  
setMotors(false);
printMenu();
}  
void loop() {
handleMenu();

// Handle emergency homing if needed
if (emergencyHomingNeeded) {
Serial.println(F("\n!!! EMERGENCY HOMING TRIGGERED !!!"));
unsigned long emergencyStartTime = millis();
bool wasRunning = isRunning;
int savedSample = currentSample;
bool wasRegularMode = regularMode;
    
emergencyHome();
    
pausedTime += (millis() - emergencyStartTime);
    
emergencyHomingNeeded = false;
    
if (wasRunning) {
isRunning = true;
currentSample = savedSample;
regularMode = wasRegularMode;
Serial.println(F(">> Resuming after emergency homing..."));
}
}

if (isRunning) {
if (!motorsEnabled) { Serial.println(F("!! MOTORS DISABLED !!")); isRunning = false; return; }
    
Point sample = sampleList[currentSample];
Point tube = tubeList[currentSample];
    
// Calculate elapsed time (excluding paused time)
unsigned long elapsedMillis = millis() - sequenceStartTime - pausedTime;
unsigned long elapsedSeconds = elapsedMillis / 1000;
unsigned long hours = elapsedSeconds / 3600;
unsigned long minutes = (elapsedSeconds % 3600) / 60;
unsigned long seconds = elapsedSeconds % 60;
    
// Move to sample first
Serial.print(hours); Serial.print(F("h "));
Serial.print(minutes); Serial.print(F("m "));
Serial.print(seconds); Serial.print(F("s - Sample "));
Serial.println(currentSample + 1);
moveGantry(sample.x, sample.y);
waitForMotors();
if (!isRunning || emergencyHomingNeeded) return;
    
// If in Regular Mode, wait for HIGH signal from Sample Collection System
if (regularMode) {
Serial.println(F(">> Waiting for Sample Collection System signal..."));
unsigned long waitStartTime = millis();
while (digitalRead(SAMPLE_READY_PIN) == LOW && isRunning) {
checkLimits();
// Check for abort
if (Serial.available() > 0) {
if (Serial.peek() == 'Q' || Serial.peek() == 'q') {
Serial.read();
globalInterrupt();
return;
}
}
if (emergencyHomingNeeded) return;
delay(10);
}
pausedTime += (millis() - waitStartTime);
if (!isRunning || emergencyHomingNeeded) return;
Serial.println(F(">> Signal received, proceeding to tube..."));
}
    
// Move to tube second
elapsedMillis = millis() - sequenceStartTime - pausedTime;
elapsedSeconds = elapsedMillis / 1000;
hours = elapsedSeconds / 3600;
minutes = (elapsedSeconds % 3600) / 60;
seconds = elapsedSeconds % 60;
    
Serial.print(hours); Serial.print(F("h "));
Serial.print(minutes); Serial.print(F("m "));
Serial.print(seconds); Serial.print(F("s - Tube "));
Serial.println(currentSample + 1);
moveGantry(tube.x, tube.y);
waitForMotors();
if (!isRunning || emergencyHomingNeeded) return;
    
currentSample++;
if (currentSample >= TUBE_COUNT) {
currentSample = 0;
Serial.println(F(">> CYCLE COMPLETE. Restarting..."));
}
}
}
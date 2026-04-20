#include "Config_pi.h"  
AccelStepper m1(AccelStepper::DRIVER, M1_STEP_PIN, M1_DIR_PIN);
AccelStepper m2(AccelStepper::DRIVER, M2_STEP_PIN, M2_DIR_PIN);
bool isRunning = false, motorsEnabled = false;
bool emergencyHomingNeeded = false;  

//Tool offsets from mixer(mm)
const float MIXER_OFFSET_X = 70.19;
const float MIXER_OFFSET_Y = 48.236;
const float CAMERA_OFFSET_X = -25.0;
const float CAMERA_OFFSET_Y = 5.0;
const float SCOOPER_OFFSET_X = 0.0;
const float SCOOPER_OFFSET_Y = 42.164;

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
  pinMode(M1_ENABLE_PIN, OUTPUT); 
  pinMode(M2_ENABLE_PIN, OUTPUT);
  pinMode(X_MIN_PIN, INPUT_PULLUP); 
  pinMode(X_MAX_PIN, INPUT_PULLUP);
  pinMode(Y_MIN_PIN, INPUT_PULLUP); 
  pinMode(Y_MAX_PIN, INPUT_PULLUP);
  pinMode(GREEN_LIGHT_PIN, OUTPUT);
  
  // Subsystem done signal pins
  //pinMode(MIXER_DONE_PIN, INPUT);
  //pinMode(CAMERA_DONE_PIN, INPUT);
  //pinMode(SCOOPER_DONE_PIN, INPUT);
  
  m1.setMaxSpeed(MAX_SPD); 
  m2.setMaxSpeed(MAX_SPD);
  m1.setAcceleration(ACCEL); 
  m2.setAcceleration(ACCEL);
  setMotors(false);
}  

void loop() {
  while (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    executeCmd(cmd);
  }
}  

void executeCmd(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;  
  
  isRunning = true;
  emergencyHomingNeeded = false;
  
  if (cmd[0] == 'B' || cmd[0] == 'T' || cmd[0] == 'M' || cmd[0] == 'C') {
    int x = cmd[1] - '0';
    int y = cmd[2] - '0';
    int index = getSampleIndex(x, y);
    
    if (index < 0) {
      Serial.println(F("F1")); // INDEX OUT OF RANGE
      isRunning = false;
      return;
    }  
    
    Point target = (cmd[0] == 'B') ? sampleList[index] : tubeList[index];
    unsigned long startTime = millis();
    
    if (cmd[0] == 'B') {
      moveScooperToSample(target.x, target.y);
    } else if (cmd[0] == 'C') {
      moveCameraToSample(target.x, target.y);
    } else if (cmd[0] == 'M') {
      moveMixerToSample(target.x, target.y);
    } else {
      moveScoopToTube(target.x, target.y);
    }
    
    if (emergencyHomingNeeded) {
      Serial.println(F("F2")); // LIMIT HIT
    } else {
      Serial.print(F("Y"));
      Serial.println(millis() - startTime);
    }
    
  } else if (cmd[0] == 'H') {
    unsigned long startTime = millis();
    physicsHome();
    
    if (emergencyHomingNeeded) {
      Serial.println(F("F2"));
    } else {
      Serial.print(F("Y"));
      Serial.println(millis() - startTime);
    }
    
  } else if (cmd[0] == 'Z') {
    m1.setCurrentPosition(0);
    m2.setCurrentPosition(0);
    Serial.println(F("Y0"));
    
  } else if (cmd[0] == 'S') {
    globalInterrupt();
    Serial.println(F("Y0"));
    
  } else if (cmd[0] == 'M') {
    if (cmd[1] == '1') {
      setMotors(true);
      Serial.println(F("Y0"));
    } else {
      setMotors(false);
      Serial.println(F("Y0"));
    }
  } else {
    Serial.println(F("F0")); // UNKNOWN COMMAND
  }  
  
  isRunning = false;
}  


void moveMixerToSample(float sampleX, float sampleY) {
  float mixerX = sampleX - MIXER_OFFSET_X;
  float mixerY = sampleY - MIXER_OFFSET_Y;
  moveGantry(mixerX, mixerY);
}

void moveCameraToSample(float sampleX, float sampleY) {
  float cameraX = sampleX - MIXER_OFFSET_X + CAMERA_OFFSET_X;
  float cameraY = sampleY - MIXER_OFFSET_Y + CAMERA_OFFSET_Y;
  moveGantry(cameraX, cameraY);
}

void moveScooperToSample(float sampleX, float sampleY) {
  float scooperX = sampleX - MIXER_OFFSET_X + SCOOPER_OFFSET_X;
  float scooperY = sampleY - MIXER_OFFSET_Y + SCOOPER_OFFSET_Y;
  moveGantry(scooperX, scooperY);
}
void moveScoopToTube(float tubeX, float tubeY) {
  float scooperX = tubeX - MIXER_OFFSET_X + SCOOPER_OFFSET_X;
  float scooperY = tubeY - MIXER_OFFSET_Y + SCOOPER_OFFSET_Y;
  moveGantry(scooperX, scooperY);
}


void multiToolSequence(float sampleX, float sampleY) {
  // Step 1: Move mixer to sample position
  float mixerX = sampleX - MIXER_OFFSET_X;
  float mixerY = sampleY - MIXER_OFFSET_Y;
  moveGantry(mixerX, mixerY);
  
  if (emergencyHomingNeeded) return;
  
  while (digitalRead(MIXER_DONE_PIN) == LOW) {
    if (!isRunning || emergencyHomingNeeded) return;
    delay(10);
  }
  
  float cameraX = sampleX - MIXER_OFFSET_X + CAMERA_OFFSET_X;
  float cameraY = sampleY - MIXER_OFFSET_Y + CAMERA_OFFSET_Y;
  moveGantry(cameraX, cameraY);
  
  if (emergencyHomingNeeded) return;
  
  while (digitalRead(CAMERA_DONE_PIN) == LOW) {
    if (!isRunning || emergencyHomingNeeded) return;
    delay(10);
  }
  
  float scooperX = sampleX - MIXER_OFFSET_X + SCOOPER_OFFSET_X;
  float scooperY = sampleY - MIXER_OFFSET_Y + SCOOPER_OFFSET_Y;
  moveGantry(scooperX, scooperY);
  
  if (emergencyHomingNeeded) return;
  
  while (digitalRead(SCOOPER_DONE_PIN) == LOW) {
    if (!isRunning || emergencyHomingNeeded) return;
    delay(10);
  }
}

int getSampleIndex(int x, int y) {
  if (x < 0 || x >= 10 || y < 0 || y >= 4) return -1;
  return (y * 10) + x;
}
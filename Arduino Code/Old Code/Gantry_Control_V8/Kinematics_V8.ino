#include "Config_V8.h"  

void moveGantry(float targetX, float targetY) {
  if (targetX < 0.0 || targetX > AXIS_X_MAX_MM || targetY < 0.0 || targetY > AXIS_Y_MAX_MM) {
    Serial.print(F("!! OUT OF BOUNDS: X=")); Serial.print(targetX);
    Serial.print(F(" Y=")); Serial.print(targetY);
    Serial.print(F(" | Limits: X[0-")); Serial.print(AXIS_X_MAX_MM);
    Serial.print(F("] Y[0-")); Serial.print(AXIS_Y_MAX_MM);
    Serial.println(F("]"));
    return;
  }
  long s1 = (targetY + targetX) * RES;
  long s2 = (targetY - targetX) * RES;
  m1.moveTo(s1); m2.moveTo(s2);
}  

void processManual(String coordinates) {
  int commaIndex = coordinates.indexOf(',');
  if (commaIndex > 0) {
    float absX = coordinates.substring(0, commaIndex).toFloat();
    float absY = coordinates.substring(commaIndex + 1).toFloat();
    Serial.print(F("Manual Move to Absolute X:")); Serial.print(absX); Serial.print(F(" Y:")); Serial.println(absY);
    setMotors(true);
    moveGantry(absX, absY);
    waitForMotors();
  }
  manualWaiting = false;
  printMenu();
}  

void physicsHome() {
  setMotors(true);
  m1.setMaxSpeed(HOMING_SPD); m2.setMaxSpeed(HOMING_SPD);
  m1.setAcceleration(ACCEL); m2.setAcceleration(ACCEL);
  long backoffSteps = (long)(BACKUP_DIST * RES);
  
  const float PRECISION_HOMING_SPD = 200.0;
  const float APPROACH_DISTANCE = 100.0;
  
  auto checkAbort = []() {
    if (Serial.available() > 0) { char c = Serial.peek(); if(c=='Q'||c=='q') { globalInterrupt(); Serial.read(); return true; } }
    return false;
  };  
  
  // 1. X-MIN
  Serial.println(F("Homing: X-MIN..."));
  while (digitalRead(X_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-HOMING_SPD); m2.setSpeed(HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  m1.move(backoffSteps); m2.move(-backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long xminBackoff_s1 = m1.currentPosition();
  long xminBackoff_s2 = m2.currentPosition();
  Serial.println(F(">> X-MIN backed off."));  
  
  // 2. X-MAX
  Serial.println(F("Homing: X-MAX (survey)..."));
  while (digitalRead(X_MAX_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(HOMING_SPD); m2.setSpeed(-HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  m1.move(-backoffSteps); m2.move(backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  Serial.println(F(">> X-MAX backed off."));  
  
  // 3. Y-MIN
  Serial.println(F("Homing: Y-MIN..."));
  while (digitalRead(Y_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-HOMING_SPD); m2.setSpeed(-HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  m1.move(backoffSteps); m2.move(backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long yminBackoff_s1 = m1.currentPosition();
  long yminBackoff_s2 = m2.currentPosition();
  Serial.println(F(">> Y-MIN backed off."));  
  
  // 4. Y-MAX
  Serial.println(F("Homing: Y-MAX (survey)..."));
  while (digitalRead(Y_MAX_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(HOMING_SPD); m2.setSpeed(HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  m1.move(-backoffSteps); m2.move(-backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  Serial.println(F(">> Y-MAX backed off."));  
  
  // Calculate approximate origin
  long s1_origin = ((yminBackoff_s1 + yminBackoff_s2) + (xminBackoff_s1 - xminBackoff_s2)) / 2;
  long s2_origin = ((yminBackoff_s1 + yminBackoff_s2) - (xminBackoff_s1 - xminBackoff_s2)) / 2;  
  
  // FAST APPROACH TO 100mm FROM ORIGIN
  Serial.println(F("Fast approach to 100mm from origin..."));
  
  float approachX = APPROACH_DISTANCE;
  float approachY = APPROACH_DISTANCE;
  long s1_approach = (long)((approachY + approachX) * RES) + s1_origin;
  long s2_approach = (long)((approachY - approachX) * RES) + s2_origin;
  
  m1.setMaxSpeed(MAX_SPD); m2.setMaxSpeed(MAX_SPD);
  m1.setAcceleration(ACCEL); m2.setAcceleration(ACCEL);
  m1.moveTo(s1_approach); m2.moveTo(s2_approach);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); m2.run();
  }
  Serial.println(F(">> Fast approach complete."));
  
  // PRECISION PASS
  Serial.println(F(">> Starting slow precision approach..."));
  m1.setMaxSpeed(PRECISION_HOMING_SPD); m2.setMaxSpeed(PRECISION_HOMING_SPD);
  
  // Precision X-MIN
  Serial.println(F("Precision X-MIN..."));
  while (digitalRead(X_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-PRECISION_HOMING_SPD); m2.setSpeed(PRECISION_HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  long precisionBackoff = (long)(1.0 * RES);
  m1.move(precisionBackoff); m2.move(-precisionBackoff);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long xmin_precise_s1 = m1.currentPosition();
  long xmin_precise_s2 = m2.currentPosition();
  Serial.println(F(">> Precision X-MIN complete."));
  
  // Precision Y-MIN
  Serial.println(F("Precision Y-MIN..."));
  while (digitalRead(Y_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-PRECISION_HOMING_SPD); m2.setSpeed(-PRECISION_HOMING_SPD);
    m1.runSpeed(); m2.runSpeed();
  }
  m1.move(precisionBackoff); m2.move(precisionBackoff);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long ymin_precise_s1 = m1.currentPosition();
  long ymin_precise_s2 = m2.currentPosition();
  Serial.println(F(">> Precision Y-MIN complete."));
  
  // Calculate precise origin
  long s1_precise_origin = ((ymin_precise_s1 + ymin_precise_s2) + (xmin_precise_s1 - xmin_precise_s2)) / 2;
  long s2_precise_origin = ((ymin_precise_s1 + ymin_precise_s2) - (xmin_precise_s1 - xmin_precise_s2)) / 2;
  
  Serial.println(F("Moving to precise 0,0..."));
  m1.moveTo(s1_precise_origin); m2.moveTo(s2_precise_origin);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); m2.run();
  }
  
  m1.setCurrentPosition(0); m2.setCurrentPosition(0);
  Serial.println(F(">> PRECISE ORIGIN SET: (0,0)"));
  
  m1.setMaxSpeed(MAX_SPD); m2.setMaxSpeed(MAX_SPD);
  
  Serial.println(F("Moving to safe position (5,5)..."));
  moveGantry(5.0, 5.0);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); m2.run();
  }
  
  Serial.println(F(">> Homing Complete. Positioned at (5,5)."));
  printMenu();
}

void emergencyHome() {
  physicsHome();
}

void globalInterrupt() {
  isRunning = false; manualWaiting = false;
  m1.setAcceleration(BRAKE_ACCEL); m2.setAcceleration(BRAKE_ACCEL);
  m1.stop(); m2.stop();
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    m1.run(); m2.run();
  }
  m1.setAcceleration(ACCEL); m2.setAcceleration(ACCEL);
  Serial.println(F("\n!!! ABORT !!!"));
  printMenu();
}  

void checkLimits() {
  if (digitalRead(X_MIN_PIN) == 0 || digitalRead(X_MAX_PIN) == 0 ||
      digitalRead(Y_MIN_PIN) == 0 || digitalRead(Y_MAX_PIN) == 0) {
    m1.setAcceleration(BRAKE_ACCEL); m2.setAcceleration(BRAKE_ACCEL);
    m1.stop(); m2.stop();
    while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) { m1.run(); m2.run(); }
    m1.setAcceleration(ACCEL); m2.setAcceleration(ACCEL);
    
    Serial.println(F("!! LIMIT HIT - EMERGENCY HOMING REQUIRED !!"));
    emergencyHomingNeeded = true;
  }
}

void fastBinaryDiag() {
  Serial.print(F("Xmin:")); Serial.print(digitalRead(X_MIN_PIN));
  Serial.print(F(" Xmax:")); Serial.print(digitalRead(X_MAX_PIN));
  Serial.print(F(" Ymin:")); Serial.print(digitalRead(Y_MIN_PIN));
  Serial.print(F(" Ymax:")); Serial.print(digitalRead(Y_MAX_PIN));
  Serial.print(F(" | s1:")); Serial.print(m1.currentPosition());
  Serial.print(F(" s2:")); Serial.println(m2.currentPosition());
}  

void setMotors(bool on) {
  motorsEnabled = on;
  digitalWrite(M1_ENABLE_PIN, !on); digitalWrite(M2_ENABLE_PIN, !on);
  Serial.print(F("MOTOR POWER: ")); Serial.println(on ? F("ON") : F("OFF"));
}  

void waitForMotors() {
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    m1.run(); m2.run();
    checkLimits();
    if (Serial.available() > 0) {
      if (Serial.peek() == 'Q' || Serial.peek() == 'q') {
        Serial.read();
        globalInterrupt();
        break;
      }
    }
    if (!isRunning && !manualWaiting) break;
    if (emergencyHomingNeeded) break;
  }
}
#include "Config_pi.h"  

void moveGantry(float targetX, float targetY) {
  long s1 = (targetY + targetX) * RES;
  long s2 = (targetY - targetX) * RES;
  m1.moveTo(s1); 
  m2.moveTo(s2);
  waitForMotors();
}  

void physicsHome() {
  setMotors(true);
  m1.setMaxSpeed(HOMING_SPD); 
  m2.setMaxSpeed(HOMING_SPD);
  m1.setAcceleration(ACCEL); 
  m2.setAcceleration(ACCEL);
  long backoffSteps = (long)(BACKUP_DIST * RES);  
  
  const float PRECISION_HOMING_SPD = 200.0;
  const float APPROACH_DISTANCE = 100.0;  
  
  auto checkAbort = []() {
    if (Serial.available() > 0) { 
      char c = Serial.peek(); 
      if(c=='Q'||c=='q') { 
        globalInterrupt(); 
        Serial.read(); 
        return true; 
      } 
    }
    return false;
  };  
  
  while (digitalRead(X_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-HOMING_SPD); 
    m2.setSpeed(HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  m1.move(backoffSteps); 
  m2.move(-backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long xminBackoff_s1 = m1.currentPosition();
  long xminBackoff_s2 = m2.currentPosition();  
  
  while (digitalRead(X_MAX_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(HOMING_SPD); 
    m2.setSpeed(-HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  m1.move(-backoffSteps); 
  m2.move(backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }  
  
  while (digitalRead(Y_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-HOMING_SPD); 
    m2.setSpeed(-HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  m1.move(backoffSteps); 
  m2.move(backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long yminBackoff_s1 = m1.currentPosition();
  long yminBackoff_s2 = m2.currentPosition();  
  
  while (digitalRead(Y_MAX_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(HOMING_SPD); 
    m2.setSpeed(HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  m1.move(-backoffSteps); 
  m2.move(-backoffSteps);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }  
  
  // Calculate approximate origin
  long s1_origin = ((yminBackoff_s1 + yminBackoff_s2) + (xminBackoff_s1 - xminBackoff_s2)) / 2;
  long s2_origin = ((yminBackoff_s1 + yminBackoff_s2) - (xminBackoff_s1 - xminBackoff_s2)) / 2;  
  
  float approachX = APPROACH_DISTANCE;
  float approachY = APPROACH_DISTANCE;
  long s1_approach = (long)((approachY + approachX) * RES) + s1_origin;
  long s2_approach = (long)((approachY - approachX) * RES) + s2_origin;  
  
  m1.setMaxSpeed(MAX_SPD); 
  m2.setMaxSpeed(MAX_SPD);
  m1.setAcceleration(ACCEL); 
  m2.setAcceleration(ACCEL);
  m1.moveTo(s1_approach); 
  m2.moveTo(s2_approach);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); 
    m2.run();
  }  
  
  // PRECISION PASS
  m1.setMaxSpeed(PRECISION_HOMING_SPD); 
  m2.setMaxSpeed(PRECISION_HOMING_SPD);  
  
  while (digitalRead(X_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-PRECISION_HOMING_SPD); 
    m2.setSpeed(PRECISION_HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  long precisionBackoff = (long)(1.0 * RES);
  m1.move(precisionBackoff); 
  m2.move(-precisionBackoff);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long xmin_precise_s1 = m1.currentPosition();
  long xmin_precise_s2 = m2.currentPosition();  
  
  while (digitalRead(Y_MIN_PIN) == HIGH) {
    if (checkAbort()) return;
    m1.setSpeed(-PRECISION_HOMING_SPD); 
    m2.setSpeed(-PRECISION_HOMING_SPD);
    m1.runSpeed(); 
    m2.runSpeed();
  }
  m1.move(precisionBackoff); 
  m2.move(precisionBackoff);
  while (m1.distanceToGo() != 0) { m1.run(); m2.run(); }
  long ymin_precise_s1 = m1.currentPosition();
  long ymin_precise_s2 = m2.currentPosition();  
  
  // Calculate precise origin
  long s1_precise_origin = ((ymin_precise_s1 + ymin_precise_s2) + (xmin_precise_s1 - xmin_precise_s2)) / 2;
  long s2_precise_origin = ((ymin_precise_s1 + ymin_precise_s2) - (xmin_precise_s1 - xmin_precise_s2)) / 2;  
  
  m1.moveTo(s1_precise_origin); 
  m2.moveTo(s2_precise_origin);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); 
    m2.run();
  }  
  
  m1.setCurrentPosition(0); 
  m2.setCurrentPosition(0);
  m1.setMaxSpeed(MAX_SPD);  
  
  moveGantry(5.0, 5.0);
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    if (checkAbort()) return;
    m1.run(); 
    m2.run();
  }
}  

void emergencyHome() {
  physicsHome();
}  

void globalInterrupt() {
  isRunning = false;
  m1.setAcceleration(BRAKE_ACCEL); 
  m2.setAcceleration(BRAKE_ACCEL);
  m1.stop(); 
  m2.stop();
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    m1.run(); 
    m2.run();
  }
  m1.setAcceleration(ACCEL); 
  m2.setAcceleration(ACCEL);
}  

void checkLimits() {
  if (digitalRead(X_MIN_PIN) == 0 || digitalRead(X_MAX_PIN) == 0 ||
      digitalRead(Y_MIN_PIN) == 0 || digitalRead(Y_MAX_PIN) == 0) {
    m1.setAcceleration(BRAKE_ACCEL); 
    m2.setAcceleration(BRAKE_ACCEL);
    m1.stop(); 
    m2.stop();
    while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) { 
      m1.run(); 
      m2.run(); 
    }
    m1.setAcceleration(ACCEL); 
    m2.setAcceleration(ACCEL);  
    
    emergencyHomingNeeded = true;
  }
}  

void setMotors(bool on) {
  motorsEnabled = on;
  digitalWrite(M1_ENABLE_PIN, !on); 
  digitalWrite(M2_ENABLE_PIN, !on);
}  

void waitForMotors() {
  while (m1.distanceToGo() != 0 || m2.distanceToGo() != 0) {
    m1.run(); 
    m2.run();
    checkLimits();
    
    if (Serial.available() > 0) {
      if (Serial.peek() == 'Q' || Serial.peek() == 'q') {
        Serial.read();
        globalInterrupt();
        break;
      }
    }
    
    if (!isRunning) break;
    if (emergencyHomingNeeded) break;
  }
}
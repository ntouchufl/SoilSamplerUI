// include the Servo library
#include <Servo.h>
#include <AccelStepper.h>

String command; 

//create servo objects
Servo servoFlip;  
Servo servoScoop;
Servo servoDispense;

//Stepper Initializations (Stirrer)
const int stepPin = 3; 
const int dirPin = 2; 
AccelStepper myStepper(AccelStepper::DRIVER, stepPin, dirPin); 

//pin setup for stepper steps
const int m1Pin = 7; 
const int m2Pin = 6;

void setup() {
  servoFlip.write(2550);
  servoScoop.write(2550);
  servoDispense.write(1500);

  servoFlip.attach(8, 450, 2550);  
  servoScoop.attach(9, 450, 2550);
  servoDispense.attach(10);

  pinMode(m1Pin, OUTPUT); 
  pinMode(m2Pin, OUTPUT);

  digitalWrite(m1Pin, HIGH);
  digitalWrite(m2Pin, LOW);

  myStepper.setMaxSpeed(1000);
  myStepper.setSpeed(500);

  Serial.begin(9600);  
}

void scoop(){
  if (servoScoop.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
      servoScoop.writeMicroseconds(pos);                 
      delay(1);
    }
  }
  else {
   for (int pos = 2550; pos >= 450; pos--) { 
      servoScoop.writeMicroseconds(pos);                 
      delay(1);
   }
  }
}

void flip(){
  if (servoFlip.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
      servoFlip.writeMicroseconds(pos);                 
      delayMicroseconds(100);
    }
  }
  else {
   for (int pos = 2550; pos >= 450; pos--) { 
      servoFlip.writeMicroseconds(pos);                 
      delayMicroseconds(100);
   }
  }
}

void dispense(){
  servoDispense.writeMicroseconds(1500);
  delay(250);
  servoDispense.writeMicroseconds(500);
}

void loop() {
  if (Serial.available()){
    command = Serial.readStringUntil('\n');
    command.trim();
    
    unsigned long startTime = millis();
    bool valid = true;

    if(command == "S"){
      scoop();
    }
    else if(command == "F"){
      flip();
    }
    else if(command == "D"){
      dispense();
    }
    else if(command == "START"){
      myStepper.setSpeed(500);
      // Continuous run handled in loop or just pulse here?
      // For simplicity in this structure, we'll just return success.
    }
    else if(command == "STOP"){
      myStepper.setSpeed(0);
    }
    else{
      valid = false;
    }

    if (valid) {
      Serial.print("Y");
      Serial.println(millis() - startTime);
    } else {
      Serial.println("F0");
    }
  }
  
  // Keep the stirrer running if speed is set
  myStepper.runSpeed();
}

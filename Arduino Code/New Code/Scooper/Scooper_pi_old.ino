// include the Servo library
#include <Servo.h>
#include <AccelStepper.h>

String command; //will store user input command

//create servo objects
Servo servoFlip;  
Servo servoScoop;
Servo servoDispense;

//Stepper Initializations 
const int stepPin = 3; //step is plugged into pin 3
const int dirPin = 2; //dir is plugged into pin 2
AccelStepper myStepper(AccelStepper::DRIVER, stepPin, dirPin); //create stepper object

//pin setup for stepper steps
const int m1Pin = 7; 
const int m2Pin = 6;

void setup() {
    servoFlip.write(2550);
  servoScoop.write(2550);
  servoDispense.write(1500);

  servoFlip.attach(8, 450, 2550);  //tell arduino to control the servo through pin 4
  servoScoop.attach(9, 450, 2550);
  servoDispense.attach(10);

  //Tell the arduino mega to send to these pins
  pinMode(m1Pin, OUTPUT); 
  pinMode(m2Pin, OUTPUT);

  //ms0-low, ms1-high, and ms2-low will tell the nema 17 stepper to quarter step
  digitalWrite(m1Pin, HIGH);
  digitalWrite(m2Pin, LOW);

  myStepper.setMaxSpeed(1000);
  myStepper.setSpeed(500);
  //myStepper.setAcceleration(200);

  Serial.begin(9600);  // open a serial connection
  delay(2000);
}

void loop() {
    if (Serial.available()){
    command = Serial.readStringUntil('\n');
    command.trim(); //deletes surrounding whitespace from command
    if(command[0] == 'S'){
      scoop();
    }
    else if(command[0] == 'F'){
      flip();
    }
    else if(command[0] == 'D'){
      dispense();
    }
    else if (command[0] == 'Q') {
        // Stop the stepper motor immediately
        myStepper.stop();
    }
}

void scoop(){
  //Serial.println(servoScoop.read());
  if (servoScoop.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
    servoScoop.writeMicroseconds(pos);                 
    delay(1);
    Serial.println("Y");
    }
  }
  else {
    //delay(1000);
   for (int pos = 2550; pos >= 450; pos--) { 
    servoScoop.writeMicroseconds(pos);                 
    delay(1);
    Serial.println("Y");
   }
  }
}

void flip(){
  //Serial.println(servoFlip.read());
  if (servoFlip.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
    servoFlip.writeMicroseconds(pos);                 
    delayMicroseconds(100);
    Serial.println("Y");
    }
  }
  else {
    //delay(1000);
   for (int pos = 2550; pos >= 450; pos--) { 
    servoFlip.writeMicroseconds(pos);                 
    delayMicroseconds(100);
    Serial.println("Y");
   }
  }
}

void dispense(){
  //Serial.println(servoDispense.read());
  if (servoDispense.read() == 0){
    /*for (int pos = 500; pos <= 1500; pos++) { 
    servoDispense.writeMicroseconds(pos);                 
    delayMicroseconds(100);
    }*/
    servoDispense.writeMicroseconds(1500);
    delay(250);
    servoDispense.writeMicroseconds(500);
  }
  else {
    //delay(1000);
   /*for (int pos = 1500; pos >= 500; pos--) { 
    servoDispense.writeMicroseconds(pos);                 
    delayMicroseconds(100);
   }*/
   servoDispense.writeMicroseconds(500);
  }
  Serial.println("Y");
}

void estop() {
    Serial.println("E");
}

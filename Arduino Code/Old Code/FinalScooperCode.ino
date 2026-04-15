// include the Servo library
#include <Servo.h>
#include <AccelStepper.h>

String command; //will store user input command

//buttons setup
const int scoopButtonPin = 4;
const int stepperButtonPin = 5;
const int flipButtonPin = 11;
const int dispenseButtonPin = 12;

int scoopButtonState = 0;
int flipButtonState = 0;
int dispenseButtonState = 0;
int stepperButtonState = 0;

bool direction = true;     // true = one direction, false = opposite

int lastButtonState = 0;

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
  pinMode(scoopButtonPin, INPUT);
  pinMode(stepperButtonPin, INPUT);
  pinMode(flipButtonPin, INPUT);
  pinMode(dispenseButtonPin, INPUT);

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

  Serial.println("Type Command (scoopSoil, dispenseIntoTestVessel, emptyScoop)");
}

void scoop(){
  //Serial.println(servoScoop.read());
  if (servoScoop.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
    servoScoop.writeMicroseconds(pos);                 
    delay(1);
    }
  }
  else {
    //delay(1000);
   for (int pos = 2550; pos >= 450; pos--) { 
    servoScoop.writeMicroseconds(pos);                 
    delay(1);
   }
  }
}

void flip(){
  //Serial.println(servoFlip.read());
  if (servoFlip.read() == 0){
    for (int pos = 450; pos <= 2550; pos++) { 
    servoFlip.writeMicroseconds(pos);                 
    delayMicroseconds(100);
    }
  }
  else {
    //delay(1000);
   for (int pos = 2550; pos >= 450; pos--) { 
    servoFlip.writeMicroseconds(pos);                 
    delayMicroseconds(100);
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
}

void loop() {
  if (Serial.available()){
    command = Serial.readStringUntil('\n');
    command.trim(); //deletes surrounding whitespace from command
    if(command == "scoopSoil"){
      scoop();
    }
    else if(command == "dispenseIntoTestVessel"){
      flip();
    }
    else if(command == "emptyScoop"){
      scoop();
    }
    else{
      command = "Incorrect Input: " + command; 
    }
    Serial.print("Command: ");
    Serial.println(command);
  }
}
 
void handleButtonPress() {
  direction = !direction;

  if (direction) {
    myStepper.setSpeed(500);
  } else {
    myStepper.setSpeed(-500);
  }
}

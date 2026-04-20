// include the Servo library
#include <Servo.h>
#include <AccelStepper.h>
#include "HX711.h"
#include <ezButton.h>
HX711 loadcellL;
HX711 loadcellR;

String command; //will store user input command

//buttons setup
const int scoopButtonPin = 4;
const int stepperButtonPin = 5;
const int flipButtonPin = 11;
const int dispenseButtonPin = 12;

ezButton limitSwitch(43);

bool direction = true;     // true = one direction, false = opposite

//create servo objects
Servo servoFlip;  
Servo servoScoop;
Servo servoDispense;

//Stepper Initializations 
const int stepPin = 3; //step is plugged into pin 3
const int dirPin = 2; //dir is plugged into pin 2
const int MAX_STEPS = 1400; // 100mm of travel w/pitch 1mm and 200 steps/rev, 1400 ish
const int MOTOR_DIR = -1;  // Sign convention is - speed is down in code. This flips it
AccelStepper stepper(AccelStepper::DRIVER, stepPin, dirPin); //create stepper object

//pin setup for stepper steps
const int m1Pin = 7; 
const int m2Pin = 6;

// 1. HX711 circuit wiring
const int LOADCELLR_DOUT_PIN = 33;
const int LOADCELLR_SCK_PIN = 35;

// 1. HX711 circuit wiring
const int LOADCELLL_DOUT_PIN = 23;
const int LOADCELLL_SCK_PIN = 25;

// 2. Adjustment settings
const long LOADCELL_OFFSET_L = 511636.00;
const long LOADCELL_DIVIDER_L = 420.480468;

const long LOADCELL_OFFSET_R = 444267.00;
const long LOADCELL_DIVIDER_R = -300.048706;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  limitSwitch.setDebounceTime(50);

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

  stepper.setMaxSpeed(1000);
  stepper.setSpeed(500);
  //myStepper.setAcceleration(200);

  loadcellR.begin(LOADCELLR_DOUT_PIN, LOADCELLR_SCK_PIN);
  loadcellR.set_scale(LOADCELL_DIVIDER_R);
  loadcellR.set_offset(LOADCELL_OFFSET_R);
  loadcellR.tare();

  loadcellL.begin(LOADCELLL_DOUT_PIN, LOADCELLL_SCK_PIN);
  loadcellL.set_scale(LOADCELL_DIVIDER_L);
  loadcellL.set_offset(LOADCELL_OFFSET_L);
  loadcellL.tare();

  Serial.begin(115200);  // open a serial connection
  delay(1000);

  Serial.println("Type Command (scoopSoil, dispenseIntoTestVessel, emptyScoop)");
}

void loop() {
  if (Serial.available()){
    command = Serial.readStringUntil('\n');
    command.trim(); //deletes surrounding whitespace from command
    if(command[0] == 'S'){
      digitalWrite(LED_BUILTIN, HIGH);
      scoop();
    }
    else if(command[0] == 'D'){
      digitalWrite(LED_BUILTIN, HIGH);
      String weightString = command.substring(1,3);
      float weight = weightString.toFloat();
      dispense(weight);
    }
    else if(command[0] == 'E'){
      digitalWrite(LED_BUILTIN, HIGH);
      empty();
    }
    else if (command[0] == 'Q') {
      digitalWrite(LED_BUILTIN, HIGH);
        // Stop the stepper motor immediately
      stepper.stop();
    }
    digitalWrite(LED_BUILTIN, LOW);
  }
}

void zeroActuator() {
  // First, move away from limit switch if it's already pressed
  stepper.setCurrentPosition(0);
  stepper.setSpeed(500 * MOTOR_DIR); // Move in reverse direction
  unsigned long timeout = millis() + 5000; // 5 second timeout
  while (limitSwitch.getState() == HIGH && millis() < timeout) {
    limitSwitch.loop();
    stepper.runSpeed();
  }
  stepper.setSpeed(0);
  stepper.stop(); // Ensure motor stops
  delay(100); // Brief pause
  
  // Move forward until limit switch is pressed
  stepper.setSpeed(-400 * MOTOR_DIR); // Set the speed (positive for one direction)
  timeout = millis() + 60000; // 60 second timeout for safety
  while (limitSwitch.getState() == LOW && millis() < timeout) {
    limitSwitch.loop();
    stepper.runSpeed(); // Run at constant speed
  }
  
  // Stop the motor immediately when limit switch is hit
  stepper.setSpeed(0);
  stepper.stop(); // Ensure motor stops
  stepper.setCurrentPosition(0); // Zero position
  return;
}

void resetAll() {
  servoFlip.write(2550);
  servoScoop.write(2550);
  servoDispense.write(1500);
  delay(2000);
  zeroActuator(); //calibrates the position of the scoop through the stepper
  delay(1000);
  loadcellR.tare();
  loadcellL.tare();
  return;
}

void scoop(){
  //calls helper function to reset all motors
  resetAll();
  
  //Flip hopper and open scoop in same motion
  for (int pos = 450; pos <= 2550; pos++) {
    servoFlip.writeMicroseconds(pos);
    servoScoop.writeMicroseconds(pos);
    delay(1);
  }
  delay(2000);

  // Drive stepper motor downward until the one load cell experiences 50g or max steps hit
  stepper.setSpeed(500 * MOTOR_DIR);
  while (stepper.currentPosition() < MAX_STEPS and abs((loadcellL.get_units(10) + loadcellR.get_units(10)) / 2) < 50) {
    stepper.setSpeed(1000 * MOTOR_DIR);
    stepper.run();
  }
  //For albert: check if stopping/starting stepper gives loadcell readings > 50
  stepper.stop(); // Ensure motor stops
  //send out error if bag empty (if loadcells don't detect impact with soil)
  if (abs((loadcellL.get_units(10) + loadcellR.get_units(10)) / 2) < 50){
    Serial.println("E"); 
  }
  delay(2000);

   // Scoop the soil
   for (int pos = 450; pos <= 2550; pos++) {
    servoScoop.writeMicroseconds(pos);
    delay(1);
  }

  // Moves hopper out of bag and flips it over
  zeroActuator();
  delay(1000);
  for (int pos = 450; pos <= 2550; pos++) {
    servoFlip.writeMicroseconds(pos);
    delay(1);
  }
  delay(2000);
  Serial.println("Y");
}

void dispense(float soilWeight){
  const float startWeight = abs((loadcellL.get_units(10) + loadcellR.get_units(10)) / 2);
  //startWeight is the calculated weight before any dispensing begins
  //soilWeight is the target soil weight to be deposited
  while(true){
    float averageWeight = abs((loadcellL.get_units(10) + loadcellR.get_units(10)) / 2); //calculate current weight
    if(abs(startWeight - averageWeight - soilWeight) < 0.05 * soilWeight){ // if the dispensed weight is within 5%, stop dispensing
      break;
    }
    //open dispenser for various lengths of time depending on how much soil needs depositing
    if (abs(startWeight - averageWeight - soilWeight) > 6.5){
      servoDispense.writeMicroseconds(1500);
      delay(500);
      servoDispense.writeMicroseconds(500);
    }
    else if (abs(startWeight - averageWeight - soilWeight) > 3){
      servoDispense.writeMicroseconds(1500);
      delay(200);
      servoDispense.writeMicroseconds(500);
    }
    else{
      servoDispense.writeMicroseconds(1500);
      delay(100);
      servoDispense.writeMicroseconds(500);
    }
    delay(50); //lets vibrations die out to get more accurate loadcell readings
  }
  Serial.println("Y");
}

void empty(){
//open dispenser for 3 seconds
    servoDispense.writeMicroseconds(1500);
    delay(3000);
    servoDispense.writeMicroseconds(500);
    Serial.println("Y");
}
 
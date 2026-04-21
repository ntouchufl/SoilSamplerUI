const int STBY = 8;
const int AIN1 = 4;
const int AIN2 = 12;
const int PWMA = 6;
 
const int ENC_C1 = 2;
const int ENC_C2 = 10;
 
volatile long globalEncoderCount = 0;
long lead = 2700;
 
bool motorRunning = false;
 
long lastEncoderCount = 0;
unsigned long lastMotionTime = 0;
 
const unsigned long stallTimeout = 250; // ms
unsigned long lastCheck = 0;
 
const bool down = true;
const int buffer = 300;
 
// -----------------------------------------------
void setup() {
  Serial.begin(115200); // Bumped to 115200 to match Gantry/Standard speeds
 
  pinMode(STBY, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMA, OUTPUT);
  pinMode(ENC_C1, INPUT_PULLUP);
  pinMode(ENC_C2, INPUT_PULLUP);
 
  attachInterrupt(digitalPinToInterrupt(ENC_C1), countEncoder, RISING);
 
  digitalWrite(STBY, HIGH);
}
 
void loop(){
  // Handle serial commands
  if (Serial.available()) {
    char cmd = Serial.read();
 
    switch (cmd) {
      case 'm':
      case 'C': // Added 'C' standard calibrate command
        lead = manualCalibrate(true);
        break;
     
      case 'd':
        driveDistance(down, lead);
        Serial.println("Y0"); // Acknowledge debug commands
        break;
     
      case 'u':
        driveDistance(!down, lead);
        Serial.println("Y0");
        break;
 
      case 'S': // Standard system Stir command
      case ' ': // Kept spacebar for manual debug
        stir();
        break;
 
      // Ignore newline/carriage return noise
      case '\n':
      case '\r':
        break;
 
      default:
        Serial.println("F0"); // Unknown command standard
        break;
    }
  }
}
 
void countEncoder() {
  if (digitalRead(ENC_C2) == HIGH) {
    globalEncoderCount++;
  } else {
    globalEncoderCount--;
  }
}
 
void drive(bool forward) {
  digitalWrite(STBY, HIGH);
  digitalWrite(AIN1, forward ? HIGH : LOW);
  digitalWrite(AIN2, forward ? LOW  : HIGH);
  analogWrite(PWMA, 255);
  motorRunning = true;
  lastEncoderCount = globalEncoderCount;
  lastCheck = millis();
}
 
void stopMotor() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  analogWrite(PWMA, 0);
  motorRunning = false;
}
 
bool checkStall() {
  if (!motorRunning) return false;
 
  long currentCount = globalEncoderCount;
 
  // If encoder changed → reset timer
  if (currentCount != lastEncoderCount) {
    lastEncoderCount = currentCount;
    lastCheck = millis();   // reset "last movement time"
    return false;
  }
 
  // If no movement for too long → stall
  if (millis() - lastCheck > stallTimeout) {
    stopMotor();
    return true;
  }
 
  return false;
}
 
int manualCalibrate(bool dir){
  Serial.println("-----Starting Calibration-----");
  Serial.println("Spin to top zero and click space");
  bool start = true;
  bool top = true;
  long encoderLength=0;
  
  while (start){
    if (Serial.available()) {
      char cmd = Serial.read();
      switch (cmd) {
        case ' ':
          if (top){
            globalEncoderCount = 0;
            Serial.println("Reached Top");
            Serial.println("Begin precessing down screw");
            top = false;
            delay(500);
          }
          else{
            Serial.println("Reached bottom");
            encoderLength = globalEncoderCount;
            Serial.print("Encoder Length: "); Serial.println(abs(encoderLength));
            delay(500);
            start = false;
          }
          break;
         
        case 's':
          Serial.println("-----Calibration Stopped-----");
          encoderLength = 0;
          start = !start;
          delay(500);
          break;
      }
    }
  }
  delay(1000);
  driveDistance(!down, abs(encoderLength));
  Serial.println("Y0"); // Acknowledge calibration finished to UI
  return abs(encoderLength);
}
 
// FIXED: Ensures return value is always positive absolute distance
int driveDistance(bool dir, int length){
  drive(dir);
  long startEncoderLength = globalEncoderCount;
  
  while (abs(globalEncoderCount - startEncoderLength) < length){
    if (checkStall()) {
      // Exiting motion due to stall
      break;
    }  
  }
  stopMotor();
  return abs(globalEncoderCount - startEncoderLength);
}
 
// FIXED: UI Compatible Stir Logic
void stir(){
  unsigned long startTime = millis();
  
  // Try to drive down
  int dist1 = driveDistance(down, lead);
  
  // Check if it stalled (using a 50 tick buffer to account for minor inertia differences)
  if (dist1 < (lead - 50)){ 
    
    // It jammed! Back up EXACTLY the distance it traveled
    driveDistance(!down, dist1);
    delay(250); // Pause for dirt to settle
    
    // Try going down one more time
    int dist2 = driveDistance(down, lead);
    
    if (dist2 < (lead - 50)){
      // Failed a second time. Give up, back out, and tell Python it failed
      driveDistance(!down, dist2);
      Serial.println("F1"); // Send Fail code to Python UI
      return; 
    }
    else {
      // Succeeded on the second try, return to top
      driveDistance(!down, lead);
    }
  }
  else {
    // Succeeded on the first try, return to top
    driveDistance(!down, lead);
  }
 
  // Success! Send standard "Y" + elapsed time back to Python UI
  Serial.print("Y");
  Serial.println(millis() - startTime);
}
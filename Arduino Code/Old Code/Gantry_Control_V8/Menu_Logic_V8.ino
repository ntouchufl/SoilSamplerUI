#include "Config_V8.h"  

String inputStr = "";  

void printMenu() {
  Serial.println(F("\n--- GANTRY v8.0 ---"));
  Serial.println(F(" ON / OFF : Motor Power"));
  Serial.println(F(" H        : Perimeter Home (0,0 @ X-MIN/Y-MIN)"));
  Serial.println(F(" S        : Sample-Tube Automation (Continuous)"));
  Serial.println(F(" R        : Regular Mode (Wait for external signal)"));
  Serial.println(F(" M        : Manual Absolute (X,Y)"));
  Serial.println(F(" MON      : Sensor Monitoring"));
  Serial.println(F(" Q        : ABORT"));
}  

void handleMenu() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == 'Q' || c == 'q') { globalInterrupt(); inputStr = ""; return; }
    if (c == '\n' || c == '\r') {
      if (inputStr.length() > 0) {
        if (manualWaiting) processManual(inputStr);
        else executeCmd(inputStr);
        inputStr = "";
      }
    } else { inputStr += c; }
  }
}  

void executeCmd(String cmd) {
  cmd.trim(); cmd.toUpperCase();
  if (cmd == "H") physicsHome();
  else if (cmd == "S") { 
    isRunning = true; 
    currentSample = 0; 
    sequenceStartTime = millis();
    pausedTime = 0;
    regularMode = false;
  }
  else if (cmd == "R") {
    isRunning = true; 
    currentSample = 0; 
    sequenceStartTime = millis();
    pausedTime = 0;
    regularMode = true;
    Serial.println(F(">> Regular Mode: Will wait for signal at each sample"));
  }
  else if (cmd == "M") { manualWaiting = true; Serial.println(F("Enter Absolute Target (X,Y):")); }
  else if (cmd == "ON") setMotors(true);
  else if (cmd == "OFF") setMotors(false);
  else if (cmd == "MON") monitorActive = !monitorActive;
}
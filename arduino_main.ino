/*
 * 6-DOF Robotic Arm Controller for PCA9685
 * Compatible with Position-Based Hand Gesture Control
 * 
 * Serial Protocol: "servoIndexangle\n"
 * Examples: "190" = servo 1 to 90°, "5120" = servo 5 to 120°
 * 
 * Servo Mapping:
 * 1 = ELBOW
 * 2 = SHOULDER
 * 3 = PRONATION-SUPINATION
 * 4 = FLEXION-EXTENSION
 * 5 = GRIPPER
 * 6 = BASE
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Initialize PCA9685
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// Servo calibration (adjust these if your servos behave differently)
#define SERVO_MIN 150   // Pulse length for 0° (typically 150-200)
#define SERVO_MAX 600   // Pulse length for 180° (typically 550-650)

// Servo configuration
const int SERVO_COUNT = 6;

// Smoothing configuration
int currentAngles[SERVO_COUNT] = {90, 90, 90, 90, 90, 90};  // Current positions
int targetAngles[SERVO_COUNT] = {90, 90, 90, 90, 90, 90};   // Target positions
const int SMOOTH_STEP = 2;  // Degrees per update (increase for faster movement)
const int UPDATE_INTERVAL = 15;  // Milliseconds between updates
unsigned long lastUpdate = 0;

// Command buffer
String inputBuffer = "";

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10);
  
  // Initialize PCA9685
  pwm.begin();
  pwm.setPWMFreq(50);  // Standard 50Hz for servos
  delay(10);
  
  // Home all servos to 90°
  Serial.println("Initializing servos...");
  for (int i = 0; i < SERVO_COUNT; i++) {
    moveServoImmediate(i + 1, 90);
  }
  delay(500);
  
  Serial.println("==============================================");
  Serial.println("6-DOF Robot Arm - Ready for Gesture Control");
  Serial.println("==============================================");
  Serial.println("Servo Mapping:");
  Serial.println("  [1] ELBOW");
  Serial.println("  [2] SHOULDER");
  Serial.println("  [3] PRONATION-SUPINATION");
  Serial.println("  [4] FLEXION-EXTENSION");
  Serial.println("  [5] GRIPPER");
  Serial.println("  [6] BASE");
  Serial.println("==============================================");
  Serial.println("Waiting for commands...\n");
}

/**
 * Convert angle (0-180°) to PCA9685 pulse width
 */
int angleToPulse(int angle) {
  angle = constrain(angle, 0, 180);
  return map(angle, 0, 180, SERVO_MIN, SERVO_MAX);
}

/**
 * Move servo immediately (no smoothing) - used for initialization
 */
void moveServoImmediate(int servoIndex, int angle) {
  if (servoIndex < 1 || servoIndex > SERVO_COUNT) {
    Serial.print("ERR: Invalid servo index ");
    Serial.println(servoIndex);
    return;
  }
  
  angle = constrain(angle, 0, 180);
  int pulse = angleToPulse(angle);
  pwm.setPWM(servoIndex - 1, 0, pulse);  // Channels 0-5 for servos 1-6
  currentAngles[servoIndex - 1] = angle;
  targetAngles[servoIndex - 1] = angle;
}

/**
 * Set target angle for smooth movement
 */
void setTargetAngle(int servoIndex, int angle) {
  if (servoIndex < 1 || servoIndex > SERVO_COUNT) {
    Serial.print("ERR: Invalid servo index ");
    Serial.println(servoIndex);
    return;
  }
  
  angle = constrain(angle, 0, 180);
  targetAngles[servoIndex - 1] = angle;
  
  // Optional: Print confirmation
  // Serial.print("Target set: S");
  // Serial.print(servoIndex);
  // Serial.print(" -> ");
  // Serial.print(angle);
  // Serial.println("°");
}

/**
 * Smooth servo movement update (non-blocking)
 */
void updateSmoothMovement() {
  unsigned long currentTime = millis();
  if (currentTime - lastUpdate >= UPDATE_INTERVAL) {
    lastUpdate = currentTime;
    
    for (int i = 0; i < SERVO_COUNT; i++) {
      int current = currentAngles[i];
      int target = targetAngles[i];
      
      if (current != target) {
        // Move towards target
        if (current < target) {
          current += SMOOTH_STEP;
          if (current > target) current = target;
        } else {
          current -= SMOOTH_STEP;
          if (current < target) current = target;
        }
        
        // Update servo
        int pulse = angleToPulse(current);
        pwm.setPWM(i, 0, pulse);
        currentAngles[i] = current;
      }
    }
  }
}

/**
 * Parse serial command in format: "servoIndexangle"
 * Examples: "190" = servo 1 to 90°, "5120" = servo 5 to 120°
 */
void parseCommand(String input) {
  input.trim();
  
  if (input.length() < 2) {
    Serial.print("ERR: Command too short: '");
    Serial.print(input);
    Serial.println("'");
    return;
  }
  
  // Extract servo index (first character)
  int servoIndex = input.substring(0, 1).toInt();
  
  // Extract angle (remaining characters)
  int angle = input.substring(1).toInt();
  
  // Validate
  if (servoIndex < 1 || servoIndex > SERVO_COUNT) {
    Serial.print("ERR: Invalid servo index ");
    Serial.print(servoIndex);
    Serial.print(" in command '");
    Serial.print(input);
    Serial.println("'");
    return;
  }
  
  if (angle < 0 || angle > 180) {
    Serial.print("ERR: Invalid angle ");
    Serial.print(angle);
    Serial.print(" in command '");
    Serial.print(input);
    Serial.println("'");
    return;
  }
  
  // Execute command
  setTargetAngle(servoIndex, angle);
  
  // Optional: Uncomment for verbose feedback
  // Serial.print("OK: S");
  // Serial.print(servoIndex);
  // Serial.print(" -> ");
  // Serial.print(angle);
  // Serial.println("°");
}

void loop() {
  // Read serial commands (non-blocking)
  while (Serial.available() > 0) {
    char inChar = Serial.read();
    
    if (inChar == '\n') {
      // Process complete command
      if (inputBuffer.length() > 0) {
        parseCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      // Build command string
      inputBuffer += inChar;
      
      // Prevent buffer overflow
      if (inputBuffer.length() > 10) {
        Serial.println("ERR: Command too long, resetting buffer");
        inputBuffer = "";
      }
    }
  }
  
  // Update smooth movements
  updateSmoothMovement();
}
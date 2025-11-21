#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

#define SERVO_MIN 150   // PCA9685 pulse length for 0°
#define SERVO_MAX 600   // PCA9685 pulse length for 180°

int servoCount = 6;

void setup() {
  Serial.begin(115200);
  pwm.begin();
  pwm.setPWMFreq(50);  // Standard servo frequency
  delay(10);
}

// Convert 0–180° to PCA9685 pulse width
int angleToPulse(int angle) {
  return map(angle, 0, 180, SERVO_MIN, SERVO_MAX);
}

void moveServo(int servoIndex, int angle) {
  if (servoIndex < 1 || servoIndex > servoCount) return;

  int pulse = angleToPulse(angle);
  pwm.setPWM(servoIndex - 1, 0, pulse);  // channels 0–5 for servo 1–6
}

void loop() {
  if (Serial.available()) {

    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() < 2) return;  // Must be like "190" or "6120"

    int servoIndex = input.substring(0, 1).toInt(); 
    int angle = input.substring(1).toInt();

    angle = constrain(angle, 0, 180);

    moveServo(servoIndex, angle);
  }
}

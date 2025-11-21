import cv2
import mediapipe as mp
import numpy as np
import serial
import serial.tools.list_ports
import time
from collections import deque

class HandGestureRobot:
    def __init__(self, port=None, baud=115200):
        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Gesture state
        self.current_gesture = "NONE"
        self.gesture_buffer = deque(maxlen=8)  # Larger buffer for stability
        self.active_servo = 1  # Currently controlled servo
        
        # Position smoothing buffer
        self.position_buffer = deque(maxlen=5)
        self.angle_buffer = deque(maxlen=5)
        self.last_sent_angles = {i: None for i in range(1, 7)}  # Track each servo separately
        
        # Serial connection
        self.ser = None
        self.connected = False
        if port:
            self.connect_arduino(port, baud)
        
        # FPS calculation
        self.fps_buffer = deque(maxlen=30)
        self.last_time = time.time()
        
        # Servo names (MATCHES YOUR ARDUINO MAPPING)
        self.servo_names = {
            1: "ELBOW",
            2: "SHOULDER", 
            3: "PRONATION-SUPINATION",
            4: "FLEXION-EXTENSION",
            5: "GRIPPER",
            6: "BASE"
        }
        
        # Gesture to Servo mapping (matches your code)
        self.gesture_servo_map = {
            "PINCH": 5,  # Pinch → GRIPPER (servo 5)
            "THREE": 3,  # 3 fingers → PRONATION-SUPINATION (servo 3)
            "PEACE": 4,  # Peace → FLEXION-EXTENSION (servo 4)
            "POINT": 1,  # Point → ELBOW (servo 1)
            "OPEN": 2,   # Open hand → SHOULDER (servo 2)
            "FIST": 6    # Fist → BASE (servo 6)
        }
    
    def list_ports(self):
        """List available COM ports"""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]
    
    def connect_arduino(self, port, baud=115200):
        """Connect to Arduino"""
        try:
            self.ser = serial.Serial(port, baud, timeout=0.5)
            time.sleep(2)  # Allow Arduino reset
            self.connected = True
            print(f"✓ Connected to {port} @ {baud} baud")
            
            # Home all servos to 90°
            for servo_num in range(1, 7):
                self.send_to_arduino(servo_num, 90)
                self.last_sent_angles[servo_num] = 90
                time.sleep(0.05)
            
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
        print("Disconnected from Arduino")
    
    def send_to_arduino(self, servo_index, angle):
        """
        Send command in format: servoIndexangle
        Example: "190" = servo 1 to 90°, "6120" = servo 6 to 120°
        """
        if not self.connected or not self.ser:
            return False
        
        try:
            # Format: servo index (1-6) + angle (0-180)
            command = f"{int(servo_index)}{int(angle)}\n"
            self.ser.write(command.encode('ascii'))
            return True
        except Exception as e:
            print(f"Serial error: {e}")
            return False
    
    def count_fingers(self, hand_landmarks):
        """Count extended fingers"""
        fingers_up = 0
        
        # Thumb (compare x-coordinates)
        if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
            fingers_up += 1
        
        # Other fingers (compare y-coordinates)
        finger_tips = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky
        finger_pips = [6, 10, 14, 18]
        
        for tip, pip in zip(finger_tips, finger_pips):
            if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
                fingers_up += 1
        
        return fingers_up
    
    def calculate_pinch_distance(self, hand_landmarks):
        """Calculate distance between thumb tip and index finger tip"""
        thumb_tip = hand_landmarks.landmark[4]
        index_tip = hand_landmarks.landmark[8]
        
        distance = np.sqrt(
            (thumb_tip.x - index_tip.x)**2 + 
            (thumb_tip.y - index_tip.y)**2 + 
            (thumb_tip.z - index_tip.z)**2
        )
        
        return distance
    
    def detect_gesture(self, hand_landmarks):
        """Detect hand gesture (YOUR METHOD)"""
        fingers = self.count_fingers(hand_landmarks)
        pinch_dist = self.calculate_pinch_distance(hand_landmarks)
        
        # Gestures (exact order from your code)
        if fingers == 0:
            return "FIST"  # Fist = BASE
        elif fingers == 5:
            return "OPEN"  # Open hand = SHOULDER
        elif fingers == 1:
            return "POINT"  # Point = ELBOW
        elif fingers == 2:
            return "PEACE"  # Peace = WRIST2 (FLEXION-EXTENSION)
        elif fingers == 3:
            return "THREE"  # 3 fingers = WRIST1 (PRONATION-SUPINATION)
        elif pinch_dist < 0.05:
            return "PINCH"  # Pinch = GRIPPER
        else:
            return "NONE"
    
    def get_hand_center_position(self, hand_landmarks):
        """
        Get the center position of the hand (palm center)
        Returns x position normalized 0-1 (left to right)
        """
        # Use palm center (landmark 9 is middle of palm)
        palm_center = hand_landmarks.landmark[9]
        return palm_center.x
    
    def position_to_angle(self, x_position):
        """
        Convert hand X position (0-1) to servo angle (0-180°)
        Left side of screen = 0°
        Right side of screen = 180°
        """
        # Add dead zones on edges (5% on each side)
        dead_zone = 0.05
        
        if x_position < dead_zone:
            x_position = dead_zone
        elif x_position > (1 - dead_zone):
            x_position = 1 - dead_zone
        
        # Normalize to 0-1 range
        normalized = (x_position - dead_zone) / (1 - 2 * dead_zone)
        
        # Map to 0-180°
        angle = int(normalized * 180)
        return angle
    
    def process_frame(self, frame):
        """Process video frame and control robot with position-based control"""
        
        # Calculate FPS
        current_time = time.time()
        fps = 1 / (current_time - self.last_time + 1e-6)
        self.fps_buffer.append(fps)
        self.last_time = current_time
        avg_fps = np.mean(self.fps_buffer)
        
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        frame_height, frame_width = frame.shape[:2]
        
        # Draw angle zone indicator (color bar at top)
        bar_height = 30
        cv2.rectangle(frame, (0, 0), (frame_width, bar_height), (50, 50, 50), -1)
        
        # Draw angle markers
        for angle in [0, 45, 90, 135, 180]:
            x = int((angle / 180) * frame_width)
            cv2.line(frame, (x, 0), (x, bar_height), (255, 255, 255), 1)
            cv2.putText(frame, f"{angle}°", (x - 15, bar_height - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw status panel
        panel_height = 250
        panel = np.zeros((panel_height, frame_width, 3), dtype=np.uint8)
        
        # Connection status
        status_color = (0, 255, 0) if self.connected else (0, 0, 255)
        status_text = "CONNECTED" if self.connected else "DISCONNECTED"
        cv2.putText(panel, f"Status: {status_text}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # FPS
        cv2.putText(panel, f"FPS: {int(avg_fps)}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw hand skeleton
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                    self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                )
                
                # Detect gesture
                gesture = self.detect_gesture(hand_landmarks)
                self.gesture_buffer.append(gesture)
                
                # Smooth gesture detection (require consistency)
                if len(self.gesture_buffer) >= 5:
                    most_common = max(set(self.gesture_buffer), key=self.gesture_buffer.count)
                    if most_common != "NONE":
                        self.current_gesture = most_common
                        
                        # Auto-select servo based on gesture
                        if self.current_gesture in self.gesture_servo_map:
                            new_servo = self.gesture_servo_map[self.current_gesture]
                            if new_servo != self.active_servo:
                                self.active_servo = new_servo
                                self.position_buffer.clear()
                                self.angle_buffer.clear()
                
                # Get hand position
                x_position = self.get_hand_center_position(hand_landmarks)
                self.position_buffer.append(x_position)
                
                # Smooth position
                smoothed_x = np.mean(self.position_buffer)
                
                # Convert position to angle
                angle = self.position_to_angle(smoothed_x)
                self.angle_buffer.append(angle)
                smoothed_angle = int(np.mean(self.angle_buffer))
                
                # Draw position indicator on angle bar
                indicator_x = int(smoothed_x * frame_width)
                cv2.circle(frame, (indicator_x, bar_height // 2), 12, (0, 255, 255), -1)
                cv2.circle(frame, (indicator_x, bar_height // 2), 12, (0, 0, 0), 2)
                
                # Draw vertical line from hand to indicator
                palm_y = int(hand_landmarks.landmark[9].y * frame_height)
                palm_x = int(hand_landmarks.landmark[9].x * frame_width)
                cv2.line(frame, (palm_x, palm_y), (indicator_x, bar_height), (0, 255, 255), 2)
                
                # Display current gesture
                gesture_color = (0, 255, 255) if self.current_gesture != "NONE" else (128, 128, 128)
                cv2.putText(panel, f"Gesture: {self.current_gesture}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, gesture_color, 2)
                
                # Active servo (with arrow indicator)
                servo_name = self.servo_names.get(self.active_servo, "UNKNOWN")
                cv2.putText(panel, f">>> Servo {self.active_servo}: {servo_name}", (10, 125),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # Display angle
                cv2.putText(panel, f"Target Angle: {smoothed_angle}°", (10, 160),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                
                # Display position
                cv2.putText(panel, f"Hand Position: {smoothed_x:.2f}", (10, 190),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                # Send to Arduino (only if changed by more than 3°)
                if self.connected and self.current_gesture != "NONE":
                    last_angle = self.last_sent_angles[self.active_servo]
                    if last_angle is None or abs(smoothed_angle - last_angle) > 3:
                        self.send_to_arduino(self.active_servo, smoothed_angle)
                        self.last_sent_angles[self.active_servo] = smoothed_angle
                        cv2.putText(panel, f"✓ Sent: S{self.active_servo} = {smoothed_angle}°", 
                                   (10, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        else:
            cv2.putText(panel, "No hand detected", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            self.current_gesture = "NONE"
        
        # Combine frame and panel
        combined = np.vstack([frame, panel])
        
        # Gesture mapping legend (right side)
        legend_x = frame_width - 240
        legend_y_start = frame_height + 30
        cv2.putText(combined, "Gesture Map:", (legend_x, legend_y_start), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        cv2.putText(combined, "PINCH -> Gripper", (legend_x, legend_y_start + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(combined, "3 Fingers -> Pronation", (legend_x, legend_y_start + 45), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(combined, "Peace -> Flexion", (legend_x, legend_y_start + 65), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(combined, "Point -> Elbow", (legend_x, legend_y_start + 85), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(combined, "Open -> Shoulder", (legend_x, legend_y_start + 105), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(combined, "Fist -> Base", (legend_x, legend_y_start + 125), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        
        # Instructions
        cv2.putText(combined, "Move hand LEFT/RIGHT to control angle | H=Home | Q=Quit", 
                   (10, combined.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return combined
    
    def home_all_servos(self):
        """Move all servos to 90° (home position)"""
        print("Homing all servos...")
        for servo_num in range(1, 7):
            self.send_to_arduino(servo_num, 90)
            self.last_sent_angles[servo_num] = 90
            time.sleep(0.05)
        
        self.position_buffer.clear()
        self.angle_buffer.clear()
    
    def run(self):
        """Main loop"""
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not cap.isOpened():
            print("Error: Cannot access webcam")
            return
        
        print("\n" + "="*70)
        print("HAND GESTURE ROBOT CONTROL - POSITION-BASED CONTROL")
        print("="*70)
        print("\n🎯 HOW TO USE:")
        print("  1. Show a GESTURE to select which servo to control")
        print("  2. Move your hand LEFT/RIGHT on screen to set angle")
        print("     • Left side  = 0°")
        print("     • Center     = 90°")
        print("     • Right side = 180°")
        print("\n✋ GESTURE CONTROLS:")
        print("  🤏 PINCH (thumb+index) → Servo 5: GRIPPER")
        print("  ✌️  THREE fingers        → Servo 3: PRONATION-SUPINATION")
        print("  ✌️  PEACE (2 fingers)    → Servo 4: FLEXION-EXTENSION")
        print("  ☝️  POINT (1 finger)     → Servo 1: ELBOW")
        print("  🖐️  OPEN (5 fingers)     → Servo 2: SHOULDER")
        print("  ✊ FIST (closed)        → Servo 6: BASE")
        print("\n⌨️  KEYBOARD CONTROLS:")
        print("  H = Home all servos (90°)")
        print("  Q = Quit")
        print("="*70 + "\n")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to grab frame")
                    break
                
                frame = cv2.flip(frame, 1)
                processed_frame = self.process_frame(frame)
                
                cv2.imshow('Hand Gesture Robot Control', processed_frame)
                
                key = cv2.waitKey(1) & 0xFF
                
                # Quit
                if key == ord('q') or key == ord('Q'):
                    break
                
                # Home
                elif key == ord('h') or key == ord('H'):
                    self.home_all_servos()
        
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.disconnect()
            print("\nShutdown complete")


def main():
    """Interactive startup with port selection"""
    print("\n" + "="*70)
    print("HAND GESTURE ROBOT CONTROLLER - POSITION-BASED CONTROL")
    print("="*70 + "\n")
    
    # List available ports
    controller = HandGestureRobot()
    ports = controller.list_ports()
    
    if not ports:
        print("✗ No COM ports found!")
        print("\nRunning in DEMO MODE (no robot control)")
        controller.run()
        return
    
    print("Available COM Ports:")
    for i, port in enumerate(ports, 1):
        print(f"  [{i}] {port}")
    
    # Port selection
    while True:
        choice = input(f"\nSelect port (1-{len(ports)}) or 'D' for demo mode: ").strip().upper()
        
        if choice == 'D':
            print("\n→ Running in DEMO MODE (no Arduino)")
            controller.run()
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                selected_port = ports[idx]
                break
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Invalid input. Enter a number or 'D'.")
    
    # Baud rate selection
    baud = input("Enter baud rate (default 115200): ").strip()
    baud = int(baud) if baud.isdigit() else 115200
    
    # Connect and run
    if controller.connect_arduino(selected_port, baud):
        print("\n✓ Ready! Show gestures and move your hand left/right!")
        controller.run()
    else:
        print("\n✗ Failed to connect. Check port and try again.")


if __name__ == "__main__":
    main()
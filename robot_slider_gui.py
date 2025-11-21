"""
robot_sliders_gui.py
Simple GUI (PySimpleGUI) to control 6 servos via Serial.
Sends commands as: "<servoIndex><angle>\\n" (e.g. "190\\n" moves servo 1 to 90°)
"""

import PySimpleGUI as sg
import serial
import serial.tools.list_ports
import time
import json
import os

# ---------- CONFIG ----------
BAUD_DEFAULT = 9600
SERVO_COUNT = 6
IMAGE_PATH = r"C:\Users\danyb\Desktop\Robo_GUI.png"  # reference image (from your upload)
# ----------------------------

# Serial helper
class SerialController:
    def __init__(self):
        self.ser = None
        self.connected = False

    def list_ports(self):
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port, baud=BAUD_DEFAULT):
        try:
            self.ser = serial.Serial(port, baud, timeout=0.5)
            time.sleep(2)  # allow Arduino reset
            self.connected = True
            return True, f"Connected {port}@{baud}"
        except Exception as e:
            self.connected = False
            return False, str(e)

    def disconnect(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass
        self.connected = False

    def send_servo(self, servo_index, angle):
        """Send command 'servoIndexangle\\n' where servo_index is 1..6."""
        if not self.connected or not self.ser:
            return False, "Not connected"
        try:
            cmd = f"{int(servo_index)}{int(angle)}\n"
            self.ser.write(cmd.encode('ascii'))
            # small delay
            time.sleep(0.02)
            return True, cmd
        except Exception as e:
            return False, str(e)

serial_ctrl = SerialController()

# ---------- GUI Layout ----------
sg.theme("DarkBlue3")

# left column: connection and image
left_col = [
    [sg.Text("Select Port:"), sg.Combo(serial_ctrl.list_ports(), key="-PORT-", size=(20,1)), sg.Button("Refresh", key="-REF-")],
    [sg.Text("Baud:"), sg.Input(BAUD_DEFAULT, key="-BAUD-", size=(8,1)), sg.Button("Connect", key="-CONNECT-"), sg.Button("Disconnect", key="-DISCONNECT-")],
    [sg.Text("", key="-STATUS-", size=(40,1))],
    [sg.HorizontalSeparator()],
    [sg.Text("Reference Image:")],
    [sg.Image(filename=IMAGE_PATH, key="-IMAGE-", size=(400,400))],
]

# right column: sliders and controls
# Custom labels for each servo
SERVO_LABELS = [
    "Elbow",                  # Servo 1
    "Shoulder",               # Servo 2
    "Pronation-Supination",   # Servo 3
    "Flexion-Extension",      # Servo 4
    "Gripper",                # Servo 5
    "Base"                    # Servo 6
]

# Right-column sliders with custom labels
slider_rows = []
for i in range(SERVO_COUNT):
    label = SERVO_LABELS[i]
    slider_key = f"-S{i+1}-"
    input_key = f"-IN{i+1}-"
    slider_rows.append([
        sg.Text(label, size=(18,1)),
        sg.Slider(range=(0,180), orientation="h", size=(40,15),
                  key=slider_key, default_value=90, enable_events=True),
        sg.InputText("90", size=(4,1), key=input_key)
    ])

right_col = [
    [sg.Frame("Servo Controls", slider_rows)],
    [sg.Button("Send All", key="-SEND_ALL-"), sg.Button("Home", key="-HOME-")],
    [sg.HorizontalSeparator()],
    [sg.Text("Sequence (poses):")],
    [sg.Button("Save Pose", key="-SAVE-"), sg.Button("Run Sequence", key="-RUN-"), sg.Button("Clear", key="-CLEAR-")],
    [sg.Text("Delay (s) between poses:"), sg.InputText("0.5", key="-DELAY-", size=(6,1))],
    [sg.Listbox(values=[], size=(50,6), key="-SEQ_LIST-")],
    [sg.Button("Export JSON", key="-EXPORT-"), sg.Button("Import JSON", key="-IMPORT-")],
    [sg.HorizontalSeparator()],
    [sg.Text("Log:")],
    [sg.Multiline("", size=(70,8), key="-LOG-")]
]

layout = [
    [sg.Column(left_col), sg.VerticalSeparator(), sg.Column(right_col)]
]

window = sg.Window("Robot Slider Controller", layout, finalize=True)

# internal state
sequence = []

def log(msg):
    existing = window["-LOG-"].get()
    new = existing + msg + "\n"
    window["-LOG-"].update(new)

# main event loop
while True:
    event, values = window.read(timeout=100)
    if event == sg.WINDOW_CLOSED:
        break

    if event == "-REF-":
        window["-PORT-"].update(values=serial_ctrl.list_ports())

    if event == "-CONNECT-":
        port = values["-PORT-"]
        if not port:
            sg.popup("Select a COM port first (Refresh to list).")
            continue
        try:
            baud = int(values["-BAUD-"])
        except:
            baud = BAUD_DEFAULT
        ok, msg = serial_ctrl.connect(port, baud)
        window["-STATUS-"].update(msg)
        log(msg)

    if event == "-DISCONNECT-":
        serial_ctrl.disconnect()
        window["-STATUS-"].update("Disconnected")
        log("Disconnected")

    # slider moved -> update input box and send
    for i in range(SERVO_COUNT):
        s_key = f"-S{i+1}-"
        in_key = f"-IN{i+1}-"
        if event == s_key:
            val = int(values[s_key])
            window[in_key].update(val)
            if serial_ctrl.connected:
                ok, resp = serial_ctrl.send_servo(i+1, val)
                if ok:
                    log(f"Sent: {resp.strip()}")
                else:
                    log(f"Err: {resp}")

    # manual input changed -> update slider and send
    for i in range(SERVO_COUNT):
        in_key = f"-IN{i+1}-"
        s_key = f"-S{i+1}-"
        if event == in_key:
            try:
                ang = int(values[in_key])
                ang = max(0, min(180, ang))
                window[s_key].update(ang)
                if serial_ctrl.connected:
                    ok, resp = serial_ctrl.send_servo(i+1, ang)
                    if ok:
                        log(f"Sent: {resp.strip()}")
                    else:
                        log(f"Err: {resp}")
            except:
                pass

    if event == "-SEND_ALL-":
        if serial_ctrl.connected:
            for i in range(SERVO_COUNT):
                ang = int(values[f"-S{i+1}-"])
                ok, resp = serial_ctrl.send_servo(i+1, ang)
                if ok:
                    log(f"Sent: {resp.strip()}")
                else:
                    log(f"Err: {resp}")
        else:
            sg.popup("Not connected to serial port.")

    if event == "-HOME-":
        for i in range(SERVO_COUNT):
            window[f"-S{i+1}-"].update(90)
            window[f"-IN{i+1}-"].update("90")
            if serial_ctrl.connected:
                serial_ctrl.send_servo(i+1, 90)
        log("Homed all servos to 90°")

    if event == "-SAVE-":
        pose = [int(values[f"-S{i+1}-"]) for i in range(SERVO_COUNT)]
        sequence.append(pose)
        window["-SEQ_LIST-"].update([str(p) for p in sequence])
        log(f"Saved pose: {pose}")

    if event == "-CLEAR-":
        sequence = []
        window["-SEQ_LIST-"].update([])
        log("Cleared sequence")

    if event == "-RUN-":
        if not sequence:
            sg.popup("Sequence empty. Save poses first.")
        else:
            try:
                delay_s = float(values["-DELAY-"])
            except:
                delay_s = 0.5
            log(f"Running sequence ({len(sequence)} poses) with {delay_s}s delay")
            for pose in sequence:
                for i, ang in enumerate(pose):
                    if serial_ctrl.connected:
                        serial_ctrl.send_servo(i+1, ang)
                    time.sleep(0.02)  # small gap between servo commands
                time.sleep(delay_s)
            log("Sequence finished")

    if event == "-EXPORT-":
        if not sequence:
            sg.popup("No sequence to export.")
        else:
            fn = sg.popup_get_file("Save sequence as JSON", save_as=True, file_types=(("JSON files","*.json"),), default_extension="json")
            if fn:
                try:
                    with open(fn, "w") as f:
                        json.dump(sequence, f)
                    log(f"Exported sequence to {fn}")
                except Exception as e:
                    sg.popup("Failed to save:", e)

    if event == "-IMPORT-":
        fn = sg.popup_get_file("Open sequence JSON", file_types=(("JSON files","*.json"),))
        if fn:
            try:
                with open(fn, "r") as f:
                    sequence = json.load(f)
                window["-SEQ_LIST-"].update([str(p) for p in sequence])
                log(f"Imported sequence from {fn}")
            except Exception as e:
                sg.popup("Failed to import:", e)

# cleanup
serial_ctrl.disconnect()
window.close()

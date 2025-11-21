# Ordimus Bot - Your Pick-and-Place Robot

A complete multi-modal robotic arm platform combining Arduino-based servo control, a custom-built desktop GUI for manual operation & motion recording, and a computer-vision controller using OpenCV + MediaPipe for gesture-based or vision-based automation.

This repo houses:
✔ Arduino code
✔ GUI controller code
✔ Vision-based control code

## 🚀 Project Overview

This project demonstrates a full robotics stack from perception → planning → actuation.

Includes three major subsystems:

1️. **Arduino Motion Controller (Firmware)**

Handles:

Low-level servo actuation

Receiving angle commands

Position saving & playback

Safety limits (joint constraints)

Smooth movement via angle interpolation

Serial communication with GUI & CV modules

2️. **Desktop GUI Controller**

A standalone GUI (Python/PyQt / Tkinter / Processing / etc.) enabling:

Real-time manual control of the arm

Slider-based or joystick-based joint movement

Save multiple motion keyframes

Play sequences with adjustable speed

Import/export pose libraries (.json / .txt)

Servo offset calibration

Emergency stop & reset

3️. **OpenCV + MediaPipe Vision Control**

This subsystem allows hands-free or object-based control of the robotic arm:

Object detection (OpenCV)

Hand-gesture detection (MediaPipe)

Mapping gestures → joint commands

Pixel → world coordinate transformation

## 🧠 Core Features

1. **Vision Features**

Hand tracking (MediaPipe Hands)

Gesture-to-motion mapping

Object tracking using contours & color segmentation

Pose estimation

Real-time camera feed calibration

2. **Motion Features**

Linear interpolation between poses

IK + FK modules

Servo zero-offset calibration

Motion playback and sequencing

Jitter suppression & smoothing

Emergency stop override
                
Automatic reach & grasp positioning

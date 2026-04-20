"""
============================================================
Smart Posture Correction System — Computer Vision Module
============================================================
Detects head/neck posture in real-time using:
  - dlib 68-point facial landmark detection
  - OpenCV solvePnP (Perspective-n-Point) head pose estimation
  - 7-frame rolling pitch average for stable classification
  - UDP socket to send posture alerts to ESP32-C3 wearable

Posture Classes (pitch angle ranges):
  - Straight     : -2° ≤ avg ≤ 2°   → Good
  - Inclined      : -17° ≤ avg < -2° → OK (relaxed)
  - Humped Back   : 2° < avg ≤ 17°  → BAD
  - Looking Down  : avg > 17°        → BAD
  - Overly Inclined: avg < -17°      → BAD

Industry Award Winner — 9th EE Capstone Showcase (EECS 2026)
Universiti Teknologi Malaysia
============================================================

Requirements:
  pip install opencv-python dlib imutils numpy
  Download shape_predictor_68_face_landmarks.dat from:
  http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
  (extract and place in the same folder as this script)
"""

import cv2
import dlib
import numpy as np
from imutils import face_utils
import socket

# ============================================================
# 1. UDP CONFIGURATION
# ============================================================
# Step 1: Flash firmware to ESP32-C3
# Step 2: Open Arduino Serial Monitor to find the IP address printed on boot
# Step 3: Paste that IP address below

ESP_IP   = "192.168.0.100"  # <--- REPLACE WITH YOUR ESP32 IP (shown in Serial Monitor)
ESP_PORT = 4210             # Must match localPort in firmware

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.05)       # Non-blocking — short timeout

def send_to_esp32(is_bad_posture: bool):
    """Send '1' for bad posture, '0' for good posture via UDP."""
    try:
        msg = b'1' if is_bad_posture else b'0'
        sock.sendto(msg, (ESP_IP, ESP_PORT))
    except Exception as e:
        print(f"UDP Error: {e}")

# ============================================================
# 2. CAMERA INTRINSICS (generic 640×480 calibration)
# ============================================================
# Camera matrix K and distortion coefficients D
# (calibrated for a standard 640×480 webcam)
K = [6.5308391993466671e+002, 0.0, 3.1950000000000000e+002,
     0.0, 6.5308391993466671e+002, 2.3950000000000000e+002,
     0.0, 0.0, 1.0]
D = [7.0834633684407095e-002, 6.9140193737175351e-002,
     0.0, 0.0, -1.3073460323689292e+000]

cam_matrix  = np.array(K).reshape(3, 3).astype(np.float32)
dist_coeffs = np.array(D).reshape(5, 1).astype(np.float32)

# ============================================================
# 3. 3D FACE MODEL (14 anthropometric landmark positions)
# ============================================================
# These are standard 3D positions in face-centred coordinates (mm)
# Mapped to dlib landmarks: eyebrows, eye corners, nose, mouth, chin
object_pts = np.float32([
    [ 6.825897,  6.760612,  4.402142],  # [0]  Right brow outer
    [ 1.330353,  7.122144,  6.903745],  # [1]  Right brow inner
    [-1.330353,  7.122144,  6.903745],  # [2]  Left brow inner
    [-6.825897,  6.760612,  4.402142],  # [3]  Left brow outer
    [ 5.311432,  5.485328,  3.987654],  # [4]  Right eye outer corner
    [ 1.789930,  5.393625,  4.413414],  # [5]  Right eye inner corner
    [-1.789930,  5.393625,  4.413414],  # [6]  Left eye inner corner
    [-5.311432,  5.485328,  3.987654],  # [7]  Left eye outer corner
    [ 2.005628,  1.409845,  6.165652],  # [8]  Nose right
    [-2.005628,  1.409845,  6.165652],  # [9]  Nose left
    [ 2.774015, -2.080775,  5.048531],  # [10] Mouth right corner
    [-2.774015, -2.080775,  5.048531],  # [11] Mouth left corner
    [ 0.000000, -3.116408,  6.097667],  # [12] Mouth bottom centre
    [ 0.000000, -7.415691,  4.070434],  # [13] Chin
])

# Bounding cube for 3D axis visualisation
reprojectsrc = np.float32([
    [10, 10, 10], [10, 10, -10], [10, -10, -10], [10, -10, 10],
    [-10, 10, 10], [-10, 10, -10], [-10, -10, -10], [-10, -10, 10],
])
line_pairs = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]

# ============================================================
# 4. HEAD POSE ESTIMATION
# ============================================================
status_text = ''
frame_count = 0
pitch_buffer = [0.0] * 7   # 7-frame rolling average

def get_head_pose(shape):
    """
    Estimate head pose from 68 dlib landmarks using solvePnP.
    Updates pitch_buffer every frame; classifies posture every 7 frames.
    Returns reprojected 3D bounding box corners and euler angles.
    """
    global status_text, frame_count, pitch_buffer

    # Map 14 specific dlib landmarks → 2D image points
    image_pts = np.float32([
        shape[17], shape[21], shape[22], shape[26],  # eyebrows
        shape[36], shape[39], shape[42], shape[45],  # eye corners
        shape[31], shape[35],                         # nose
        shape[48], shape[54], shape[57],              # mouth
        shape[8]                                      # chin
    ])

    # Solve PnP → rotation & translation vectors
    _, rotation_vec, translation_vec = cv2.solvePnP(
        object_pts, image_pts, cam_matrix, dist_coeffs
    )

    # Project 3D bounding box for visualisation
    reprojectdst, _ = cv2.projectPoints(
        reprojectsrc, rotation_vec, translation_vec, cam_matrix, dist_coeffs
    )
    reprojectdst = [tuple(map(int, pt)) for pt in reprojectdst.reshape(8, 2)]

    # Decompose rotation matrix → Euler angles (pitch, yaw, roll)
    rotation_mat, _ = cv2.Rodrigues(rotation_vec)
    pose_mat        = cv2.hconcat((rotation_mat, translation_vec))
    _, _, _, _, _, _, euler_angle = cv2.decomposeProjectionMatrix(pose_mat)

    # Update 7-frame rolling pitch buffer
    j = frame_count % 7
    frame_count += 1
    pitch_buffer[j] = float(euler_angle[0])

    # Classify posture every 7 frames (once buffer is filled)
    if j == 0:
        avg    = sum(pitch_buffer) / 7
        is_bad = False

        if 2 < avg <= 17:
            status_text = 'Humped Back — BAD'
            is_bad = True
        elif -17 <= avg < -2:
            status_text = 'Inclined — OK'
            is_bad = False
        elif avg > 17:
            status_text = 'Looking Down — BAD'
            is_bad = True
        elif avg < -17:
            status_text = 'Overly Inclined — BAD'
            is_bad = True
        else:
            status_text = 'Sitting Straight — GOOD'
            is_bad = False

        print(f"[Posture] {status_text} | avg pitch: {avg:.1f}° | UDP → {'BAD' if is_bad else 'OK'}")
        send_to_esp32(is_bad)

    return reprojectdst, euler_angle

# ============================================================
# 5. MAIN LOOP
# ============================================================
def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam.")
        return

    detector  = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor('shape_predictor_68_face_landmarks.dat')

    print("=" * 50)
    print("Smart Posture Detection — RUNNING")
    print(f"Sending UDP alerts to {ESP_IP}:{ESP_PORT}")
    print("Press 'q' to quit")
    print("=" * 50)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        faces = detector(frame, 0)

        for rect in faces:
            shape = predictor(frame, rect)
            shape = face_utils.shape_to_np(shape)

            reprojectdst, euler_angle = get_head_pose(shape)

            # Draw 68 facial landmarks
            for (x, y) in shape:
                cv2.circle(frame, (x, y), 1, (0, 0, 255), -1)

            # Draw 3D bounding cube
            for start, end in line_pairs:
                cv2.line(frame, reprojectdst[start], reprojectdst[end], (0, 0, 255))

            # Overlay euler angles and status
            cv2.putText(frame, f"Pitch: {euler_angle[0, 0]:6.1f}", (20, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
            cv2.putText(frame, f"Yaw:   {euler_angle[1, 0]:6.1f}", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
            cv2.putText(frame, f"Roll:  {euler_angle[2, 0]:6.1f}", (20, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)

            is_bad_display = any(kw in status_text for kw in ['BAD'])
            color = (0, 0, 255) if is_bad_display else (0, 200, 0)
            cv2.putText(frame, status_text, (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        cv2.imshow("Smart Posture Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    sock.close()

if __name__ == '__main__':
    main()

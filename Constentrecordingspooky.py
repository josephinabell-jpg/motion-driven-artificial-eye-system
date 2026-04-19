"""
Spooky Eye Tracker - Fullscreen Pair + Optional MP4 Recording + Safer Quit
Press ESC, Q, or Cmd+W to quit.
Before launch, asks whether recording consent is given.
"""

import cv2
import pygame
import sys
import time
import random
import os

print("Python:", sys.version)
print("OpenCV:", cv2.__version__)
print("Pygame:", pygame.version.ver)

# ----------------- PARAMETERS -----------------
FULLSCREEN = True   # Set to False for easier testing in a normal window

AREA_THRESHOLD = 1200
ALPHA = 0.25
DIR_THRESHOLD = 0.35
DIRECTION_LAG = 0.12
DIAG_COMPONENT_THRESHOLD = 0.22

IDLE_SEARCH_ENABLED = True
IDLE_SEARCH_START_DELAY = 1.2
IDLE_SEARCH_DURATION = 3.0

IDLE_STEP_MIN_TIME = 0.15
IDLE_STEP_MAX_TIME = 0.35
IDLE_SMOOTH_ALPHA = 0.30
IDLE_RADIUS = 0.90

CENTER_LOCK_ALPHA = 0.20
BG_COLOR = (0, 0, 0)
# ------------------------------------------------


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def direction_from_gaze(gx, gy, threshold, diag_threshold):
    if abs(gx) < threshold and abs(gy) < threshold:
        return "center"

    if abs(gx) >= diag_threshold and abs(gy) >= diag_threshold:
        if gx < 0 and gy < 0:
            return "up_left"
        elif gx > 0 and gy < 0:
            return "up_right"
        elif gx < 0 and gy > 0:
            return "down_left"
        else:
            return "down_right"

    if abs(gx) >= abs(gy):
        return "right" if gx > 0 else "left"
    return "down" if gy > 0 else "up"


def pick_idle_target():
    r = IDLE_RADIUS
    d = 0.72 * IDLE_RADIUS

    choices = [
        ("left", (-r, 0.0)),
        ("right", (r, 0.0)),
        ("up", (0.0, -r)),
        ("down", (0.0, r)),
        ("up_left", (-d, -d)),
        ("up_right", (d, -d)),
        ("down_left", (-d, d)),
        ("down_right", (d, d)),
        ("center", (0.0, 0.0)),
    ]

    weights = [0.15, 0.15, 0.13, 0.13, 0.10, 0.10, 0.10, 0.10, 0.04]
    _, (tx, ty) = random.choices(choices, weights=weights, k=1)[0]

    tx += random.uniform(-0.06, 0.06)
    ty += random.uniform(-0.06, 0.06)
    return clamp(tx, -1.0, 1.0), clamp(ty, -1.0, 1.0)


def load_image_with_fallbacks(image_size, *names):
    for name in names:
        if os.path.exists(name):
            img = pygame.image.load(name).convert_alpha()
            return pygame.transform.smoothscale(img, image_size)
    raise FileNotFoundError(f"None of these files were found: {names}")


def ask_recording_consent():
    while True:
        answer = input("Do you consent to recording? (y/n): ").strip().lower()
        if answer in ["y", "yes"]:
            return True
        if answer in ["n", "no"]:
            return False
        print("Please enter 'y' for yes or 'n' for no.")


def quit_program(cap, out):
    try:
        if cap is not None:
            cap.release()
    except:
        pass

    try:
        if out is not None:
            out.release()
    except:
        pass

    pygame.quit()
    sys.exit()


def should_quit(event):
    if event.type == pygame.QUIT:
        return True

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            return True
        if event.key == pygame.K_q:
            return True
        if event.key == pygame.K_w and (event.mod & pygame.KMOD_META):
            return True

    return False


# ----------------- CONSENT -----------------
record_consent = ask_recording_consent()
print(f"Recording consent: {'YES' if record_consent else 'NO'}")

# ----------------- INIT -----------------
pygame.init()
pygame.display.set_caption("Spooky Eye")
clock = pygame.time.Clock()

if FULLSCREEN:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
else:
    screen = pygame.display.set_mode((1200, 700))

screen_width, screen_height = screen.get_size()

print(f"Screen size: {screen_width} x {screen_height}")
print("Press ESC, Q, or Cmd+W to quit.")

# Eye sizing and placement
eye_width = int(screen_width * 0.28)
eye_height = int(screen_height * 0.70)
EYE_SIZE = (eye_width, eye_height)

gap = int(screen_width * 0.04)
y_pos = (screen_height - eye_height) // 2

LEFT_EYE_POS = ((screen_width // 2) - eye_width - (gap // 2), y_pos)
RIGHT_EYE_POS = ((screen_width // 2) + (gap // 2), y_pos)

print(f"EYE_SIZE = {EYE_SIZE}")
print(f"LEFT_EYE_POS = {LEFT_EYE_POS}")
print(f"RIGHT_EYE_POS = {RIGHT_EYE_POS}")

# Load images
center_img = load_image_with_fallbacks(EYE_SIZE, "eye_center.png")
left_img = load_image_with_fallbacks(EYE_SIZE, "eye_left.png")
right_img = load_image_with_fallbacks(EYE_SIZE, "eye_right.png")
up_img = load_image_with_fallbacks(EYE_SIZE, "eye_up.png")
down_img = load_image_with_fallbacks(EYE_SIZE, "eye_down.png")
up_left_img = load_image_with_fallbacks(EYE_SIZE, "eye_up_left.png", "eye_up.left.png")
up_right_img = load_image_with_fallbacks(EYE_SIZE, "eye_up_right.png", "eye_up.right.png")
down_left_img = load_image_with_fallbacks(EYE_SIZE, "eye_down_left.png", "eye_down.left.png")
down_right_img = load_image_with_fallbacks(EYE_SIZE, "eye_down_right.png", "eye_down.right.png")

# Camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Could not open camera")
    pygame.quit()
    sys.exit(1)

ret, frame = cap.read()
if not ret:
    print("Could not read first camera frame")
    cap.release()
    pygame.quit()
    sys.exit(1)

# ----------------- OPTIONAL RECORDING SETUP -----------------
out = None
video_filename = None

if record_consent:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_filename = f"participant_{timestamp}.mp4"

    frame_height, frame_width = frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_filename, fourcc, 20.0, (frame_width, frame_height))

    print(f"Recording started: {os.path.abspath(video_filename)}")
else:
    print("Recording disabled. No video will be saved.")

prev_gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (7, 7), 0)

# State
gx_smooth, gy_smooth = 0.0, 0.0
current_dir = "center"
current_img = center_img
last_motion_time = time.time()
last_dir_change_time = time.time()

idle_target_x, idle_target_y = 0.0, 0.0
idle_next_switch_time = time.time() + random.uniform(IDLE_STEP_MIN_TIME, IDLE_STEP_MAX_TIME)

search_phase_active = False
search_phase_start_time = 0.0
center_lock_active = False

try:
    while True:
        # -------- event handling --------
        for event in pygame.event.get():
            if should_quit(event):
                quit_program(cap, out)

        ret, frame = cap.read()
        if not ret:
            print("Camera frame read failed")
            break

        # Save frame only if consent was given
        if out is not None:
            out.write(frame)

        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (7, 7), 0)

        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        thresh = cv2.erode(thresh, None, iterations=1)
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        gx, gy = 0.0, 0.0
        motion_found = False
        now = time.time()

        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)

            if area > AREA_THRESHOLD:
                x, y, w, h = cv2.boundingRect(largest)
                cx = x + w // 2
                cy = y + h // 2

                h_frame, w_frame = gray.shape[:2]
                gx = (cx - w_frame // 2) / (w_frame // 2)
                gy = (cy - h_frame // 2) / (h_frame // 2)

                motion_found = True
                last_motion_time = now

        prev_gray = gray

        # -------- motion tracking --------
        if motion_found:
            search_phase_active = False
            center_lock_active = False

            gx_smooth = (1 - ALPHA) * gx_smooth + ALPHA * gx
            gy_smooth = (1 - ALPHA) * gy_smooth + ALPHA * gy

            proposed_dir = direction_from_gaze(
                gx_smooth, gy_smooth, DIR_THRESHOLD, DIAG_COMPONENT_THRESHOLD
            )

            if proposed_dir != current_dir and (now - last_dir_change_time) > DIRECTION_LAG:
                current_dir = proposed_dir
                last_dir_change_time = now

            idle_next_switch_time = now + random.uniform(IDLE_STEP_MIN_TIME, IDLE_STEP_MAX_TIME)

        # -------- no motion behaviour --------
        else:
            no_motion_for = now - last_motion_time

            if (
                IDLE_SEARCH_ENABLED
                and (not search_phase_active)
                and (not center_lock_active)
                and no_motion_for >= IDLE_SEARCH_START_DELAY
            ):
                search_phase_active = True
                search_phase_start_time = now
                idle_next_switch_time = now

            if search_phase_active:
                elapsed_search = now - search_phase_start_time

                if elapsed_search < IDLE_SEARCH_DURATION:
                    if now >= idle_next_switch_time:
                        idle_target_x, idle_target_y = pick_idle_target()
                        idle_next_switch_time = now + random.uniform(IDLE_STEP_MIN_TIME, IDLE_STEP_MAX_TIME)

                    gx_smooth = (1 - IDLE_SMOOTH_ALPHA) * gx_smooth + IDLE_SMOOTH_ALPHA * idle_target_x
                    gy_smooth = (1 - IDLE_SMOOTH_ALPHA) * gy_smooth + IDLE_SMOOTH_ALPHA * idle_target_y

                    proposed_dir = direction_from_gaze(
                        gx_smooth, gy_smooth, DIR_THRESHOLD, DIAG_COMPONENT_THRESHOLD
                    )

                    if proposed_dir != current_dir and (now - last_dir_change_time) > DIRECTION_LAG:
                        current_dir = proposed_dir
                        last_dir_change_time = now
                else:
                    search_phase_active = False
                    center_lock_active = True

            if center_lock_active:
                gx_smooth *= (1 - CENTER_LOCK_ALPHA)
                gy_smooth *= (1 - CENTER_LOCK_ALPHA)

                proposed_dir = direction_from_gaze(
                    gx_smooth, gy_smooth, DIR_THRESHOLD, DIAG_COMPONENT_THRESHOLD
                )

                if proposed_dir == "center":
                    current_dir = "center"
                else:
                    if abs(gx_smooth) < DIR_THRESHOLD * 0.6 and abs(gy_smooth) < DIR_THRESHOLD * 0.6:
                        current_dir = "center"

        # -------- image selection --------
        if current_dir == "center":
            current_img = center_img
        elif current_dir == "left":
            current_img = left_img
        elif current_dir == "right":
            current_img = right_img
        elif current_dir == "up":
            current_img = up_img
        elif current_dir == "down":
            current_img = down_img
        elif current_dir == "up_left":
            current_img = up_left_img
        elif current_dir == "up_right":
            current_img = up_right_img
        elif current_dir == "down_left":
            current_img = down_left_img
        elif current_dir == "down_right":
            current_img = down_right_img
        else:
            current_img = center_img

        # -------- draw --------
        screen.fill(BG_COLOR)
        screen.blit(current_img, LEFT_EYE_POS)
        screen.blit(current_img, RIGHT_EYE_POS)
        pygame.display.flip()
        clock.tick(60)

finally:
    try:
        cap.release()
    except:
        pass

    try:
        if out is not None:
            out.release()
    except:
        pass

    pygame.quit()

    if record_consent and video_filename is not None:
        print(f"Recording saved: {os.path.abspath(video_filename)}")
    else:
        print("Program closed without saving a recording.")
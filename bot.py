import time
import cv2
import numpy as np
import pyautogui
from mss import mss
pyautogui.FAILSAFE = False

# =========================
# CONFIG
# =========================

CAPTURE_REGION = {
    "top": 100,
    "left": 100,
    "width": 2300,
    "height": 1200
}

SALVAGE_TEMPLATES = [
    "Templates/Salvage_1.png",
    "Templates/Salvage_2.png",
    "Templates/Salvage_3.png",
    "Templates/Salvage_4.png",
    "Templates/Salvage_5.png",
    "Templates/Salvage_6.png",
    "Templates/Salvage_7.png",
    "Templates/Salvage_8.png",
    "Templates/Salvage_9.png",
    "Templates/Salvage_10.png"
]

NOTIFICATION_TEMPLATES = [
    "notifications/Gathering_salvage.png",
    "notifications/Inventory_full.png"
]

IGNORE_TEMPLATES = [
    "Nono/Salvage_field.png"
]

TEMPLATE_THRESHOLD = 0.4
MINE_TIME = 1.5
STATUS_THRESHOLD = 0.8

sct = mss()

# =========================
# SCREEN CAPTURE
# =========================

def get_screen():
    img = sct.grab(CAPTURE_REGION)
    return np.array(img)

# =========================
# NODE DETECTION
# =========================

def find_node(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    for path in SALVAGE_TEMPLATES:
        template = cv2.imread(path, 0)
        if template is None:
            continue
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        print(f"{path} score: {max_val:.2f}")
        if max_val >= TEMPLATE_THRESHOLD:
            return True, max_loc
    return False, None

# =========================
# IGNORE NODE CHECK
# =========================

def is_ignored(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for path in IGNORE_TEMPLATES:
        template = cv2.imread(path, 0)
        if template is None:
            continue
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= TEMPLATE_THRESHOLD:
            print(f"Node genegeerd: {path} (score {max_val:.2f})")
            return True
    return False

# =========================
# STATUS CHECK (notifications)
# =========================

def check_status(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for notif in NOTIFICATION_TEMPLATES:
        template = cv2.imread(notif, 0)
        if template is None:
            continue
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= STATUS_THRESHOLD:
            if "Inventory_full" in notif:
                return "FULL"
            elif "Gathering_salvage" in notif:
                return "MINING"
    return "NONE"

# =========================
# ACTIONS
# =========================

def move_and_mine(node_pos, frame_shape):
    x, y = node_pos
    h, w = frame_shape[:2]

    # Beperk muisbeweging zodat hij niet in de fail-safe hoek komt
    dx = x - w // 2
    dy = y - h // 2
    dx = max(min(dx, 1000), -1000)  # limiet horizontaal
    dy = max(min(dy, 500), -500)    # limiet verticaal

    # Beweeg muis naar node
    pyautogui.moveRel(dx, dy, duration=0.15)

    # Loop vooruit
    pyautogui.keyDown("w")
    time.sleep(0.8)
    pyautogui.keyUp("w")

    # Mining
    pyautogui.mouseDown()
    time.sleep(MINE_TIME)
    pyautogui.mouseUp()

def deliver():
    pyautogui.keyDown("s")
    time.sleep(2)
    pyautogui.keyUp("s")
    pyautogui.press("e")
    time.sleep(0.5)
    pyautogui.click()
    time.sleep(1)

# =========================
# MAIN LOOP
# =========================

state = "SEARCH"
print("✅ Bot gestart — Druk CTRL+C om te stoppen")

try:
    while True:
        frame = get_screen()
        cv2.imshow("BOT VIEW", frame)
        cv2.waitKey(1)

        status = check_status(frame)

        if state == "SEARCH":
            found, pos = find_node(frame)
            if found:
                if not is_ignored(frame):
                    move_and_mine(pos, frame.shape)
                    state = "MINE"
                else:
                    print("Node genegeerd, blijft zoeken...")
                    pass
            else:
                pass  # blijft stil

        elif state == "MINE":
            if status == "FULL":
                state = "DELIVER"
            elif status == "MINING":
                print("🛠️ Bot blijft minen op deze node...")
                time.sleep(0.5)
            else:
                state = "SEARCH"

        elif state == "DELIVER":
            deliver()
            state = "SEARCH"

        time.sleep(0.1)

except KeyboardInterrupt:
    print("⛔ Bot gestopt")
    cv2.destroyAllWindows()

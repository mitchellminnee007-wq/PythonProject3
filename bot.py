import time
import cv2
import numpy as np
import pyautogui
from mss import mss
import pygetwindow as gw
pyautogui.FAILSAFE = False

# =========================
# CONFIG
# =========================

WINDOW_TITLE = "War"  # Target window name
CAPTURE_REGION = None  # Will be set dynamically based on window

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
# =======================q==

def get_window_region():
    """Find the War-Win64-Shipping window and return its region"""
    try:
        # First, try exact match
        windows = gw.getWindowsWithTitle(WINDOW_TITLE)
        
        # If not found, try partial match
        if not windows:
            all_windows = gw.getAllTitles()
            windows = [w for w in gw.getAllWindows() if WINDOW_TITLE in w.title]
            
            if not windows:
                print(f"⚠️ Window containing '{WINDOW_TITLE}' not found!")
                print("Available windows:")
                for title in all_windows:
                    if title.strip():  # Only show non-empty titles
                        print(f"  - {title}")
                return None
        
        win = windows[0]
        print(f"✅ Found window: {win.title}")
        
        if win.isMinimized:
            win.restore()
        
        return {
            "top": win.top,
            "left": win.left,
            "width": win.width,
            "height": win.height
        }
    except Exception as e:
        print(f"Error finding window: {e}")
        return None

def get_screen():
    global CAPTURE_REGION
    
    # Update capture region to match the window
    region = get_window_region()
    if region is None:
        print(f"Cannot find '{WINDOW_TITLE}' window. Make sure it's open.")
        return None
    
    CAPTURE_REGION = region
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

    # Calculate position relative to center
    center_x = w // 2
    center_y = h // 2
    
    dx = x - center_x
    dy = y - center_y
    
    # Determine movement direction based on node position
    # Custom keybinds: up=z, down=s, left=q, right=d
    move_duration = 0.8
    
    # Determine which keys to press (can be multiple for diagonal movement)
    keys_to_press = []
    
    # Horizontal movement
    if abs(dx) > 50:  # threshold to avoid tiny movements
        if dx > 0:  # node is to the right
            keys_to_press.append("d")
        else:  # node is to the left
            keys_to_press.append("q")
    
    # Vertical movement
    if abs(dy) > 50:  # threshold to avoid tiny movements
        if dy > 0:  # node is below center (move down)
            keys_to_press.append("s")
        else:  # node is above center (move up)
            keys_to_press.append("z")
    
    # Press all movement keys simultaneously
    if keys_to_press:
        print(f"Moving towards node using keys: {keys_to_press}")
        for key in keys_to_press:
            pyautogui.keyDown(key)
        time.sleep(move_duration)
        for key in keys_to_press:
            pyautogui.keyUp(key)

    # Mining
    pyautogui.mouseDown()
    time.sleep(MINE_TIME)
    pyautogui.mouseUp()

def deliver():
    pyautogui.keyDown("s")
    time.sleep(2)
    pyautogui.keyUp("s")
    pyautogui.press("w")
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
        if frame is None:
            print("Waiting for window...")
            time.sleep(2)
            continue

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

import time
import cv2
import numpy as np
import pyautogui
from mss import mss
import pygetwindow as gw
import argparse
pyautogui.FAILSAFE = False

# =========================
# CONFIG
# =========================

WINDOW_TITLE = "War"  # Target window name
CAPTURE_REGION = None  # Will be set dynamically based on window

SALVAGE_TEMPLATES = [
    "Templates/T1-GL1.png",
    "Templates/T1-GL2.png",
    "Templates/T1-GL3.png",
    "Templates/T1-GL4.png",
    "Templates/T1-GL5.png",
    "Templates/T1-GL6.png",
    "Templates/T2-GL1.png",
    "Templates/T2-GL2.png",
    "Templates/T2-GL3.png",
    "Templates/T2-GL4.png",
    "Templates/T2-GL5.png",
    "Templates/T2-GL6.png",
    "Templates/T3-GL1.png",
    "Templates/T3-GL2.png",
    "Templates/T3-GL3.png",
    "Templates/T3-GL4.png",
    "Templates/T3-GL5.png",
    "Templates/T3-GL6.png"
]

NOTIFICATION_TEMPLATES = [
    "notifications/Gathering_salvage.png",
    "notifications/Inventory_full.png"
]

IGNORE_TEMPLATES = [
    "Nono/Salvage_field.png",
    "Nono/Big_Node.png",
    "Nono/Grass.png"
]

CHARACTER_TEMPLATE = "notifications/Character.png"

TEMPLATE_THRESHOLD = 0.4
MINE_TIME = 1.5
STATUS_THRESHOLD = 0.8
THRESH_VALUE = 60  # Binary threshold for hard grayscaling (0-255)
CLAHE_CLIP_LIMIT = 2.0  # CLAHE contrast enhancement (1.0-4.0 range typical)
SEARCH_RADIUS = 50  # Max distance from character to target node (pixels)

# =========================
# COMMAND-LINE ARGUMENTS
# =========================
def parse_args():
    parser = argparse.ArgumentParser(description='Resource gathering bot')
    parser.add_argument('--thresh', type=int, default=THRESH_VALUE,
                        help=f'Binary threshold value (0-255, default: {THRESH_VALUE})')
    parser.add_argument('--clahe', type=float, default=CLAHE_CLIP_LIMIT,
                        help=f'CLAHE clip limit for grayscale enhancement (default: {CLAHE_CLIP_LIMIT})')
    return parser.parse_args()

args = parse_args()
THRESH_VALUE = args.thresh
CLAHE_CLIP_LIMIT = args.clahe
RADIUS_EXPANSION = 50  # How much to expand radius each time no node found

# No fixed square boundary; use character-relative radius only

sct = mss()

# Fixed search radius

# Cache templates to avoid loading every frame
template_cache = {}
for path in SALVAGE_TEMPLATES + NOTIFICATION_TEMPLATES + IGNORE_TEMPLATES + [CHARACTER_TEMPLATE]:
    img = cv2.imread(path, 0)  # Load plain grayscale
    if img is None:
        continue
    template_cache[path] = img

# =========================
# SCREEN CAPTURE
# =======================q==

window_region_cache = None
region_update_counter = 0

def get_window_region():
    """Find the War-Win64-Shipping window and return its region"""
    global window_region_cache, region_update_counter
    
    # Use cached region and only update every 100 frames for speed
    if window_region_cache is not None and region_update_counter < 50:
        region_update_counter += 1
        return window_region_cache
    
    try:
        # First, try exact match
        windows = gw.getWindowsWithTitle(WINDOW_TITLE)
        
        # If not found, try partial match
        if not windows:
            all_windows = gw.getAllTitles()
            windows = [w for w in gw.getAllWindows() if WINDOW_TITLE in w.title]
            
            if not windows:
                print(f"⚠️ Window containing '{WINDOW_TITLE}' not found!")
                return None
        
        win = windows[0]
        if region_update_counter >= 100:
            region_update_counter = 0
        
        if win.isMinimized:
            win.restore()
        
        window_region_cache = {
            "top": win.top,
            "left": win.left,
            "width": win.width,
            "height": win.height
        }
        return window_region_cache
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
    bgr_img = np.array(img)
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    return gray

# =========================
# CHARACTER DETECTION
# =========================

def find_character(frame):
    """Find the character position on screen"""
    template = template_cache.get(CHARACTER_TEMPLATE)
    if template is None:
        print("⚠️ Character template not found!")
        return None
    
    res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= 0.6:  # Lower threshold for character detection
        # Return center of character template
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        return (center_x, center_y)
    
    return None

# =========================
# NODE DETECTION
# =========================

def find_node(frame):
    # Frame is already grayscale from get_screen()
    
    # First, find the character position
    char_pos = find_character(frame)
    
    # Find ALL nodes and their distances, then select the closest one
    nodes_found = []  # List of (score, location, template_path, distance, template, w, h)

    for path in SALVAGE_TEMPLATES:
        template = template_cache.get(path)
        if template is None:
            continue
        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= TEMPLATE_THRESHOLD:
            h, w = template.shape[:2]
            node_center_x = max_loc[0] + w // 2
            node_center_y = max_loc[1] + h // 2
            
            # Calculate distance from character to this node
            if char_pos is not None:
                distance = ((node_center_x - char_pos[0])**2 + (node_center_y - char_pos[1])**2)**0.5
            else:
                distance = 0  # If no character found, accept any node
            
            nodes_found.append((max_val, max_loc, path, distance, template, w, h))
    
    # If nodes were found, select the closest one within search radius
    if nodes_found:
        # Sort by distance (closest first)
        nodes_found.sort(key=lambda x: x[3])
        
        # Find the closest node within search radius from character
        for score, loc, path, distance, template, w, h in nodes_found:
            if char_pos is None or distance <= SEARCH_RADIUS:
                print(f"✅ Found closest node within radius: {path} score: {score:.2f}, distance: {distance:.0f}px (radius: {SEARCH_RADIUS}px)")
                return True, (loc, w, h)
        
        # If we're here, all nodes are beyond search radius
        closest_distance = nodes_found[0][3]
        print(f"⚠️ Closest node too far: {closest_distance:.0f}px (radius: {SEARCH_RADIUS}px)")
        return False, None
    
    return False, None

def is_node_still_visible(frame, node_pos):
    """Check if a node at a specific position is still visible"""
    if node_pos is None:
        return False
    
    x, y = node_pos
    
    # Check each template at this approximate location
    for path in SALVAGE_TEMPLATES:
        template = template_cache.get(path)
        if template is None:
            continue
        h, w = template.shape[:2]
        # Refined search in a small ROI to keep lock on same node
        x0 = max(x - 64, 0)
        y0 = max(y - 64, 0)
        x1 = min(x + 64, frame.shape[1] - w)
        y1 = min(y + 64, frame.shape[0] - h)
        roi = frame[y0:y1 + h, x0:x1 + w]
        if roi.size == 0:
            continue
        res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= TEMPLATE_THRESHOLD:
            center_x = x0 + max_loc[0] + w // 2
            center_y = y0 + max_loc[1] + h // 2
            if abs(center_x - x) <= 50 and abs(center_y - y) <= 50:
                return True
    
    return False

def refine_node_position(frame, last_pos):
    """Refine and update node position around last_pos to keep lock on the same node."""
    if last_pos is None:
        return None
    x, y = last_pos
    best = None  # (score, (loc, w, h))
    for path in SALVAGE_TEMPLATES:
        template = template_cache.get(path)
        if template is None:
            continue
        h, w = template.shape[:2]
        x0 = max(x - 64, 0)
        y0 = max(y - 64, 0)
        x1 = min(x + 64, frame.shape[1] - w)
        y1 = min(y + 64, frame.shape[0] - h)
        roi = frame[y0:y1 + h, x0:x1 + w]
        if roi.size == 0:
            continue
        res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= TEMPLATE_THRESHOLD:
            loc_global = (x0 + max_loc[0], y0 + max_loc[1])
            if best is None or max_val > best[0]:
                best = (max_val, (loc_global, w, h))
    return best[1] if best else None

# =========================
# IGNORE NODE CHECK
# =========================

def is_ignored(frame):
    # Frame is already grayscale from get_screen()
    for path in IGNORE_TEMPLATES:
        template = template_cache.get(path)
        if template is None:
            continue
        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= TEMPLATE_THRESHOLD:
            print(f"Node genegeerd: {path} (score {max_val:.2f})")
            return True
    return False

# =========================
# STATUS CHECK (notifications)
# =========================

def check_status(frame):
    # Frame is already grayscale from get_screen()
    for notif in NOTIFICATION_TEMPLATES:
        template = template_cache.get(notif)
        if template is None:
            continue
        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
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

def move_and_mine(node_data, frame_shape):
    # Extract node center position from node_data
    if isinstance(node_data, tuple) and len(node_data) == 3:
        # node_data is (top_left_pos, width, height)
        pos, w_template, h_template = node_data
        # Calculate node center
        node_center_x = pos[0] + w_template // 2
        node_center_y = pos[1] + h_template // 2
    else:
        # Fallback: node_data is just a position
        node_center_x, node_center_y = node_data
    
    h, w = frame_shape[:2]

    # Calculate position relative to screen center
    center_x = w // 2
    center_y = h // 2
    
    # Calculate direction from screen center to node center
    dx = node_center_x - center_x
    dy = node_center_y - center_y
    
    # Calculate distance to node
    distance = (dx**2 + dy**2)**0.5
    
    # Determine movement direction based on node position
    # Custom keybinds: up=z, down=s, left=q, right=d
    # Move longer for farther nodes
    move_duration = min(2.0, 0.5 + (distance / 400))
    
    # Determine which keys to press (can be multiple for diagonal movement)
    keys_to_press = []
    
    # Horizontal movement
    if abs(dx) > 30:  # lower threshold for better accuracy
        if dx > 0:  # node is to the right
            keys_to_press.append("d")
        else:  # node is to the left
            keys_to_press.append("q")
    
    # Vertical movement
    if abs(dy) > 30:  # lower threshold for better accuracy
        if dy > 0:  # node is below center (move down)
            keys_to_press.append("s")
        else:  # node is above center (move up)
            keys_to_press.append("z")
    
    # Press all movement keys simultaneously - run to the node
    if keys_to_press:
        print(f"Running to node (distance: {distance:.0f}px) using keys: {keys_to_press}")
        frame = get_screen()  # Screenshot before movement
        display_frame = cv2.resize(frame, (800, 800))
        cv2.imshow("Bot Detection", display_frame)
        cv2.waitKey(1)
        for key in keys_to_press:
            pyautogui.keyDown(key)
        time.sleep(move_duration)
        for key in keys_to_press:
            pyautogui.keyUp(key)
        
        # Small pause to stabilize
        time.sleep(0.3)
        frame = get_screen()  # Screenshot after movement
        display_frame = cv2.resize(frame, (800, 800))
        cv2.imshow("Bot Detection", display_frame)
        cv2.waitKey(1)

    # Start mining
    print("Starting mining...")
    frame = get_screen()  # Screenshot before mining
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)
    pyautogui.mouseDown()
    time.sleep(MINE_TIME)
    pyautogui.mouseUp()
    frame = get_screen()  # Screenshot after mining
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)

def deliver():
    frame = get_screen()  # Screenshot before movement
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)
    pyautogui.keyDown("s")
    time.sleep(2)
    pyautogui.keyUp("s")
    frame = get_screen()  # Screenshot after movement
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)
    pyautogui.press("w")
    time.sleep(0.5)
    frame = get_screen()  # Screenshot before click
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)
    pyautogui.click()
    time.sleep(1)
    frame = get_screen()  # Screenshot after click
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)

def explore():
    """Move to explore within boundary and find nodes"""
    import random
    
    directions = {
        "z": ("up", 0, -1),
        "s": ("down", 0, 1), 
        "q": ("left", -1, 0),
        "d": ("right", 1, 0)
    }
    
    frame = get_screen()  # Screenshot before movement
    if frame is None:
        return
    
    # Pick any direction; boundary enforcement is approximate due to unknown exact position
    key, (direction, _, _) = random.choice(list(directions.items()))
    print(f"🔍 No node found, exploring {direction} within boundary...")
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)
    pyautogui.keyDown(key)
    time.sleep(1)
    pyautogui.keyUp(key)
    frame = get_screen()  # Screenshot after movement
    display_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Bot Detection", display_frame)
    cv2.waitKey(1)

# =========================
# MAIN LOOP
# =========================
state = "SEARCH"
miss_count = 0  # consecutive frames without node while mining
status_miss_count = 0  # consecutive frames without Gathering_salvage while mining
last_node_pos = None  # track last known node position
last_node_data = None  # track last detected node data for persistent display
window_initialized = False  # track if display window is set up

# Frame rate control for 120 FPS
TARGET_FPS = 120
FRAME_TIME = 1.0 / TARGET_FPS  # 0.0083 seconds per frame

print("✅ Bot gestart — Druk CTRL+C om te stoppen")

try:
    while True:
        frame_start_time = time.time()
        frame = get_screen()
        if frame is None:
            print("Waiting for window...")
            time.sleep(2)
            continue

        # Check for nodes to draw rectangles
        found, node_data = find_node(frame)
        
        # Display frame on right monitor with 800x800 size (convert grayscale to BGR for drawing)
        display_frame = cv2.resize(frame, (800, 800))
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
        
        # Update persistent node data if new node found
        if found:
            last_node_data = node_data
        
        # Draw red rectangle around detected node (use persistent data)
        if last_node_data:
            # Try to refine the node position to keep lock even after movement
            refined = refine_node_position(frame, (last_node_data[0][0] + last_node_data[1] // 2,
                                                  last_node_data[0][1] + last_node_data[2] // 2))
            if refined:
                last_node_data = refined
            pos, w, h = last_node_data
            # Scale rectangle to match resized display and make it smaller
            scale_x = 800 / frame.shape[1]
            scale_y = 800 / frame.shape[0]
            # Reduce rectangle size to 40% of template (smaller box)
            w_reduced = int(w * 0.4)
            h_reduced = int(h * 0.4)
            offset_x = (w - w_reduced) // 2
            offset_y = (h - h_reduced) // 2
            x1 = int((pos[0] + offset_x) * scale_x)
            y1 = int((pos[1] + offset_y) * scale_y)
            x2 = int((pos[0] + offset_x + w_reduced) * scale_x)
            y2 = int((pos[1] + offset_y + h_reduced) * scale_y)
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 1)
        
        cv2.imshow("Bot Detection", display_frame)
        
        # Initialize window position on first run
        if not window_initialized:
            try:
                # Move to right monitor (adjust 1920 if your main monitor has different width)
                cv2.moveWindow("Bot Detection", 1920, 100)
                window_initialized = True
            except:
                pass
        
        cv2.waitKey(1)

        status = check_status(frame)

        if state == "SEARCH":
            # If we're already gathering, don't move — keep mining
            if status == "MINING":
                print("⛏️ Already gathering — hammering instead of moving...")
                frame = get_screen()  # Fresh screenshot before action
                pyautogui.mouseDown()
                time.sleep(0.2)
                pyautogui.mouseUp()
                time.sleep(0.1)
                frame = get_screen()  # Screenshot during hammer to verify status
                display_frame = cv2.resize(frame, (800, 800))
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                cv2.imshow("Bot Detection", display_frame)
                cv2.waitKey(1)
                status = check_status(frame)
                if status == "MINING":
                    print("✅ Gathering status confirmed during hammer")
                else:
                    print("⚠️ Gathering status not detected after hammer")
            else:
                found, node_data = find_node(frame)
                if found:
                    if not is_ignored(frame):
                        pos, w, h = node_data
                        print(f"✅ Node detected at position {pos}, moving towards it...")
                        
                        # Draw red rectangle on display
                        display_frame = cv2.resize(frame, (800, 800))
                        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                        # Scale rectangle to match resized display and make it smaller
                        scale_x = 800 / frame.shape[1]
                        scale_y = 800 / frame.shape[0]
                        # Reduce rectangle size by 30%
                        w_reduced = int(w * 0.7)
                        h_reduced = int(h * 0.7)
                        offset_x = (w - w_reduced) // 2
                        offset_y = (h - h_reduced) // 2
                        x1 = int((pos[0] + offset_x) * scale_x)
                        y1 = int((pos[1] + offset_y) * scale_y)
                        x2 = int((pos[0] + offset_x + w_reduced) * scale_x)
                        y2 = int((pos[1] + offset_y + h_reduced) * scale_y)
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 1)
                        cv2.imshow("Bot Detection", display_frame)
                        cv2.waitKey(1)
                        
                        last_node_pos = pos
                        move_and_mine(node_data, frame.shape)
                        frame = get_screen()  # Screenshot after move_and_mine
                        display_frame = cv2.resize(frame, (800, 800))
                        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                        cv2.imshow("Bot Detection", display_frame)
                        cv2.waitKey(1)
                        state = "MINE"
                    else:
                        print("Nozde genegeerd, blijft zoeken...")
                        explore()
                        frame = get_screen()  # Screenshot after explore
                        display_frame = cv2.resize(frame, (800, 800))
                        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                        cv2.imshow("Bot Detection", display_frame)
                        cv2.waitKey(1)
                else:
                    # No node visible, explore randomly to find one
                    explore()
                    frame = get_screen()  # Screenshot after explore
                    display_frame = cv2.resize(frame, (800, 800))
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                    cv2.imshow("Bot Detection", display_frame)
                    cv2.waitKey(1)

        elif state == "MINE":
            # Priority 1: Check if inventory is full
            if status == "FULL":
                state = "DELIVER"
                miss_count = 0
                status_miss_count = 0
                last_node_pos = None
            # Priority 2: Check if current node is still visible - stay and mine it
            elif is_node_still_visible(frame, last_node_pos):
                print("⛏️ Current node still visible - continuing to mine...")
                frame = get_screen()  # Fresh screenshot before action
                pyautogui.mouseDown()
                time.sleep(0.2)
                pyautogui.mouseUp()
                time.sleep(0.1)
                frame = get_screen()  # Screenshot during hammer to verify status
                display_frame = cv2.resize(frame, (800, 800))
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                cv2.imshow("Bot Detection", display_frame)
                cv2.waitKey(1)
                status = check_status(frame)
                if status == "MINING":
                    print("✅ Still gathering - staying on node")
                    miss_count = 0
                    status_miss_count = 0
                else:
                    print("⚠️ Gathering status no longer detected")
                    status_miss_count += 1
            # Priority 3: Current node gone, check if another node is available
            else:
                found, node_data = find_node(frame)
                if found and not is_ignored(frame):
                    print(f"✅ Current node depleted - moving to new node...")
                    
                    last_node_pos = node_data[0]
                    move_and_mine(node_data, frame.shape)
                    frame = get_screen()  # Screenshot after move_and_mine
                    display_frame = cv2.resize(frame, (800, 800))
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                    cv2.imshow("Bot Detection", display_frame)
                    cv2.waitKey(1)
                # Priority 4: If "Gathering Salvage..." is showing, keep mining current node
                elif status == "MINING":
                    print("⛏️ Gathering salvage detected - continuing to hammer...")
                    frame = get_screen()  # Fresh screenshot before action
                    pyautogui.mouseDown()
                    time.sleep(0.2)
                    pyautogui.mouseUp()
                    time.sleep(0.1)
                    frame = get_screen()  # Screenshot during hammer to verify status
                    display_frame = cv2.resize(frame, (800, 800))
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                    cv2.imshow("Bot Detection", display_frame)
                    cv2.waitKey(1)
                    status = check_status(frame)
                    if status == "MINING":
                        print("✅ Still gathering - staying on node")
                        miss_count = 0
                        status_miss_count = 0
                    else:
                        print("⚠️ Gathering status no longer detected")
                        status_miss_count += 1
                # Priority 5: No gathering status and no new nodes - wait or give up
                else:
                    # Keep hammering for a few frames in case gathering notification is delayed
                    status_miss_count += 1
                    print(f"⚠️ No gathering status detected (miss {status_miss_count}/60)")
                    
                    # Only leave if gathering status has been missing for 60+ consecutive frames
                    if status_miss_count >= 60:
                        print("✅ Gathering stopped - node depleted, returning to search...")
                        state = "SEARCH"
                        miss_count = 0
                        status_miss_count = 0
                        last_node_pos = None
                        last_node_data = None  # Clear persistent node display
                    else:
                        # Continue hammering while waiting for gathering status
                        print(f"⛏️ Continuing to hammer (waiting for gathering status)...")
                        frame = get_screen()  # Fresh screenshot before action
                        pyautogui.mouseDown()
                        time.sleep(0.2)
                        pyautogui.mouseUp()
                        time.sleep(0.1)
                        frame = get_screen()  # Screenshot during hammer to verify status
                        display_frame = cv2.resize(frame, (800, 800))
                        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
                        cv2.imshow("Bot Detection", display_frame)
                        cv2.waitKey(1)

        elif state == "DELIVER":
            deliver()
            frame = get_screen()  # Screenshot after deliver
            display_frame = cv2.resize(frame, (800, 800))
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
            cv2.imshow("Bot Detection", display_frame)
            cv2.waitKey(1)
            state = "SEARCH"
            last_node_data = None  # Clear persistent node display
        # Frame rate control - sleep for remaining time to achieve 30 FPS
        elapsed_time = time.time() - frame_start_time
        sleep_time = FRAME_TIME - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    print("⛔ Bot gestopt")
    cv2.destroyAllWindows()

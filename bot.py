import time
import cv2
import numpy as np
import pyautogui
import requests
from mss import mss
import json
import pygetwindow as gw
pyautogui.FAILSAFE = False

# =========================
# CONFIG
# =========================

# =========================
# FOXHOLE WINDOW DETECTION
# =========================

def get_foxhole_window():
    """
    Automatically detects the Foxhole (War-Win64-Shipping.exe) window and returns its coordinates.
    """
    try:
        # Try to find War-Win64-Shipping window
        windows = gw.getWindowsWithTitle("War")
        if windows:
            window = windows[0]
            # Un-minimize window if it's minimized
            if window.isMinimized:
                window.restore()
            print(f"✅ Detected Foxhole window: {window.title}")
            print(f"   Position: ({window.left}, {window.top}) | Size: {window.width}x{window.height}")
            return {
                "top": window.top,
                "left": window.left,
                "width": window.width,
                "height": window.height
            }
        else:
            print("⚠️ War-Win64-Shipping.exe window not found. Using default capture region.")
            return {
                "top": 100,
                "left": 100,
                "width": 2300,
                "height": 1200
            }
    except Exception as e:
        print(f"⚠️ Error detecting Foxhole window: {e}")
        print("   Using default capture region.")
        return {
            "top": 100,
            "left": 100,
            "width": 2300,
            "height": 1200
        }

CAPTURE_REGION = get_foxhole_window()

# Discord Webhook
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1493763164960063598/sCvNFZGarHxsc1OQ5YRT5xFvJiLI7pM0LpD6owHYdAVDW0PnvJU9I8Vzk8v_cNEOxJFX"

# Blue color detection (HSV range for blue)
# OpenCV uses H: 0-180, S: 0-255, V: 0-255
BLUE_LOWER = np.array([100, 80, 120])    # Lower bound for blue (lighter blues)
BLUE_UPPER = np.array([135, 255, 255])   # Upper bound for blue (wider range)

# Green color detection (to exclude)
GREEN_LOWER = np.array([35, 80, 80])     # Lower bound for green
GREEN_UPPER = np.array([85, 255, 255])   # Upper bound for green

MIN_BLUE_AREA = 30  # Minimum pixel area to count as a blue dot (very small for tiny dots)
MAX_BLUE_AREA = 50000  # Maximum pixel area

# Ignore templates (blue objects to skip)
IGNORE_TEMPLATES = [
    "Nono/Legend.png",
    "Nono/StateOfWar.png",
    "Nono/green dot.png",
    "Nono/water icon.png"
]

sct = mss()

# =========================
# SCREEN CAPTURE
# =========================

def get_screen():
    img = sct.grab(CAPTURE_REGION)
    return np.array(img)

# =========================
# BLUE DOT/PLANE DETECTION
# =========================

def find_blue_objects(frame):
    """
    Detects blue dots/planes on the map using HSV color detection.
    Excludes green colors.
    Returns list of (x, y, area) tuples for each blue object found.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create mask for blue colors
    blue_mask = cv2.inRange(hsv, BLUE_LOWER, BLUE_UPPER)
    
    # Create mask for green colors (to exclude)
    green_mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)
    
    # Subtract green from blue (keep only blue, not green)
    mask = cv2.subtract(blue_mask, green_mask)
    
    # Apply morphological operations to clean up the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    blue_objects = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if MIN_BLUE_AREA <= area <= MAX_BLUE_AREA:
            M = cv2.moments(contour)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                blue_objects.append((cx, cy, area))
    
    return blue_objects

# =========================
# IGNORE CHECK
# =========================

def should_ignore_region(frame, x, y, area, ignore_threshold=0.3):
    """
    Checks if a blue object matches any of the ignore templates.
    Returns True if it should be ignored.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Extract region around the detected blue object
    h, w = frame.shape[:2]
    size = int(np.sqrt(area)) + 30  # Larger extraction area
    x1 = max(0, x - size // 2)
    y1 = max(0, y - size // 2)
    x2 = min(w, x + size // 2)
    y2 = min(h, y + size // 2)
    
    region = gray[y1:y2, x1:x2]
    if region.size == 0:
        return False
    
    # Check against ignore templates
    for ignore_path in IGNORE_TEMPLATES:
        template = cv2.imread(ignore_path, 0)
        if template is None:
            continue
        
        # Resize template to match region size
        template_resized = cv2.resize(template, (region.shape[1], region.shape[0]))
        
        # Calculate similarity
        res = cv2.matchTemplate(region, template_resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        
        if max_val >= ignore_threshold:
            print(f"🚫 Ignored at ({x}, {y}): {ignore_path} (match: {max_val:.2f})")
            return True
    
    return False


def send_discord_notification(blue_objects, frame, frame_shape):
    """
    Sends a Discord notification with blue object count and locations.
    Includes screenshot with bounding boxes around detected blue dots.
    """
    if not blue_objects:
        print("⚠️ No valid blue objects to send")
        return
    
    count = len(blue_objects)
    print(f"📸 Creating annotated screenshot with {count} blue objects...")
    
    # Create a copy of the frame to draw on
    annotated_frame = frame.copy()
    
    # Draw UI region boundary box (the area being ignored)
    ui_x_max = 500
    ui_y_max = 400
    cv2.rectangle(annotated_frame, (0, 0), (ui_x_max, ui_y_max), (0, 165, 255), 3)  # Orange box
    cv2.putText(annotated_frame, "IGNORED UI REGION", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    
    print(f"   Frame size: {annotated_frame.shape}")
    
    # Draw rectangles around each blue object
    for idx, (x, y, area) in enumerate(blue_objects):
        print(f"   Drawing box #{idx+1} at ({x}, {y}), area={area}")
        
        size = int(np.sqrt(area)) + 10
        x1 = max(0, x - size // 2)
        y1 = max(0, y - size // 2)
        x2 = min(frame_shape[1], x + size // 2)
        y2 = min(frame_shape[0], y + size // 2)
        
        print(f"      Box coords: ({x1}, {y1}) to ({x2}, {y2})")
        
        # Draw purple rectangle around blue dot
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 255), 4)
        # Draw yellow circle at center
        cv2.circle(annotated_frame, (x, y), 10, (0, 255, 255), -1)
    
    # Save annotated screenshot
    image_path = "blue_detection_screenshot.png"
    cv2.imwrite(image_path, annotated_frame)
    print(f"   Screenshot saved: {image_path}")
    
    locations = ", ".join([f"({x}, {y})" for x, y, _ in blue_objects[:5]])
    
    # Create Discord message with embed
    embed = {
        "title": "🔵 Blue Dots/Planes Detected!",
        "description": f"Found **{count}** blue object(s) on the map",
        "color": 3447003,  # Blue color
        "fields": [
            {
                "name": "Locations",
                "value": locations if count <= 5 else f"{locations} + {count - 5} more",
                "inline": False
            },
            {
                "name": "Count",
                "value": str(count),
                "inline": True
            }
        ]
    }
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        # Send with image attachment
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                DISCORD_WEBHOOK, 
                data={"payload_json": json.dumps(payload)}, 
                files=files
            )
        
        if response.status_code in [200, 204]:
            print(f"✅ Discord notification sent! ({count} blue objects with image)")
        else:
            print(f"⚠️ Discord notification failed: {response.status_code}")
            print(f"   Response: {response.text[:100]}")
    except Exception as e:
        print(f"❌ Error sending Discord message: {e}")


# =========================
# ACTIONS (Optional)
# =========================

def move_to_blue_object(x, y):
    """
    Moves mouse to a detected blue object.
    """
    frame = get_screen()
    h, w = frame.shape[:2]
    
    dx = x - w // 2
    dy = y - h // 2
    dx = max(min(dx, 1000), -1000)
    dy = max(min(dy, 500), -500)
    
    pyautogui.moveRel(dx, dy, duration=0.2)
    print(f"🎯 Tracking blue dot at ({x}, {y})")


# =========================
# MAIN LOOP
# =========================

last_notification_time = 0
last_status_log_time = 0
NOTIFICATION_COOLDOWN = 30  # Send Discord notification every 30 seconds when blue dots detected
STATUS_LOG_INTERVAL = 120  # Send status log every 2 minutes (120 seconds)
frame_count = 0
total_blue_detected = 0

def send_status_log(frame_count, total_blue_detected):
    """
    Sends a status log to Discord every 2 minutes to confirm bot is running.
    """
    embed = {
        "title": "🤖 Bot Status Log",
        "description": "Bot is running and monitoring for blue objects",
        "color": 65280,  # Green color
        "fields": [
            {
                "name": "Frames Processed",
                "value": str(frame_count),
                "inline": True
            },
            {
                "name": "Total Blue Objects Detected",
                "value": str(total_blue_detected),
                "inline": True
            },
            {
                "name": "Timestamp",
                "value": f"<t:{int(time.time())}:F>",
                "inline": False
            }
        ]
    }
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload)
        if response.status_code == 204:
            print(f"✅ Status log sent! (Frames: {frame_count}, Blue objects detected: {total_blue_detected})")
        else:
            print(f"⚠️ Status log failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending status log: {e}")

print("✅ Bot gestart — Druk CTRL+C om te stoppen")
print("🔍 Scanning for blue dots/planes on the map...")
print("📊 Status log will be sent every 2 minutes")
print("🖥️ Detection window disabled - monitoring in background")

# Create window and lock its position (disabled)
# cv2.namedWindow("BOT VIEW - Blue Detection", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("BOT VIEW - Blue Detection", 1200, 800)
# cv2.moveWindow("BOT VIEW - Blue Detection", 0, 0)

try:
    while True:
        frame = get_screen()
        
        frame_count += 1
        
        # Detect blue objects
        blue_objects = find_blue_objects(frame)
        
        # Debug: Show detection info
        if frame_count % 30 == 0:  # Print every 30 frames (roughly every 3 seconds)
            print(f"📊 [Frame {frame_count}] Raw detections: {len(blue_objects)} objects")
            for idx, (x, y, area) in enumerate(blue_objects):
                print(f"   [{idx+1}] Position: ({x}, {y}), Area: {area}")
        
        # Create display frame with annotations
        display_frame = frame.copy()
        
        # Filter out ignored objects
        valid_blue_objects = []
        ignored_count = 0
        for x, y, area in blue_objects:
            # Ignore UI regions (top-left area where Legend/State of War are)
            # Expanded boundaries to catch more UI elements
            if x < 500 and y < 400:
                ignored_count += 1
                if frame_count % 30 == 0:
                    print(f"   🚫 Ignored UI element at ({x}, {y})")
                continue
            
            if not should_ignore_region(frame, x, y, area):
                valid_blue_objects.append((x, y, area))
            else:
                ignored_count += 1
        
        if frame_count % 30 == 0:
            if ignored_count > 0:
                print(f"   ⚠️ {ignored_count} object(s) filtered out (ignored templates)")
            if valid_blue_objects:
                print(f"   ✅ Valid detections: {len(valid_blue_objects)}")
        
        # Draw squares around all detected blue objects on display frame
        for x, y, area in valid_blue_objects:
            size = int(np.sqrt(area)) + 10
            x1 = max(0, x - size // 2)
            y1 = max(0, y - size // 2)
            x2 = min(frame.shape[1], x + size // 2)
            y2 = min(frame.shape[0], y + size // 2)
            
            # Draw green square around blue dot
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Draw yellow circle at center
            cv2.circle(display_frame, (x, y), 5, (0, 255, 255), -1)
        
        # Don't display window on screen
        # cv2.imshow("BOT VIEW - Blue Detection", display_frame)
        # cv2.moveWindow("BOT VIEW - Blue Detection", 0, 0)
        # cv2.waitKey(1)
        
        if valid_blue_objects:
            total_blue_detected += len(valid_blue_objects)
            print(f"🔵 Found {len(valid_blue_objects)} valid blue object(s)!")
            
            # Don't move cursor, just mark with square and notify Discord
            # if valid_blue_objects:
            #     closest_dot = valid_blue_objects[0]
            #     x, y, area = closest_dot
            #     move_to_blue_object(x, y)
            
            # Send Discord notification with cooldown
            current_time = time.time()
            if current_time - last_notification_time >= NOTIFICATION_COOLDOWN:
                send_discord_notification(valid_blue_objects, frame, frame.shape)
                last_notification_time = current_time
        
        # Send status log every 2 minutes
        current_time = time.time()
        if current_time - last_status_log_time >= STATUS_LOG_INTERVAL:
            send_status_log(frame_count, total_blue_detected)
            last_status_log_time = current_time
            frame_count = 0  # Reset frame count for next interval
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("⛔ Bot stopped")
    # cv2.destroyAllWindows()


import subprocess
import time

def get_wechat_window():
    # Get WeChat window ID
    wid = subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--class", "wechat"]
    ).decode().splitlines()[0]

    # Get window position (absolute screen X,Y)
    geom = subprocess.check_output(
        ["xdotool", "getwindowgeometry", wid]
    ).decode()

    for line in geom.splitlines():
        if "Position:" in line:
            pos = line.split()[1]
            win_x, win_y = pos.split(',')
            return int(win_x), int(win_y), wid

print("=== WECHAT RELATIVE COORDINATE TOOL ===")
print("1. Make sure WeChat is open")
print("2. Click INSIDE WECHAT on the SEARCH BOX")
print("3. Press ENTER in terminal\n")

# Wait for you to confirm you clicked
input("Press ENTER after you CLICK the WeChat search box...")

# Get WeChat window position
win_x, win_y, _ = get_wechat_window()

# Get your mouse absolute position
mouse = subprocess.check_output(["xdotool", "getmouselocation"]).decode()
parts = mouse.split()
abs_x = int(parts[0].split(':')[1])
abs_y = int(parts[1].split(':')[1])

# Calculate RELATIVE coordinates
rel_x = abs_x - win_x
rel_y = abs_y - win_y

print("\n" + "="*60)
print("✅ YOUR WECHAT RELATIVE SEARCH BOX COORDINATES:")
print(f"REL_X = {rel_x}")
print(f"REL_Y = {rel_y}")
print("="*60)

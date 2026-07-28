import subprocess
import time

print("=== WECHAT SEARCH BOX LOCATOR (FIXED) ===")
print("✅ Instructions:")
print("1. Open WeChat")
print("2. Move mouse to the TOP GLOBAL SEARCH BOX (magnifying glass)")
print("3. LEFT CLICK once right there")
print("Waiting for your click...\n")

# This script will WAIT until you press ANY KEY on your keyboard
# MUCH MORE RELIABLE on Linux
input("Press ENTER after you CLICK on the search box...")

# NOW capture the position
pos = subprocess.check_output(["xdotool", "getmouselocation"]).decode()
print("\n" + "="*50)
print("✅ YOUR SEARCH BOX COORDINATES:")
print(pos.strip())
print("="*50)

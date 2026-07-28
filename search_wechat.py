import subprocess
import time

# --------------------------
# YOUR FIXED COORDINATES (all relative to THEIR OWN WINDOW)
# --------------------------
SEARCH_BAR_REL_X = 165
SEARCH_BAR_REL_Y = 58
FIRST_RESULT_REL_X = 348
FIRST_RESULT_REL_Y = 197
ARTICLE_TAB_REL_X = 439
ARTICLE_TAB_REL_Y = -9

# --------------------------
# AUTO-DETECT MAIN WECHAT WINDOW
# --------------------------
def get_any_wechat_window(name_part="wechat"):
    try:
        wid = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--class", name_part]
        ).decode().splitlines()[0]
        
        geom = subprocess.check_output(
            ["xdotool", "getwindowgeometry", wid]
        ).decode()
        
        for line in geom.splitlines():
            if "Position:" in line:
                pos = line.split()[1]
                win_x, win_y = pos.split(',')
                return int(win_x), int(win_y), wid
    except:
        return 0, 0, ""

# --------------------------
# ACTIVATE A WINDOW
# --------------------------
def activate_window(wid):
    subprocess.run(["xdotool", "windowactivate", wid])
    time.sleep(1)

# --------------------------
# MAIN SCRIPT
# --------------------------
if __name__ == "__main__":
    SEARCH_TERM = "latest AI agent news"

    print("🔹 Step 1: Open main WeChat window")
    subprocess.run(["wmctrl", "-xa", "wechat"])
    time.sleep(6)
    wx, wy, main_wid = get_any_wechat_window("wechat")

    # --------------------------
    # SEARCH (main window)
    # --------------------------
    print("🔹 Step 2: Search in WeChat top search box")
    activate_window(main_wid)
    subprocess.run(["xdotool", "mousemove", str(wx + SEARCH_BAR_REL_X), str(wy + SEARCH_BAR_REL_Y)])
    time.sleep(0.5)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(1)
    subprocess.run(["xdotool", "type", SEARCH_TERM])
    time.sleep(1)
    subprocess.run(["xdotool", "key", "Return"])
    time.sleep(6)

    # --------------------------
    # AUTO-DETECT NEW SEARCH WINDOW
    # --------------------------
    print("🔹 Step 3: Detected NEW SEARCH WINDOW")
    sx, sy, search_wid = get_any_wechat_window("wechat")
    activate_window(search_wid)

    # --------------------------
    # CLICK FIRST RESULT (in new search window)
    # --------------------------
    print("🔹 Step 4: Click first result in new window")
    subprocess.run(["xdotool", "mousemove", str(sx + FIRST_RESULT_REL_X), str(sy + FIRST_RESULT_REL_Y)])
    time.sleep(0.8)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(6)

    # --------------------------
    # AUTO-DETECT ARTICLE WINDOW
    # --------------------------
    print("🔹 Step 5: Detected ARTICLE WINDOW")
    ax, ay, article_wid = get_any_wechat_window("wechat")
    activate_window(article_wid)

    # --------------------------
    # SWITCH TO ARTICLE TAB
    # --------------------------
    print("🔹 Step 6: Switch to article tab")
    subprocess.run(["xdotool", "mousemove", str(ax + ARTICLE_TAB_REL_X), str(ay + ARTICLE_TAB_REL_Y)])
    time.sleep(0.6)
    subprocess.run(["xdotool", "click", "1"])
    time.sleep(2)

    # --------------------------
    # RIGHT-CLICK + COPY URL
    # --------------------------
    print("🔹 Step 7: Right-click to copy URL")
    subprocess.run(["xdotool", "mousemove", str(ax + 250), str(ay + 250)])
    time.sleep(0.7)
    subprocess.run(["xdotool", "click", "3"])
    time.sleep(1.5)
    subprocess.run(["xdotool", "mousemove", str(ax + 280), str(ay + 270)])
    time.sleep(0.6)
    subprocess.run(["xdotool", "click", "1"])

    print("\n🎉 FULLY AUTOMATED — URL COPIED!")

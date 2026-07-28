import subprocess

def get_wechat_window():
    wid = subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--class", "wechat"]
    ).decode().splitlines()[0]
    geom = subprocess.check_output(
        ["xdotool", "getwindowgeometry", wid]
    ).decode()
    for line in geom.splitlines():
        if "Position:" in line:
            pos = line.split()[1]
            win_x, win_y = pos.split(',')
            return int(win_x), int(win_y)

print("=== GET NEW ARTICLE TAB RELATIVE COORDINATES ===")
print("1. Keep WeChat open with article already opened in new tab")
print("2. Manually CLICK the NEW ARTICLE TAB on the TOP TAB BAR")
print("3. Press ENTER in terminal\n")

input("Press ENTER after clicking the new article tab...")

win_x, win_y = get_wechat_window()
mouse = subprocess.check_output(["xdotool", "getmouselocation"]).decode()
abs_x = int(mouse.split()[0].split(':')[1])
abs_y = int(mouse.split()[1].split(':')[1])

rel_x = abs_x - win_x
rel_y = abs_y - win_y

print("\n✅ YOUR NEW ARTICLE TAB RELATIVE COORDINATES:")
print(f"ARTICLE_TAB_REL_X = {rel_x}")
print(f"ARTICLE_TAB_REL_Y = {rel_y}")

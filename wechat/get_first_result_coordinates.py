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

print("=== GET FIRST RESULT COORDINATES ===")
print("1. Do a WeChat search and SHOW THE RESULTS")
print("2. Click DIRECTLY on the FIRST RESULT title")
print("3. Press ENTER in terminal\n")
input("Press ENTER after clicking first result...")

win_x, win_y = get_wechat_window()
mouse = subprocess.check_output(["xdotool", "getmouselocation"]).decode()
abs_x = int(mouse.split()[0].split(':')[1])
abs_y = int(mouse.split()[1].split(':')[1])

rel_x = abs_x - win_x
rel_y = abs_y - win_y

print("\n✅ YOUR FIRST RESULT RELATIVE COORDINATES:")
print(f"FIRST_RESULT_REL_X = {rel_x}")
print(f"FIRST_RESULT_REL_Y = {rel_y}")

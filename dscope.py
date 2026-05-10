import os

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "0")

import sys
import cv2
import mss
import time
import shutil
import ctypes
import numpy as np
from ctypes import wintypes

try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except AttributeError:
    pass

SRC_CAMERA = 'camera'
SRC_MONITOR = 'monitor'
SRC_WINDOW = 'window'
SRC_WINDOW_PICKER = 'window_picker'
SRC_REGION = 'region'

MODE_COLOR = 'color'
MODE_GRAY = 'gray'
MODE_HICOLOR = 'hicolor'

ASCII_CHARS_SIMPLE = " .:-=+*#%@"
ASCII_CHARS_DENSE = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

EDGE_CHARS = np.array(['|', '/', '-', '\\'])
EDGE_THRESHOLD = 80

GAMMA = 0.65
USE_DENSE_PALETTE_GRAY = True
SATURATION_BOOST = 1.30
COLOR_BG_FILL = True
COLOR_BG_DARKEN = 0.35

CHAR_ASPECT_RATIO = 0.5
CAMERA_PROBE_MAX = 5
WINDOW_MIN_DIM = 100
WINDOW_PICKER_TITLE_MAX = 48
WINDOW_LABEL_TITLE_MAX = 16
DEFAULT_TERMINAL_SIZE = (80, 24)
MIN_TERMINAL_COLS = 20
MIN_TERMINAL_ROWS = 5
FPS_SMOOTHING = 0.85

PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0
DIB_RGB_COLORS = 0
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
DPI_PER_MONITOR_AWARE = 2
STD_OUTPUT_HANDLE = -11

_GAMMA_LUT = np.clip((np.power(np.arange(256) / 255.0, GAMMA) * 255).round(), 0, 255).astype(np.uint8)
_CHAR_ARR_SIMPLE = np.array(list(ASCII_CHARS_SIMPLE))
_CHAR_ARR_DENSE = np.array(list(ASCII_CHARS_DENSE))

class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]

class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', _BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3),
    ]

def _setup_win32_signatures():
    if os.name != 'nt':
        return

    u = ctypes.windll.user32

    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.IsIconic.argtypes = [wintypes.HWND]
    u.IsIconic.restype = wintypes.BOOL
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.GetWindowDC.argtypes = [wintypes.HWND]
    u.GetWindowDC.restype = wintypes.HDC
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    u.ReleaseDC.restype = ctypes.c_int
    u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    u.PrintWindow.restype = wintypes.BOOL

    g = ctypes.windll.gdi32

    g.CreateCompatibleDC.argtypes = [wintypes.HDC]
    g.CreateCompatibleDC.restype = wintypes.HDC
    g.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    g.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    g.SelectObject.restype = wintypes.HGDIOBJ
    g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    g.DeleteObject.restype = wintypes.BOOL
    g.DeleteDC.argtypes = [wintypes.HDC]
    g.DeleteDC.restype = wintypes.BOOL
    g.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(_BITMAPINFO), wintypes.UINT]
    g.GetDIBits.restype = ctypes.c_int

_setup_win32_signatures()

def set_dpi_aware():
    if os.name != 'nt':
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(DPI_PER_MONITOR_AWARE)
        return
    except (AttributeError, OSError):
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

def enable_vt_mode():
    if os.name != 'nt':
        return

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (AttributeError, OSError):
        pass

def list_cameras(max_idx=CAMERA_PROBE_MAX):
    found = []

    for i in range(max_idx):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)

        if cap.isOpened():
            ok, _ = cap.read()

            if ok:
                found.append(i)

            cap.release()

    return found

def list_monitors():
    with mss.MSS() as sct:
        return list(sct.monitors)

def list_windows():
    if os.name != 'nt':
        return []

    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    results = []

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        if user32.IsIconic(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)

        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()

        if not title:
            return True

        rect = wintypes.RECT()

        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True

        w = rect.right - rect.left
        h = rect.bottom - rect.top

        if w < WINDOW_MIN_DIM or h < WINDOW_MIN_DIM:
            return True

        results.append({'hwnd': int(hwnd), 'title': title, 'left': rect.left, 'top': rect.top, 'width': w, 'height': h})

        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)

    return results

def capture_window(hwnd):
    if os.name != 'nt':
        return None

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None

    rect = wintypes.RECT()

    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None

    w = rect.right - rect.left
    h = rect.bottom - rect.top

    if w <= 0 or h <= 0:
        return None

    hdc_window = user32.GetWindowDC(hwnd)

    if not hdc_window:
        return None

    hdc_mem = None
    hbm = None

    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)

        if not hdc_mem:
            return None

        hbm = gdi32.CreateCompatibleBitmap(hdc_window, w, h)

        if not hbm:
            return None

        old = gdi32.SelectObject(hdc_mem, hbm)
        ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
        gdi32.SelectObject(hdc_mem, old)

        if not ok:
            return None

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buffer = (ctypes.c_uint8 * (w * h * 4))()

        if not gdi32.GetDIBits(hdc_mem, hbm, 0, h, buffer, ctypes.byref(bmi), DIB_RGB_COLORS):
            return None

        arr = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)

        return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

    finally:
        if hbm:
            gdi32.DeleteObject(hbm)

        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)

        user32.ReleaseDC(hwnd, hdc_window)

def ask_int(prompt, min_val=None):
    while True:
        s = input(prompt).strip()

        try:
            v = int(s)

            if min_val is not None and v < min_val:
                print(f"  Minimum value: {min_val}")
                continue

            return v
        except ValueError:
            print("  Invalid input, please enter an integer.")

def select_source():
    print("\n=== Available video sources ===")

    print("Probing cameras...")
    cams = list_cameras()

    print("Probing monitors...")
    monitors = list_monitors()

    options = []
    n = 1

    for c in cams:
        print(f"  [{n}] Camera #{c}")
        options.append((SRC_CAMERA, c, f"_Cam_{c}_"))
        n += 1

    for i, m in enumerate(monitors):
        if i == 0:
            label = f"All monitors ({m['width']}x{m['height']})"
            short = "_All_Screens_"
        else:
            label = f"Monitor {i} ({m['width']}x{m['height']} @ {m['left']},{m['top']})"
            short = f"_Screen_{i}_"

        print(f"  [{n}] {label}")
        options.append((SRC_MONITOR, i, short))
        n += 1

    print(f"  [{n}] Application window (pick from list)")
    options.append((SRC_WINDOW_PICKER, None, None))
    n += 1

    print(f"  [{n}] Custom region (X, Y, width, height)")
    options.append((SRC_REGION, None, "_Region_"))

    while True:
        choice = ask_int("\nChoice: ", min_val=1)

        if 1 <= choice <= len(options):
            break

        print("  Out of range.")

    src_type, src_data, label = options[choice - 1]

    if src_type == SRC_REGION:
        full = monitors[0] if monitors else {'width': 1920, 'height': 1080, 'left': 0, 'top': 0}

        print(f"\n(Full area: {full['width']}x{full['height']} starting at {full.get('left', 0)},{full.get('top', 0)})")

        x = ask_int("  X position: ")
        y = ask_int("  Y position: ")
        w = ask_int("  Width: ", min_val=1)
        h = ask_int("  Height: ", min_val=1)

        src_data = {'left': x, 'top': y, 'width': w, 'height': h}
        label = f"_Region_{w}x{h}@{x},{y}"

    elif src_type == SRC_WINDOW_PICKER:
        print("\n=== Open windows ===")
        wins = list_windows()

        if not wins:
            print("  No window detected.")
            sys.exit(1)

        for i, win in enumerate(wins, 1):
            title = win['title']

            if len(title) > WINDOW_PICKER_TITLE_MAX:
                title = title[:WINDOW_PICKER_TITLE_MAX - 3] + '...'

            print(f"  [{i}] {title}  ({win['width']}x{win['height']})")

        while True:
            wchoice = ask_int("\nChoice: ", min_val=1)

            if 1 <= wchoice <= len(wins):
                break

            print("  Out of range.")

        chosen = wins[wchoice - 1]
        src_type = SRC_WINDOW
        src_data = chosen['hwnd']
        short_title = chosen['title']

        if len(short_title) > WINDOW_LABEL_TITLE_MAX:
            short_title = short_title[:WINDOW_LABEL_TITLE_MAX - 3] + '...'

        label = f"_Win_ @> {short_title}"

    return src_type, src_data, label

def select_mode():
    print("\n=== Display mode ===")
    print("  [1] Color (24-bit)")
    print("  [2] Grayscale")
    print("  [3] HiColor (24-bit and 2x vertical sampling)")

    while True:
        choice = input("Choice: ").strip()

        if choice == '1':
            return MODE_COLOR, 'Color'

        if choice == '2':
            return MODE_GRAY, 'Gray'

        if choice == '3':
            return MODE_HICOLOR, 'HiColor'

        print("  Invalid input.")

def select_antialiasing():
    print("\n=== Anti-aliasing ===")
    print("  [1] Enabled")
    print("  [2] Disabled")

    while True:
        choice = input("Choice: ").strip()

        if choice == '1':
            return True

        if choice == '2':
            return False

        print("  Invalid input.")

def get_frame(cam, sct, src_state, src_type):
    if src_type == SRC_CAMERA:
        ok, frame = cam.read()

        return frame if ok else None

    if src_type == SRC_WINDOW:
        return capture_window(src_state)

    try:
        img = np.asarray(sct.grab(src_state))
    except Exception:
        return None

    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def _render_hicolor(frame, target_w, target_h, antialiasing):
    sample_h = max(2, target_h * 2)
    small = cv2.resize(frame, (target_w, sample_h), interpolation=cv2.INTER_AREA)

    if small.ndim == 2:
        small = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)

    if SATURATION_BOOST != 1.0:
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * SATURATION_BOOST, 0, 255)
        small = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    gray_full = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    if GAMMA != 1.0:
        gray_full = _GAMMA_LUT[gray_full]

    top = small[0::2]
    bot = small[1::2]
    gray = ((gray_full[0::2].astype(np.int32) + gray_full[1::2].astype(np.int32)) // 2).astype(np.uint8)

    palette = _CHAR_ARR_DENSE
    n_chars = len(palette) - 1
    idx = (gray.astype(np.int32) * n_chars // 255).clip(0, n_chars)
    char_grid = palette[idx]

    if antialiasing:
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx * gx + gy * gy)
        edge_mask = mag > EDGE_THRESHOLD
        angle = np.arctan2(gy, gx)
        angle = np.where(angle < 0, angle + np.pi, angle)
        bin_idx = np.floor((angle + np.pi / 8) / (np.pi / 4)).astype(np.int32) % 4
        edge_grid = EDGE_CHARS[bin_idx]
        char_grid = np.where(edge_mask, edge_grid, char_grid)

    Rt = top[:, :, 2]
    Gt = top[:, :, 1]
    Bt = top[:, :, 0]
    Rb = bot[:, :, 2]
    Gb = bot[:, :, 1]
    Bb = bot[:, :, 0]

    out_lines = []

    for y in range(target_h):
        parts = ['\x1b[0m']
        prev_fg = None
        prev_bg = None

        for x in range(target_w):
            fg = (int(Rt[y, x]), int(Gt[y, x]), int(Bt[y, x]))
            bg = (int(Rb[y, x]), int(Gb[y, x]), int(Bb[y, x]))

            if fg != prev_fg:
                parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                prev_fg = fg

            if bg != prev_bg:
                parts.append(f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
                prev_bg = bg

            parts.append(char_grid[y, x])

        out_lines.append(''.join(parts))

    return '\x1b[0m\x1b[K\n'.join(out_lines) + '\x1b[0m\x1b[K'

def render_ascii(frame, cols, rows, mode, antialiasing=False):
    if frame is None or frame.size == 0:
        return ''

    h, w = frame.shape[:2]

    if h == 0 or w == 0:
        return ''

    target_w = max(1, cols)
    target_h = max(1, int(target_w * (h / w) * CHAR_ASPECT_RATIO))

    if target_h > rows:
        target_h = max(1, rows)
        target_w = max(1, int(target_h * (w / h) / CHAR_ASPECT_RATIO))
        target_w = min(target_w, cols)

    if mode == MODE_HICOLOR:
        return _render_hicolor(frame, target_w, target_h, antialiasing)

    small = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

    if mode == MODE_COLOR and small.ndim == 3 and SATURATION_BOOST != 1.0:
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * SATURATION_BOOST, 0, 255)
        small = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    if small.ndim == 3:
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    else:
        gray = small

    if GAMMA != 1.0:
        gray = _GAMMA_LUT[gray]

    if mode == MODE_GRAY and USE_DENSE_PALETTE_GRAY:
        palette = _CHAR_ARR_DENSE
    else:
        palette = _CHAR_ARR_SIMPLE

    n_chars = len(palette) - 1
    idx = (gray.astype(np.int32) * n_chars // 255).clip(0, n_chars)
    char_grid = palette[idx]

    if antialiasing:
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx * gx + gy * gy)
        edge_mask = mag > EDGE_THRESHOLD
        angle = np.arctan2(gy, gx)
        angle = np.where(angle < 0, angle + np.pi, angle)
        bin_idx = np.floor((angle + np.pi / 8) / (np.pi / 4)).astype(np.int32) % 4
        edge_grid = EDGE_CHARS[bin_idx]
        char_grid = np.where(edge_mask, edge_grid, char_grid)

    if mode == MODE_GRAY:
        return '\x1b[K\n'.join(''.join(row) for row in char_grid) + '\x1b[K'

    R = small[:, :, 2]
    G = small[:, :, 1]
    B = small[:, :, 0]

    if COLOR_BG_FILL:
        f = COLOR_BG_DARKEN
        bgR = (R.astype(np.int32) * f).astype(np.int32)
        bgG = (G.astype(np.int32) * f).astype(np.int32)
        bgB = (B.astype(np.int32) * f).astype(np.int32)
        out_lines = []

        for y in range(target_h):
            parts = ['\x1b[0m']
            prev_fg = None
            prev_bg = None

            for x in range(target_w):
                fg = (int(R[y, x]), int(G[y, x]), int(B[y, x]))
                bg = (int(bgR[y, x]), int(bgG[y, x]), int(bgB[y, x]))

                if fg != prev_fg:
                    parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                    prev_fg = fg

                if bg != prev_bg:
                    parts.append(f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
                    prev_bg = bg

                parts.append(char_grid[y, x])

            out_lines.append(''.join(parts))

        return '\x1b[0m\x1b[K\n'.join(out_lines) + '\x1b[0m\x1b[K'

    out_lines = []

    for y in range(target_h):
        parts = ['\x1b[0m']
        prev = None

        for x in range(target_w):
            c = (int(R[y, x]), int(G[y, x]), int(B[y, x]))

            if c != prev:
                parts.append(f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m")
                prev = c

            parts.append(char_grid[y, x])

        out_lines.append(''.join(parts))

    return '\x1b[0m\x1b[K\n'.join(out_lines) + '\x1b[0m\x1b[K'

def _print_signoff():
    GREEN = '\x1b[32m'
    GREEN_BOLD = '\x1b[1;32m'
    GREEN_DIM = '\x1b[2;32m'
    RESET = '\x1b[0m'
    WIDTH = 46

    def box(text='', style=''):
        pad = WIDTH - len(text)
        left_pad = pad // 2
        right_pad = pad - left_pad

        return f"   {GREEN_DIM}|{RESET}{' ' * left_pad}{style}{text}{RESET}{' ' * right_pad}{GREEN_DIM}|{RESET}"

    border = f"   {GREEN_DIM}+{'=' * WIDTH}+{RESET}"

    print()
    print(border)
    print(box())
    print(box('>>> LOSS OF SIGNAL <<<', GREEN_BOLD))
    print(box('-' * 22, GREEN_DIM))
    print(box('Transmission terminated.', GREEN))
    print(box('All channels closed.', GREEN))
    print(box())
    print(box('... OUT.', GREEN_BOLD))
    print(box())
    print(border)
    print(f"   {GREEN_DIM} dScope :: GROUND CONTROL :: SIGNING OFF{RESET}")
    print()

def main():
    set_dpi_aware()
    enable_vt_mode()

    src_type, src_data, src_label = select_source()
    mode, mode_label = select_mode()
    antialiasing = select_antialiasing()
    aa_label = "AA" if antialiasing else "noAA"

    cam = None
    sct = None
    src_state = None

    if src_type == SRC_CAMERA:
        cam = cv2.VideoCapture(src_data, cv2.CAP_DSHOW)

        if not cam.isOpened():
            print("Cannot open camera.")
            return
    else:
        sct = mss.MSS()

        if src_type == SRC_MONITOR:
            src_state = sct.monitors[src_data]

        elif src_type == SRC_WINDOW:
            src_state = src_data

        else:
            src_state = src_data

    sys.stdout.write('\x1b[?25l\x1b[2J')
    sys.stdout.flush()

    fps_smooth = 0.0
    last_t = time.perf_counter()

    try:
        while True:
            frame = get_frame(cam, sct, src_state, src_type)

            if frame is None:
                if src_type == SRC_WINDOW:
                    cols, rows = shutil.get_terminal_size(DEFAULT_TERMINAL_SIZE)
                    msg = f"[Window unavailable (minimized or closed) - {src_label}]"
                    sys.stdout.write('\x1b[H\x1b[2J' + msg[:cols] + '\n')
                    sys.stdout.flush()

                time.sleep(0.1)

                continue

            cols, rows = shutil.get_terminal_size(DEFAULT_TERMINAL_SIZE)
            cols = max(MIN_TERMINAL_COLS, cols)
            rows = max(MIN_TERMINAL_ROWS, rows)

            left = f"FPS: {fps_smooth:5.1f}"
            right = f"{src_label} / {mode_label} / {aa_label}"
            pad = max(1, cols - len(left) - len(right))
            header = (left + ' ' * pad + right)[:cols]

            ascii_img = render_ascii(frame, cols, rows - 1, mode, antialiasing=antialiasing)

            buf = ['\x1b[H', '\x1b[0m', header, '\x1b[K\n', ascii_img, '\x1b[0m\x1b[J']
            sys.stdout.write(''.join(buf))
            sys.stdout.flush()

            now = time.perf_counter()
            dt = now - last_t
            last_t = now

            if dt > 0:
                inst = 1.0 / dt
                fps_smooth = inst if fps_smooth == 0 else fps_smooth * FPS_SMOOTHING + inst * (1.0 - FPS_SMOOTHING)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write('\x1b[0m\x1b[?25h\x1b[2J\x1b[H')
        sys.stdout.flush()

        if cam is not None:
            cam.release()

        _print_signoff()

if __name__ == '__main__':
    main()
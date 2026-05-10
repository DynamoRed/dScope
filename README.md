<p align="center">
  <img src="docs/banner.png" alt="dScope - 2026 - DynamoRed" width="100%">
  <br><br>
  <img src="https://img.shields.io/badge/python-3.11%2B-76B900?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/license-fun%20use%20only-FF6B6B" alt="License">
</p>

---

<p align="center">
  <img src="docs/preview.gif" alt="dScope demo" width="100%">
  Preview (source on left, result on right)
</p>

  <strong>Live 24-bit ASCII video in terminal, from any source on a Windows machine.</strong>

🡒 [higher resolution preview here](docs/preview.mp4)

## 🚀 Quick start

```bash
pip install -r requirements.txt
python dscope.py
```

Pick a source, a color mode, enable/disable anti-aliasing, and you are live. `Ctrl+C` to quit.

## ✨ Features

- **5 input modes**: webcam, all monitors, single monitor, application window, custom region
- **24-bit truecolor** output with HSV saturation boost and darkened background fill
- **Edge-aware rendering**: contours snap to `|`, `/`, `-`, `\` based on direction
- **Two palettes**: 10-char ramp (simple) or 70-char ramp (dense, grayscale only)
- **Window capture via `PrintWindow`**: grabs occluded or partially off-screen windows, ignores anything in front
- **DPI-aware** capture: no offset drift on scaled displays
- **Live FPS counter** with exponential smoothing
- ANSI emit dedupes consecutive identical colors per row

## 🧩 Compatibility

| Source        | Windows | macOS | Linux |
|---------------|:-------:|:-----:|:-----:|
| Webcam        |   yes   |   -   |   -   |
| Monitor       |   yes   |  yes  |  yes  |
| Custom region |   yes   |  yes  |  yes  |
| App window    |   yes   |   -   |   -   |

- Built and tuned for **Windows Terminal**. Works in `cmd.exe` and PowerShell thanks to the VT-mode toggle, but expect lower FPS.
- Webcam path uses **DirectShow** and window capture uses **Win32 GDI**. Both are Windows-only.
- On macOS / Linux the monitor and region paths still work via `mss`. The other modes will be hidden / unavailable.
- **Known limit**: hardware-accelerated apps (DirectX games, DRM video players) often return a black frame from `PrintWindow`. Use the monitor mode instead.

## 🪴 License

Source-available. Free for personal and non-commercial use. **No modifications, no redistribution for profit, no commercial use.** See [LICENSE](./LICENSE).
Contact team@dynamored.com

<img src="https://views-counter.vercel.app/badge?pageId=dscope-dynamored%2FViews-Counter&label=Views&rightColor=F8F2EA&leftColor=0B090A" alt="Views Counter">
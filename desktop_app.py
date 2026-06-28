import webview
import subprocess
import threading
import time
import sys
import os

server_process = None

def start_server():
    global server_process
    dir_path = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(dir_path, ".venv", "Scripts", "python.exe")
    python = venv_python if os.path.exists(venv_python) else sys.executable
    server_process = subprocess.Popen(
        [python, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "7789"],
        cwd=dir_path,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

def wait_and_open():
    import urllib.request
    # Чекаємо до 60 секунд
    for _ in range(120):
        try:
            urllib.request.urlopen("http://127.0.0.1:7789/api/status", timeout=1)
            window.load_url("http://127.0.0.1:7789")
            return
        except:
            time.sleep(0.5)
    window.load_url("http://127.0.0.1:7789")

LOADING_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  body { margin:0; background:#0d1117; display:flex; align-items:center; justify-content:center; height:100vh; flex-direction:column; font-family:sans-serif; }
  .spinner { width:48px; height:48px; border:4px solid #30363d; border-top-color:#1f6feb; border-radius:50%; animation:spin 1s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  p { color:#8b949e; margin-top:20px; font-size:14px; }
  h2 { color:#e6edf3; margin:0 0 8px; }
</style>
</head>
<body>
  <div class="spinner"></div>
  <h2 style="color:#e6edf3;margin-top:20px">FaceLib</h2>
  <p>Starting...</p>
</body>
</html>
"""

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()

    dir_path = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(dir_path, "facelib.ico")

    window = webview.create_window(
        "FaceLib",
        html=LOADING_HTML,
        width=1400,
        height=900,
        min_size=(800, 600),
    )

    threading.Thread(target=wait_and_open, daemon=True).start()

    webview.start()

    # Встановлюємо іконку через Windows API
    if sys.platform == "win32" and os.path.exists(icon_path):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FaceLib")
        except:
            pass

    if server_process:
        server_process.terminate()

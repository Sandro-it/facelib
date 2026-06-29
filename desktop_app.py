import webview
import subprocess
import threading
import time
import sys
import os
import ctypes

server_process = None

class Api:
    def copy_to_clipboard(self, paths):
        """Копіює файли в буфер обміну Windows (CF_HDROP) через ctypes."""
        try:
            import ctypes
            import ctypes.wintypes
            import struct

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            # Формуємо DROPFILES + список файлів у Unicode
            files_str = '\0'.join(paths) + '\0\0'
            files_bytes = files_str.encode('utf-16-le')

            # DROPFILES структура: pFiles(4) + pt(8) + fNC(4) + fWide(4) = 20 bytes
            header = struct.pack('<IIIII', 20, 0, 0, 0, 1)  # fWide=1
            data = header + files_bytes
            data_len = len(data)

            # Виділяємо глобальну пам'ять
            GMEM_MOVEABLE = 0x0002
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, data_len)
            if not h_mem:
                raise OSError("GlobalAlloc failed")

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                raise OSError("GlobalLock failed")

            ctypes.memmove(ptr, data, data_len)
            kernel32.GlobalUnlock(h_mem)

            # Відкриваємо буфер обміну і встановлюємо дані
            CF_HDROP = 15
            if not user32.OpenClipboard(None):
                raise OSError("OpenClipboard failed")
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_HDROP, h_mem)
            user32.CloseClipboard()

            return {"ok": True, "count": len(paths)}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def share_files(self, paths):
        """Залишено для сумісності."""
        return self.copy_to_clipboard(paths)

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
    # Чекаємо до 120 секунд поки сервер і БД повністю готові
    for _ in range(240):
        try:
            urllib.request.urlopen("http://127.0.0.1:7789/api/persons/count", timeout=1)
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

    api = Api()
    window = webview.create_window(
        "FaceLib",
        html=LOADING_HTML,
        width=1400,
        height=900,
        min_size=(800, 600),
        js_api=api,
    )

    threading.Thread(target=wait_and_open, daemon=True).start()

    webview.start()

    if server_process:
        server_process.terminate()

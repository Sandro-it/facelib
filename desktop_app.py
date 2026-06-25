import webview
import subprocess
import threading
import time
import sys
import os

def start_server():
    """Запускаємо FastAPI сервер у фоні"""
    subprocess.Popen(
        [sys.executable, "app.py"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

def wait_and_open():
    """Чекаємо поки сервер запуститься і відкриваємо вікно"""
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen("http://127.0.0.1:7788/api/status")
            break
        except:
            time.sleep(0.5)
    
    window.load_url("http://127.0.0.1:7788")

if __name__ == "__main__":
    # Запускаємо сервер
    threading.Thread(target=start_server, daemon=True).start()
    
    # Створюємо вікно
    window = webview.create_window(
        "FaceLib",
        url="about:blank",
        width=1400,
        height=900,
        min_size=(800, 600),
    )
    
    # Відкриваємо інтерфейс коли сервер готовий
    threading.Thread(target=wait_and_open, daemon=True).start()
    
    webview.start()

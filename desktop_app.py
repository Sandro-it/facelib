import webview
import subprocess
import threading
import time
import sys
import os
import ctypes

server_process = None

class Api:
    def share_files(self, paths):
        """Викликає системний діалог Windows Share для переданих файлів."""
        import asyncio
        import threading

        def do_share():
            try:
                import comtypes
                import comtypes.client
                from winrt.windows.storage import StorageFile
                from winrt.windows.applicationmodel.datatransfer import DataTransferManager

                # GUID для IDataTransferManagerInterop
                DTM_INTEROP_IID = "{3A3DCD6C-3EAB-43DC-BCDE-45671CE800C8}"
                DTM_IID = comtypes.GUID("{A5CAEE9B-8708-49D1-8D36-67D25A8DA00C}")

                # Отримуємо HWND вікна pywebview
                hwnd = ctypes.windll.user32.GetForegroundWindow()

                # Отримуємо IDataTransferManagerInterop через COM
                clsid = comtypes.GUID("{4CE576FA-83DC-4F88-951C-9D0782B4E376}")
                obj = comtypes.cast(
                    comtypes.CoCreateInstance(clsid),
                    comtypes.POINTER(comtypes.IUnknown)
                )

                loop = asyncio.new_event_loop()

                async def run():
                    files = []
                    for p in paths:
                        f = await StorageFile.get_file_from_path_async(p)
                        files.append(f)

                    dtm = DataTransferManager.get_for_current_view()

                    def on_data_requested(sender, args):
                        dp = args.request.data
                        dp.properties.title = f"FaceLib — {len(files)} фото"
                        dp.set_storage_items(files)

                    dtm.add_data_requested(on_data_requested)
                    DataTransferManager.show_share_ui()

                loop.run_until_complete(run())
            except Exception as e:
                import traceback
                traceback.print_exc()

        threading.Thread(target=do_share, daemon=True).start()
        return {"ok": True}

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

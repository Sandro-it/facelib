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
        import threading

        def do_share():
            try:
                import asyncio
                import ctypes
                import ctypes.wintypes

                hwnd = ctypes.windll.user32.FindWindowW(None, "FaceLib")
                if not hwnd:
                    hwnd = ctypes.windll.user32.GetForegroundWindow()

                loop = asyncio.new_event_loop()

                async def run():
                    from winrt.windows.storage import StorageFile
                    from winrt.windows.applicationmodel.datatransfer import DataTransferManager

                    files = []
                    for p in paths:
                        f = await StorageFile.get_file_from_path_async(p)
                        files.append(f)

                    # Отримуємо IDataTransferManagerInterop через RoGetActivationFactory
                    combase = ctypes.windll.combase

                    class GUID(ctypes.Structure):
                        _fields_ = [
                            ("Data1", ctypes.c_ulong),
                            ("Data2", ctypes.c_ushort),
                            ("Data3", ctypes.c_ushort),
                            ("Data4", ctypes.c_ubyte * 8),
                        ]

                    interop_iid = GUID()
                    interop_iid.Data1 = 0x3A3DCD6C
                    interop_iid.Data2 = 0x3EAB
                    interop_iid.Data3 = 0x43DC
                    interop_iid.Data4 = (ctypes.c_ubyte * 8)(0xBC, 0xDE, 0x45, 0x67, 0x1C, 0xE8, 0x00, 0xC8)

                    dtm_iid = GUID()
                    dtm_iid.Data1 = 0xA5CAEE9B
                    dtm_iid.Data2 = 0x8708
                    dtm_iid.Data3 = 0x49D1
                    dtm_iid.Data4 = (ctypes.c_ubyte * 8)(0x8D, 0x36, 0x67, 0xD2, 0x5A, 0x8D, 0xA0, 0x0C)

                    class_name = "Windows.ApplicationModel.DataTransfer.DataTransferManager"
                    hstring = ctypes.c_void_p()
                    combase.WindowsCreateString(
                        class_name, len(class_name),
                        ctypes.byref(hstring)
                    )

                    factory = ctypes.c_void_p()
                    hr = combase.RoGetActivationFactory(
                        hstring,
                        ctypes.byref(interop_iid),
                        ctypes.byref(factory)
                    )
                    if hr != 0:
                        raise OSError(f"RoGetActivationFactory failed: {hr:#010x}")

                    vtable = ctypes.cast(
                        ctypes.cast(factory, ctypes.POINTER(ctypes.c_void_p))[0],
                        ctypes.POINTER(ctypes.c_void_p)
                    )

                    # GetForWindow — індекс 3 у vtable (після QueryInterface, AddRef, Release)
                    GetForWindow = ctypes.WINFUNCTYPE(
                        ctypes.HRESULT,
                        ctypes.c_void_p,   # this
                        ctypes.wintypes.HWND,
                        ctypes.POINTER(GUID),
                        ctypes.POINTER(ctypes.c_void_p)
                    )(vtable[3])

                    dtm_ptr = ctypes.c_void_p()
                    hr2 = GetForWindow(factory, hwnd, ctypes.byref(dtm_iid), ctypes.byref(dtm_ptr))
                    if hr2 != 0:
                        raise OSError(f"GetForWindow failed: {hr2:#010x}")

                    # Підписуємось на DataRequested через winrt об'єкт
                    # Отримуємо DTM з того ж factory через стандартний winrt метод
                    dtm = DataTransferManager.get_for_current_view()

                    def on_data_requested(sender, args):
                        dp = args.request.data
                        dp.properties.title = f"FaceLib — {len(files)} фото"
                        dp.set_storage_items(files)

                    dtm.add_data_requested(on_data_requested)

                    # ShowShareUIForWindow — індекс 4 у vtable
                    ShowShareUIForWindow = ctypes.WINFUNCTYPE(
                        ctypes.HRESULT,
                        ctypes.c_void_p,   # this
                        ctypes.wintypes.HWND,
                    )(vtable[4])
                    hr3 = ShowShareUIForWindow(factory, hwnd)
                    if hr3 != 0:
                        raise OSError(f"ShowShareUIForWindow failed: {hr3:#010x}")

                loop.run_until_complete(run())
            except Exception as e:
                import traceback
                err = str(e)
                print("SHARE ERROR:", traceback.format_exc())
                try:
                    safe_err = err.replace('"', '\\"').replace('\n', '\\n')
                    window.evaluate_js(f'alert("Share помилка:\\n{safe_err}")')
                except:
                    pass

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

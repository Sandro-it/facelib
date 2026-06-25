Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Запускаємо сервер у фоні
objShell.Run "cmd /c cd /d """ & strDir & """ && call .venv\Scripts\activate.bat && uvicorn app:app --host 127.0.0.1 --port 7788", 0, False

' Чекаємо 2 секунди поки сервер запуститься
WScript.Sleep 2000

' Відкриваємо браузер
objShell.Run "http://127.0.0.1:7788"

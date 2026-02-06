Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Create shortcut on Desktop
desktopPath = WshShell.SpecialFolders("Desktop")
Set shortcut = WshShell.CreateShortcut(desktopPath & "\Metacog.lnk")

shortcut.TargetPath = scriptDir & "\start.bat"
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "Metacog - LLM Awareness Engine"
shortcut.IconLocation = "shell32.dll,71"
shortcut.Save

MsgBox "Metacog shortcut created on Desktop!" & vbCrLf & vbCrLf & "You can now pin it to taskbar by right-clicking.", vbInformation, "Metacog"

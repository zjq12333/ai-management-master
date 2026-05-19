Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
toolDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
If fso.FileExists(pythonw) Then
  shell.Run """" & pythonw & """ -X utf8 """ & toolDir & "\CodexMaintenanceGUI.py""", 0, False
Else
  shell.Run "python -X utf8 """ & toolDir & "\CodexMaintenanceGUI.py""", 0, False
End If

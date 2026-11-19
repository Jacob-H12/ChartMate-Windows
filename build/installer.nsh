; The per-machine installer requests elevation for the Microsoft runtime.
!macro customInstall
  DetailPrint "Preparing Microsoft Visual C++ runtime..."
  ExecWait '"$INSTDIR\resources\runtime\vc_redist.x64.exe" /install /quiet /norestart' $0
  ${If} $0 == 3010
    SetRebootFlag true
  ${ElseIf} $0 != 0
  ${AndIf} $0 != 1638
    MessageBox MB_ICONSTOP "Microsoft Visual C++ runtime setup failed (code $0). ChartMate may not start. Please run the installer again or send this error to the developer."
    Abort
  ${EndIf}
!macroend

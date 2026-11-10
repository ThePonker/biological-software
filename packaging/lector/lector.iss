; Inno Setup script for the free-standing Lector (Inno Setup 6). Compile with
;   ISCC.exe /DSourceDir=<the PyInstaller output folder, ...\Lector> /DOutputDir=<folder> packaging\lector\lector.iss
; (build_lector.ps1 does this.) Installs for the current user only: no administrator needed.

#ifndef SourceDir
  #define SourceDir "..\..\build\lector\dist\Lector"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\build\lector\installer"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6B0E0B4C-3E5D-4C8B-9D55-4C6C1A0E7A11}
AppName=Lector
AppVersion={#AppVersion}
AppPublisher=Flauna Ecology
DefaultDirName={localappdata}\Programs\Lector
DefaultGroupName=Lector
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Lector_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Lector (Biodiversity Heritage Library reader)

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
; Your data (lector.db, the BHL key, exports) lives here, not in the program folder. The folder
; is made only if it is not already there, and the uninstaller never removes it.
Name: "{userdocs}\Lector\data"; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\Lector"; Filename: "{app}\Lector.exe"; WorkingDir: "{userdocs}\Lector"
Name: "{autodesktop}\Lector"; Filename: "{app}\Lector.exe"; WorkingDir: "{userdocs}\Lector"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Put a Lector shortcut on the desktop"; Flags: unchecked

[Run]
Filename: "{app}\Lector.exe"; Description: "Open Lector now"; Flags: nowait postinstall skipifsilent

; Inno Setup script for TalkTalk. Build the exe first with build_exe.ps1, then compile this.

#define AppName "TalkTalk"
#define AppVersion "1.0.0"
#define AppExe "TalkTalk.exe"

[Setup]
AppId={{6C2E1B7A-4E5D-4F0B-9C1A-7A1D2C3B4E5F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=hellonearthis
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=TalkTalk-Setup
SetupIconFile=talktalk.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "startup"; Description: "Start TalkTalk when I sign in to Windows"; GroupDescription: "Options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "dist\TalkTalk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TalkTalk"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch TalkTalk"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillTalkTalk"


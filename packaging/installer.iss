; Inno Setup script. Compile after running PyInstaller:  iscc /DAppVersion=0.1.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{C88FCBF2-F3F4-4521-9782-DAF296D66673}
AppName=HornVoice
AppVersion={#AppVersion}
AppPublisher=KaeghanG
AppPublisherURL=https://github.com/KaeghanG/hornvoice
DefaultDirName={localappdata}\Programs\HornVoice
DefaultGroupName=HornVoice
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=HornVoice-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\HornVoice.exe
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "startup"; Description: "Start HornVoice with Windows"; GroupDescription: "Options:"

[Files]
Source: "..\dist\HornVoice\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\HornVoice"; Filename: "{app}\HornVoice.exe"
Name: "{userstartup}\HornVoice"; Filename: "{app}\HornVoice.exe"; Tasks: startup

[Run]
Filename: "{app}\HornVoice.exe"; Description: "Launch HornVoice"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM HornVoice.exe"; Flags: runhidden; RunOnceId: "KillHornVoice"

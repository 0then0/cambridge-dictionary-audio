#ifndef AppVersion
  #error AppVersion must be supplied by the release builder
#endif
#ifndef SourceDir
  #error SourceDir must be supplied by the release builder
#endif

[Setup]
AppId=org.cambridgeaudio.desktop
AppName=Cambridge Dictionary Audio
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher=0then0
AppPublisherURL=https://github.com/0then0/cambridge-dictionary-audio
DefaultDirName={localappdata}\Programs\Cambridge Dictionary Audio
DefaultGroupName=Cambridge Dictionary Audio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=cambridge-dictionary-audio-{#AppVersion}-windows-x86_64-setup
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Cambridge Dictionary Audio.exe
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Cambridge Dictionary Audio"; Filename: "{app}\Cambridge Dictionary Audio.exe"
Name: "{autodesktop}\Cambridge Dictionary Audio"; Filename: "{app}\Cambridge Dictionary Audio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Cambridge Dictionary Audio.exe"; Description: "{cm:LaunchProgram,Cambridge Dictionary Audio}"; Flags: nowait postinstall skipifsilent

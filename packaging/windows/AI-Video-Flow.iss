; AI Video Flow V0.1 per-user installer. Keep AppId stable across versions.
#ifndef SourceDir
  #error SourceDir must be passed by the release build script
#endif
#ifndef OutputDir
  #error OutputDir must be passed by the release build script
#endif
#ifndef ReleaseVersion
  #error ReleaseVersion must be passed by the release build script
#endif
#ifndef NumericVersion
  #error NumericVersion must be passed by the release build script
#endif

#define AppName "AI Video Flow"
#define AppExe "AIVideoFlow.exe"
#define AppIdValue "{{42ede151-81cb-5573-8ee0-547ad09a3c83}"

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#ReleaseVersion}
AppVerName={#AppName} {#ReleaseVersion}
AppComments=AI video production workflow for Windows
DefaultDirName={localappdata}\Programs\AI Video Flow
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AI-Video-Flow-{#ReleaseVersion}-windows-x64-setup
SetupIconFile=AI-Video-Flow.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
VersionInfoDescription=AI video production workflow for Windows
VersionInfoProductName={#AppName}
VersionInfoVersion={#NumericVersion}
WizardStyle=modern
Compression=lzma2/normal
SolidCompression=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

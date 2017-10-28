; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

#define MyAppName "CMN_binViewer"

[Setup]
AppName=CMN_binViewer
AppVersion=2.55
AppPublisher=Croatian Meteor Network
AppPublisherURL=http://cmn.rgn.hr/
DefaultDirName={pf}\CMN_binViewer
DefaultGroupName=CMN_binViewer
UninstallDisplayIcon={app}\CMN_binViewer.exe
Compression=lzma2
SolidCompression=yes
OutputDir="."

[Files]
Source: ".\build\exe.win32-2.7\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; 

[Icons]
Name: "{group}\CMN_binViewer"; Filename: "{app}\CMN_binViewer.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\CMN_binViewer.exe"; Tasks: desktopicon; WorkingDir: {app}

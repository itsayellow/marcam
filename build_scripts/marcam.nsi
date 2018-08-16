; Original code (http://nsis.sourceforge.net/Examples/example2.nsi)
; Modified by Matthew A. Clapp
; Copyright 2017-2018 Matthew A. Clapp
;
; Licensed under the Apache License, Version 2.0 (the "License");
; you may not use this file except in compliance with the License.
; You may obtain a copy of the License at
;
;     http://www.apache.org/licenses/LICENSE-2.0
;
; Unless required by applicable law or agreed to in writing, software
; distributed under the License is distributed on an "AS IS" BASIS,
; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
; See the License for the specific language governing permissions and
; limitations under the License.

; from example2.nsi (http://nsis.sourceforge.net/Examples/example2.nsi)
; This script is based on example1.nsi, but it remember the directory,
; has uninstall support and (optionally) installs start menu shortcuts.
;
; It will install example2.nsi into a directory that the user selects,

;--------------------------------
!include "FileAssoc.nsh"

; The name of the installer
Name "Marcam"

; The file to write
OutFile "..\dist\Marcam_Installer.exe"

; The default installation directory
InstallDir $PROGRAMFILES\Marcam

; Registry key to check for directory (so if you install again, it will
; overwrite the old one automatically)
InstallDirRegKey HKLM "Software\Marcam" "Install_Dir"

; Request application privileges for Windows Vista
RequestExecutionLevel admin

;--------------------------------

; Pages

Page components
Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

;--------------------------------

; The stuff to install
Section "Marcam (required)"

  SectionIn RO

  ; Set output path to the installation directory.
  SetOutPath $INSTDIR

  ; Put files there
  File /r "..\dist\marcam\*"

  ; Write the installation path into the registry
  WriteRegStr HKLM SOFTWARE\Marcam "Install_Dir" "$INSTDIR"

  ; Write the uninstall keys for Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Marcam" "DisplayName" "Marcam"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Marcam" "UninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Marcam" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Marcam" "NoRepair" 1
  WriteUninstaller "uninstall.exe"

; APP_ASSOCIATE EXT FILECLASS DESCRIPTION ICON COMMANDTEXT COMMAND
  !insertmacro APP_ASSOCIATE "mcm" "Marcam.ImageData" "Marcam Image Data" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""
  !insertmacro APP_OPENWITH "1sc" "Marcam.PlainImage" "Marcam Plain Image" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""
  !insertmacro APP_OPENWITH "png" "Marcam.PlainImage" "Marcam Plain Image" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""
  !insertmacro APP_OPENWITH "tif" "Marcam.PlainImage" "Marcam Plain Image" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""
  !insertmacro APP_OPENWITH "tiff" "Marcam.PlainImage" "Marcam Plain Image" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""
  !insertmacro APP_OPENWITH "jpg" "Marcam.PlainImage" "Marcam Plain Image" "$INSTDIR\media\marcam_doc.ico" "Open with Marcam" "$INSTDIR\marcam.exe $\"%1$\""

SectionEnd

; Optional section (can be disabled by the user)
Section "Start Menu Shortcuts"

  CreateDirectory "$SMPROGRAMS\Marcam"
  CreateShortcut "$SMPROGRAMS\Marcam\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
  CreateShortcut "$SMPROGRAMS\Marcam\Marcam.lnk" "$INSTDIR\marcam.exe" "" "$INSTDIR\marcam.exe" 0

SectionEnd

;--------------------------------

; Uninstaller

Section "Uninstall"

  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Marcam"
  DeleteRegKey HKLM SOFTWARE\Marcam
  ;APP_UNASSOCIATE EXT FILECLASS
  !insertmacro APP_UNASSOCIATE "mcm" "Marcam.ImageData"
  !insertmacro APP_UNOPENWITH "1sc" "Marcam.PlainImage"
  !insertmacro APP_UNOPENWITH "png" "Marcam.PlainImage"
  !insertmacro APP_UNOPENWITH "tif" "Marcam.PlainImage"
  !insertmacro APP_UNOPENWITH "tiff" "Marcam.PlainImage"
  !insertmacro APP_UNOPENWITH "jpg" "Marcam.PlainImage"

  ; Remove files and uninstaller
  Delete $INSTDIR\*.*

  ; Remove shortcuts, if any
  Delete "$SMPROGRAMS\Marcam\*.*"

  ; Remove directories used
  RMDir /r "$SMPROGRAMS\Marcam"
  RMDir /r "$INSTDIR"

SectionEnd

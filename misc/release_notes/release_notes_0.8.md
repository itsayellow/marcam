# Version 0.8 What's New

Marcam inside the dmg file should run on any Mac OS X that is Yosemite (10.10.5) or later.

The Marcam Windows Installer was created on a Windows 10 Home version 1803.

Notable improvements:
* "Save file before closing?" dialog now tells you what changed since last save (#113)
* Long tasks now happen smoothly, with Progress dialog window while you wait.  (Internal: using threads) (#114)
* New dialogs to set parameters in image processing tasks. (#108)
  * False Color
  * Auto-contrast
* False Color mapping is now over 18x faster (#118).
* Mac: Marcam now has a Window menu to list all open windows and ability to select them from menu. (#107)
* Windows: Double-clicking on a file while Marcam is already open now successfully opens the file.
* Windows: Installer now looks much more modern and polished. (#117)
* Status bar now has a permanent location for Zoom ratio (on the right side).
* Register with OS that .1sc files can be opened by Marcam.
* Register with Windows OS that many image types can be opened with Marcam.  (.tif, .jpg, .png)
* Quicker undo/redo for image processing steps. (#103)
* Attempting to open a file that already is open will just raise existing window. (#105)
* Marcam now raises window it's asking you about saving on quitting the application. (#112)
* File->Save is disabled if nothing to save (#121)
* Startup speedups (#106 )
* Mac: Dialogs look more native with no title string.
* Windows: Start Menu: Only app in Start Menu (not folder), and Marcam installed for all users.
* (Internal) Only a single instance of Marcam is allowed to run, others are shut down gracefully and their files opened in main instance.
* (Internal) FrameList to keep track of frames. (#101)


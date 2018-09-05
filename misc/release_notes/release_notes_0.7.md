# Version 0.7: More Solid, Better Behaved, More Polite

date: 2018 Aug 03
tag: v0.7
commit: 22fd8f0

Marcam inside the dmg file should run on any Mac OS X that is Yosemite (10.10.5) or later.

The Marcam Windows Installer was created on a Windows 10 Home version 1803.

Notable improvements:
* Vast improvement of image rendering.  Removes occasional image artifacts previously visible. (Issue #90)
* Image processing operations under the Tools menu
  * Invert Image
  * Image False Color
  * Image Auto-contrast (Issue #77)
  * Image Info
* Edit-\>Undo/Redo now tell you in the menu text what you are about to Undo or Redo (Issue #92)
* Filename now in titlebar of window.  (Also right-clickable icon on Mac.) (Issue #82)
* Windows: now knows Marcam handles .mcm files, Marcam file icons on .mcm files in Windows. (Issues #79, #84)
* Windows: remove jitter during zoom
* Windows: improvements in image rendering (using buffered drawing to window)
* Mac: Closing last window keeps app open with no windows, as is typical for a Mac app.
* Dialog boxes handle all errors for file open, save, etc. (Issue #96)
* Menu items disabled appropriately when no image. (Issue #97)
* Images with an Alpha channel now are displayed on white background, rendered properly. (Issue #73)
* New Debug Menu (only visible if developer is in Debug mode)
* Dragging while scrolling improved (but not perfect)
* New version of the \*.mcm file format.  Program still opens legacy files.  New files saved in new version.

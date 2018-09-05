# Version 0.6: More Functionality, More Polish, More Bugfixes

date: 2018 Jul 21
tag: v0.6
commit: edfa28f

Notable Improvements:
* Toolbar buttons look nicer, and more toolbar buttons.
* Zoom In, Zoom Out, Zoom Fit: New menu items, new toolbar buttons.
* Copy to Clipboard toolbar button. (Issue #69)
* File-\>Open Recent now works properly again.
* Now images with an alpha channel (transparency) will display properly in the application. (Issue #73)
* Big fix with rendering should speed up most zooms, and help (a bit) flicker/jitter in Windows.
* Windows: Open Files now defaults to showing all openable files. (Not only one type.) (Issue #70)
* Mac: \*.mcm files now properly show the Marcam Document icon.
* Experimental new Tools: Image Info, Image Auto-Contrast.
* Windows: App now has proper icon in titlebar. (Issue #65)
* Bugfix: Window was not totally repainted before, (a few pixels in the corners were missing).
* Bugfix: App used to grow in height each time it was opened/closed.
* Mac: Bugfix: Corner between scrollbars is not repainted properly. (Issue #20)
* Internal build improvements.
* Lots of internal file cleanup.

Marcam inside the dmg file should run on any Mac OS X that is Yosemite (10.10.5) or later.

The Marcam Windows Installer was created on a Windows 10 Home version 1803.

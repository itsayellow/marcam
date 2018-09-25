# Version 0.9 What's New

[Last Modified Sep 4, 2018]

date: 2018 
tag: v0.9
commit: 

Marcam inside the dmg file should run on any Mac OS X that is Yosemite (10.10.5) or later.

The Marcam Windows Installer was created on a Windows 10 Home version 1803.

Notable improvements:
* Fixed bug where Mac Marcam wouldn't open file properly by double-clicking
  file to start program. (#134)
* Made File-\>Open Recent paths relative to home directory. (#128)
* Clean up and simplify (remove) some statusbar text. 
* File Load and Save of .mcm files sped up (about 20%) by doing more in-memory operations.
* More errors are routed to log files for better transparency on crashes.
* Fix bug where window close didn't update internal data structures, resulting in instability. (#144)
* Use progress dialog with File -> Export Image... (#143)
* Optimize by only tracking mouse motion while dragging. (#141)
* Cleaned up text in pre-close "Do you want to save?" query dialog.
* Fixed bug where file was mistakenly thought of as "saved" when it was not.
* Use progress dialog for all image processing tasks.
* Create error dialogs for remaining open/save file errors that don't have one.
* Performance: Implement cache dir and advance conversion of image to output file in background.
* Unify handling of preferences.
* (Internal) Automated pylint checks using Jenkins. (#146)
* (Internal) Clean up some event-handling details (make sure all handlers execute via Skip()). (#142)
* (Internal) Upgrade to PyInstaller 3.4, with better support for writing Info.plist. (#137)
* (Internal) Upgrade to Python 3.7. (#138)

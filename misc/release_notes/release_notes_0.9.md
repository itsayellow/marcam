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
* File Load and Save is sped up (about 20%) by doing more in-memory operations.
* More errors are routed to log files for better transparency on crashes.
* (Internal) Setup automated testing to improve bug-catching.

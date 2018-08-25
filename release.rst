Marcam Release Instructions / Checklist
=======================================

Summary
-------

1. Make sure it builds, installs, runs on all platforms.
#. Increase version numbers

   i. file: build_scripts/Info.plist 

      a. ``<string>``\ <version_num>\ ``</string>``
      #. ``<string>``\ <version_num>\ ``</string>``

   #. file: marcam/const.py

      #. ``VERSION_STR = "``\ <version_num>\ ``"``

#. Check in
#. Github: write new release and tag it v0.0.7

   i. In separate tab, look over all commits since last release to write up
      notable changes.

#. Build Installers

   i. In Windows, upload installer as "Marcam <version_num> Windows Installer.exe" to Github release.
   #. On Mac, upload dmg file as "Marcam <version_num> Mac.dmg" to Github release.

#. Update Website for new release

   i. Edit the front page of website under branch gh-pages under Downloads

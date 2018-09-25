Marcam Release Instructions / Checklist
=======================================

Summary
-------

1. Make sure it builds, installs, runs on all platforms.
#. Increase version numbers

   a. file: marcam/const.py

      i. ``VERSION_STR = "``\ <version_num>\ ``"``
      #. ``VERSION_PLIST_STR = "``\ <version_num>\ ``"``

#. Check in
#. Github: write new release and tag it v0.7.0

   a. Use misc/release_notes/release_notes_<version_num>.md as a basis
   #. In separate tab, look over all commits since last release to write up
      notable changes.

#. Build Installers

   a. In Windows, upload installer as "Marcam <version_num> Windows Installer.exe" to Github release.
   #. On Mac, upload dmg file as "Marcam <version_num> Mac.dmg" to Github release.

#. Update Website for new release

   a. Edit the front page of website under branch gh-pages under Downloads

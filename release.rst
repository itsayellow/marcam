Marcam Release Instructions / Checklist
=======================================

Summary
-------

1. Increase version numbers

   i. file: build_scripts/Info.plist 

      a. ``<string>``\ <version_num>\ ``</string>``
      #. ``<string>``\ <version_num>\ ``</string>``

   #. file: marcam/const.py

      #. ``VERSION_STR = "``\ <version_num>\ ``"``

#. Check in
#. Github: write new release and tag it v0.0.7

   i. In separate tab, look over all commits since last release to write up
      notable changes.



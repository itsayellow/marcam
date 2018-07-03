Marcam
======

Summary
-------

Marcam - a cross-platform application to automate counting of objects in images.  

Copyright 2017-2018 Matthew A. Clapp

Building
--------

Requires python > 3.6

macOS
~~~~~

#. ``make clean_all`` to remove all build directories and files.
#. ``make dmg`` to make the Mac .dmg bundle containing application and
   Applications directory alias

Windows
~~~~~~~

#. Install NSIS
#. ``make clean_all`` to remove all build directories and files.
#. ``make wininstall`` to make the Windows installer

Notes
--------
Application preferences on Mac stored at: "~/Library/Preferences/Marcam Preferences"

Developer Reference Notes
-------------------------

Creating a Mac Icon
~~~~~~~~~~~~~~~~~~~

To make a new icon

* create a photoshop psd document at 512x512
* export to png
* read in png file and then downsize to 32x32 and save as png

References
----------

* `reStructuredText Main Page <http://docutils.sourceforge.net/rst.html>`_
* `reStructuredText Markup Spec <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_
* `reStructuredText Directives <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

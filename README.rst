Marcam
======

Summary
-------

Marcam - a cross-platform application to automate marking and counting objects in images.  

Copyright |copy| 2017-2018 Matthew A. Clapp

.. |copy| unicode:: 0xA9 .. copyright sign

Installing
----------

Fetch the latest stable release (Windows installer, Mac dmg bundle, or
source) from https://github.com/itsayellow/marcam/releases

Building
--------

Requires python |gteq| 3.6

.. |gteq| unicode:: 0x2265 .. greater than or equal to

macOS
~~~~~

#. ``make clean_all`` to remove all build directories and files (including
   removal of virtual environment).
#. ``make dmg`` to make the Mac .dmg bundle containing application and
   Applications directory alias

Windows
~~~~~~~

#. Install NSIS
#. ``make clean_all`` to remove all build directories and files (including
   removal of virtual environment).
#. ``make wininstall`` to make the Windows installer

Developer Reference Notes
-------------------------

Configuration / Log File Locations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

macOS
"""""

Application Log files stored in the directory:
"~/Library/Logs/Marcam"

Application preferences stored in the file:
"~/Library/Application Support/Marcam/config.json"

Windows
"""""""

Application Log files stored in the directory:
"C:\\Users\\<username>\\AppData\\Local\\Marcam"

Application preferences stored in the file:
"C:\\Users\\<username>\\Appdata\\Local\\Marcam\\config.json"

reStructuredText References
---------------------------

* `reStructuredText Main Page <http://docutils.sourceforge.net/rst.html>`_
* `reStructuredText Markup Spec <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_
* `reStructuredText Directives <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

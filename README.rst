Marcam
======

Summary
-------

Marcam - a cross-platform application to automate counting of objects in images.  

Copyright |copy| 2017-2018 Matthew A. Clapp

.. |copy| unicode:: 0xA9 .. copyright sign

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

Notes
--------
Application preferences on Mac stored at: "~/Library/Preferences/Marcam Preferences"

Developer Reference Notes
-------------------------

Creating a Mac Toolbar Icon
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To make a new icon

* create a photoshop psd document at 512x512
* export to png
* read in png file and then downsize to 32x32 and save as png

References
----------

* `reStructuredText Main Page <http://docutils.sourceforge.net/rst.html>`_
* `reStructuredText Markup Spec <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_
* `reStructuredText Directives <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

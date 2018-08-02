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

Using
-----

Try pushing and holding the space bar at any time for a temporary zoom, 
centered where the mouse pointer is.
Useful for detailed examination or marking.

The help from the help menu is short and useful.  You can view it to quickly
understand the basic functionality of the application.

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

Linux
~~~~~

(Preliminary.  Still a work in progress.)

The following almost works, but dumps core after the user mouses over the app.

#. sudo apt-get install python3-venv
#. sudo apt-get install python3-wxgtk4.0
#. sudo apt-get install python3-wxgtk-webview4.0
#. python3 -m venv --system-site-packages virt
#. source virt/bin/activate
#. pip3 install wheel
#. pip3 install appdirs biorad1sc-reader numpy Pillow PyInstaller

Configuration / Log File Locations
----------------------------------

macOS
~~~~~

Application Log files stored in the directory:
"~/Library/Logs/Marcam"

Application preferences stored in the file:
"~/Library/Application Support/Marcam/config.json"

Windows
~~~~~~~

Application Log files stored in the directory:
"C:\\Users\\<username>\\AppData\\Local\\Marcam\\Logs"

Application preferences stored in the file:
"C:\\Users\\<username>\\AppData\\Local\\Marcam\\config.json"

Documentation References
------------------------

* `Creating and Hosting a Personal Site on GitHub <http://jmcglone.com/guides/github-pages/>`_
* `Get Started With GitHub Pages (Plus Bonus Jekyll) <https://24ways.org/2013/get-started-with-github-pages/>`_
* `reStructuredText Main Page <http://docutils.sourceforge.net/rst.html>`_
* `reStructuredText Markup Spec <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_
* `reStructuredText Directives <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

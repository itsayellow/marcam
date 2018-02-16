Marcam
======

Summary
-------

Marcam - a cross-platform application to automate counting of objects in images.  

Copyright 2017-2018 Matthew A. Clapp

Building
--------

#. ``make clean`` to remove all build directories and files.
#. ``make app`` to make the Mac application
#. ``make dmg`` to make the Mac .dmg bundle containing application and
   Applications alias

To generate a new requirements.txt::

    source virt/bin/activate
    pip3 freeze --all > requirements.txt

To make a new icon

* create a photoshop psd document at 512x512
* export to png
* read in png file and then downsize to 32x32 and save as png

Notes
--------
Application preferences on Mac stored at: "~/Library/Preferences/Marcam Preferences"

References
----------

* `reStructuredText Main Page <http://docutils.sourceforge.net/rst.html>`_
* `reStructuredText Markup Spec <http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html>`_
* `reStructuredText Directives <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

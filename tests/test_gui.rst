Manual Testing of Marcam GUI
============================

Test in Windows.

Test in macOS.

Every time we notice something broken, add it here to test.

MCM File Format - Save Normal
-----------------------------

Procedure
~~~~~~~~~

Save a \*.mcm file. Load it back.

Expected Results
~~~~~~~~~~~~~~~~

#. No errors in the log or dialog boxes errors.
#. Same image
#. Same marks

MCM File Format - Load from Unreadable
--------------------------------------

Procedure
~~~~~~~~~

Change a \*.mcm file to be unreadable (`chmod a-r <file>`).
Try to load unreadable \*.mcm file

Expected Results
~~~~~~~~~~~~~~~~

#. A dialog box informing user that this file is unreadable.

File Formats - Load
-------------------

Procedure
~~~~~~~~~

#. Load \*.1sc file
#. Load \*.mcm file (new)
#. Load \*.mcm file (old, legacy)
#. Load \*.png file

Expected Results
~~~~~~~~~~~~~~~~

#. Files able to load normally.
#. No errors in dialogs or in log.

Zoom
----

Procedure
~~~~~~~~~

Zoom in all the way, then zoom out all the way.

Expected Results
~~~~~~~~~~~~~~~~

#. The image shows no odd artifacts at any zoom level.
#. The image does not appear to jitter in position.
#. The image does not appear to shimmer in its composition.
#. The boundary rectangles draw properly when the image is smaller than the
   window.

Zoom - Debug Paint Turned On
----------------------------

Procedure
~~~~~~~~~

Enable `_debug_paint_client_area` to see red outlines on boundary fill
rectangles.

Expected Results
~~~~~~~~~~~~~~~~

#. The boundary rectangles look like

   * two rectangles spanning the top and bottom
   * two other rectangles on the sides (the same height as the image)


Rubberband box
--------------

Procedure
~~~~~~~~~

Drag a rubberband box.

Expected Results
~~~~~~~~~~~~~~~~

1. The box shows up

   * in translucent blue on Windows
   * in translucent white on macOS

2. The box does not flicker as you drag it larger or smaller.
3. The background image does not have visual artifacts where the box
   was dragged.

   * Test with single_pixel_lines.mcm to see if pixel aliasing under
     rubberband box is a problem.

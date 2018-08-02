Manual Testing of Marcam GUI
============================

Test in Windows.

Test in macOS.

Every time we notice something broken, add it here to test.

MCM File Format - Save
----------------------

#. Save a \*.mcm file
#. Load it back

File Formats - Load
-------------------

#. Load \*.1sc file
#. Load \*.mcm file (new)
#. Load \*.mcm file (old, legacy)
#. Load \*.png file

Zoom
----

Zoom in all the way, then zoom out all the way.

#. Does the image show odd artifacts at any zoom level?
#. Does the image appear to jitter in position?
#. Does the image appear to shimmer in its composition?
#. Do the boundary rectangles draw properly when the image is smaller than the
   window?

Enable `_debug_paint_client_area` to see red outlines on boundary fill
rectangles.

#. Do the boundary rectangles look like two rectangles spanning the top
   and bottom, with two other rectangles on the sides (the same height
   as the image)?


Rubberband box
--------------

Drag a rubberband box.

1. Does the box show up?

   * in translucent blue on Windows
   * in translucent white on macOS

2. Does the box flicker as you drag it larger or smaller?
3. Does the background matter have visual artifacts where the box
   was dragged?

   * test with single_pixel_lines.mcm to see if pixel aliasing under
     rubberband box is a problem

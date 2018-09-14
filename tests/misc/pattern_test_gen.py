#!/usr/bin/env python3
"""Generate test images to test image_proc.py colormap functions.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.cm

def rgb_from_array(input_array, cmap='gray'):
    if cmap=='gray':
        image_rgba = matplotlib.cm.gray(input_array)
    else:
        image_rgba = matplotlib.cm.cmaps_listed[cmap](input_array)

    return np.round(image_rgba * 255).astype(np.uint8)

def read_print_imfile(imfilename):
    test_img_invert_load = plt.imread(imfilename)
    test_img_invert_load = test_img_invert_load * 255 / np.max(test_img_invert_load)
    for (i, byte) in enumerate(test_img_invert_load.flatten()[0:256*3]):
        byte = int(byte)
        print("%02x"%byte, end=" ")
        if (i+1) % 16 == 0:
            print("")
        if (i+1) % (8*16) == 0:
            print("")

def main():
    ascending = [list(range(0,256))]*20
    descending = [list(range(255,-1,-1))]*20
    test_img_array = np.array(ascending + descending + ascending + descending)

    plt.imsave('test_gray.png', rgb_from_array(test_img_array))

    for colormap in ['viridis', 'plasma', 'magma', 'inferno']:
        # This would be the simplest way, but due to a bug in matplotlib,
        #   it maps floating-point to uint8 without rounding. (Issue #12071)
        # https://github.com/matplotlib/matplotlib/issues/12071
        #plt.set_cmap(colormap)
        #plt.imsave('test_' + colormap + '.png', test_img_array, vmin=0, vmax=255)

        plt.imsave(
                'test_' + colormap + '.png',
                rgb_from_array(test_img_array, cmap=colormap)
                )

    test_img_invert_array = 255 - test_img_array
    plt.imsave(
            'test_gray_invert.png',
            rgb_from_array(test_img_invert_array)
            )
    #read_print_imfile('test_gray_invert.png')


if __name__ == '__main__':
    main()


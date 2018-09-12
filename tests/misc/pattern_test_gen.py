#!/usr/bin/env python3
"""Generate test images to test image_proc.py colormap functions.
"""

import numpy as np
import matplotlib.pyplot as plt

def rgb_from_grayscale(input_array):
    return np.array([input_array.T,input_array.T,input_array.T]).T

def main():
    ascending = [list(range(0,256))]*20
    descending = [list(range(255,-1,-1))]*20
    test_img = np.array(ascending + descending + ascending + descending)
    plt.imsave('test_gray.png', rgb_from_grayscale(test_img), vmin=0, vmax=255)

    for colormap in ['viridis', 'plasma', 'magma', 'inferno']:
        plt.set_cmap(colormap)
        plt.imsave('test_' + colormap + '.png', test_img, vmin=0, vmax=255)

    plt.set_cmap('gray')
    test_img_invert = 255 - test_img
    plt.imsave(
            'test_gray_invert.png',
            rgb_from_grayscale(test_img_invert)
            )

    test_img_invert_load = plt.imread('test_gray_invert.png')
    test_img_invert_load = test_img_invert_load * 255 / np.max(test_img_invert_load)
    for (i, byte) in enumerate(test_img_invert_load.flatten()[0:256*3]):
        byte = int(byte)
        print("%02x"%byte, end=" ")
        if (i+1) % 16 == 0:
            print("")
        if (i+1) % (8*16) == 0:
            print("")


if __name__ == '__main__':
    main()


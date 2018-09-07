#!/usr/bin/env python3
"""Generate test images to test image_proc.py colormap functions.
"""

import numpy as np
import matplotlib.pyplot as plt

def main():
    ascending = [list(range(0,256))]*20
    descending = [list(range(255,-1,-1))]*20
    test_img = np.array(ascending + descending + ascending + descending)

    for colormap in ['gray', 'viridis', 'plasma', 'magma', 'inferno']:
        plt.set_cmap(colormap)
        plt.imsave('test_' + colormap + '.png', test_img, vmin=0, vmax=255)

if __name__ == '__main__':
    main()


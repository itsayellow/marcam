#!/usr/bin/env python3
"""Test imsave using gray colormap
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import PIL

def print_arrays_cols(*args):
    for i in range(len(args[1])):
        row_vals = []
        for (j, arg) in enumerate(args):
            print("%.3f"%(arg[i]), end="")
            if j < len(args)-1:
                print("\t\t", end="")
            row_vals.append(arg[i])
        if all([x==row_vals[0] for x in row_vals]):
            print("")
        else:
            print(" ****")

def main():
    plt.gray()
    test_array = np.vstack((np.arange(0,256), np.arange(0,256)))
    test_array_cm_gray = matplotlib.cm.gray(test_array)
    # scale max to 255
    test_array_cm_gray = test_array_cm_gray * 255
    # save test_array to png
    plt.imsave('testme.png', test_array, format='png')
    # save test_array to tiff
    plt.imsave('testme.tif', test_array, format='tiff')

    # imread from png
    test_png_load = plt.imread('testme.png')
    # scale max to 255
    test_png_load = test_png_load * 255
    # imread from tiff
    test_tiff_load = plt.imread('testme.tif')
    # pil open from png
    pil_png_image = PIL.Image.open('testme.png')
    test_png_pil_load = list(pil_png_image.getdata())
    # just get first row, and R of RGBA
    test_png_pil_load = [x[0] for x in test_png_pil_load[0:256]]
    # pil open from tiff
    pil_tiff_image = PIL.Image.open('testme.tif')
    test_tiff_pil_load = list(pil_tiff_image.getdata())
    # just get first row
    test_tiff_pil_load = test_png_pil_load[0:256]

    # print orig, colormap, and 2 methods of loading png image data
    print("test_array\tcm.gray()\tpng_pil_load\tpng_imread_load")
    print("----------\t---------\t------------\t---------------")
    print_arrays_cols(
            test_array[0,:].flatten(),
            test_array_cm_gray[0,:,0].flatten(),
            test_png_pil_load,
            test_png_load[0,:,0].flatten(),
            )

    # print orig, colormap, and 2 methods of loading tiff image data
    print("")
    print("test_array\tcm.gray()\ttiff_pil_load\ttiff_imread_load")
    print("----------\t---------\t-------------\t----------------")
    print_arrays_cols(
            test_array[0,:].flatten(),
            test_array_cm_gray[0,:,0].flatten(),
            test_tiff_pil_load,
            test_tiff_load[0,:,0].flatten(),
            )

if __name__ == '__main__':
    main()

#!/usr/bin/env python3

# generate colormap python code for colormaps.py

import colormaps

def print_array(data_array):
    for i in range(int(len(data_array)/4)):
        print("    [ %d, %d, %d],"%(
            round(data_array[i*4][0]*255),
            round(data_array[i*4][1]*255),
            round(data_array[i*4][2]*255)
            ), end="")
        print(" [ %d, %d, %d],"%(
            round(data_array[i*4+1][0]*255),
            round(data_array[i*4+1][1]*255),
            round(data_array[i*4+1][2]*255)
            ), end="")
        print(" [ %d, %d, %d],"%(
            round(data_array[i*4+2][0]*255),
            round(data_array[i*4+2][1]*255),
            round(data_array[i*4+2][2]*255)
            ), end="")
        print(" [ %d, %d, %d],"%(
            round(data_array[i*4+3][0]*255),
            round(data_array[i*4+3][1]*255),
            round(data_array[i*4+3][2]*255)
            ))

print("MAGMA_DATA = np.array([")
print_array(colormaps.MAGMA_DATA)
print("], dtype='uint8')")
print("")

print("INFERNO_DATA = np.array([")
print_array(colormaps.INFERNO_DATA)
print("], dtype='uint8')")
print("")

print("PLASMA_DATA = np.array([")
print_array(colormaps.PLASMA_DATA)
print("], dtype='uint8')")
print("")

print("VIRIDIS_DATA = np.array([")
print_array(colormaps.VIRIDIS_DATA)
print("], dtype='uint8')")

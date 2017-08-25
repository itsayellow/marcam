#!/usr/bin/env python3

# testbed to read *.1sc files

import os
import sys
import os.path
import struct

"""
Directly cited by field_type=16
    Need format of type=1000
    Need format of type=1007
    Need format of type=1022

NOTES:
--------
Header
    <2-byte field_type>
    <2-byte byte length of entire field (len(Header) + len(Payload))>
    <4-byte possible index or other>
Payload
    <bytes or ushort or int or uint until end of field>

--------
field_type=0=0x0
    end of data, beginning of 0 fill (control field)
    always field_len=8
    header only
    header contains only 0's except for field_len=8
    jump after this field type
field_type=100=0x64
    data (int or uint)
    inside data, uint (or int) matches field names in field_type=16=0x10
    comes BEFORE data_field_names block
field_type=16=0x10
    data_field_names (string)
    last 4 bytes of header (uint or int) matches number in field_type=100
    data field_payload
    comes AFTER field_type=100 data
field_type=1000=0x03e8
    has date and scanner name in text, amongst binary

fiel_type>999 may have negative-valued ints (or it may be other data)

After 380, all zeros, ending in bytes:
    0xbf,0x0d,0x00,0x00,0x04,0x00,0x00,0x00
    0x00000dbf, 0x00000004

--------
bio-formats.java:
    codeFound == 0x81 (field_type)
    baseFP = <byte_idx of start of payload of field_type=0x81> + 2
    skip = <int of the first 4-bytes of field_type=0x81> - 32
    diff = 352-baseFP
    skip = skip + diff
    <scanner_name> at baseFP + skip - 8187
    <date_str> at baseFP + skip - 298
    <scanner_str> at baseFP + skip - 208
    at baseFP + skip:
        <2-byte_x_size_ushort>
        <2-byte_y_size_ushort>
        <2-byte_??>
        <2-byte_bpp_ushort>

    at 59654 (if diff==0) or 59654+62 or 59654-196-2*x
    i.e 91 bytes after the string "scn" + <getShort len> + 32
    i.e file_end - planeSize

    e.g. test.1sc:
        baseFP = 350
        skip = 58385 - 32 = 58353
        diff = 2
        skip = 58355
        <scanner_name> at 350 + 58355 - 8187 = 50518
            ACTUAL???
            <scanner_name> at 50246
        <date_str> at 350 + 58353 - 298 = 58405 
            ACTUAL???
            <date_str> at 58407
        <scanner_string> at 350 + 58353 - 208 = 58495
            ACTUAL???
            <date_str> at 58497

    x=0 left, y=0 top
    byte0 = first byte in image block
    pixel(x,y) at byte=xsize*((ysize-1)-y) + x
    pixel order in file:
            0               1               2               xsize-1
        (x=0,y=ysize-1), (x=1,y=ysize-1), (2,ysize-1) .. (xsize-1,ysize-1),
            xsize           xsize+1         xsize+2         2*xsize-1
        (x=0,y=ysize-2), (x=1,y=ysize-2), (2,ysize-2) .. (xsize-1,ysize-2),
            2*xsize         2*xsize+1       2*xsize+2       3*xsize-1
        (x=0,y=ysize-3), (x=1,y=ysize-3), (2,ysize-3) .. (xsize-1,ysize-3),

--------
test.1sc:
    BitsPerPixel   16
    DimensionOrder    XYCZT
    IsInterleaved    false
    IsRGB   false
    LittleEndian   true
    PixelType uint16
    Series 0 Name    test.1sc
    SizeC   1
    SizeT  1
    SizeX 696
    SizeY    520
    SizeZ   1
    Location    /Users/mclapp/git/cellcounter/docs/test.1sc
    Scanner name    ChemiDoc XRS

    696*520*2bytes = 723840bytes
    696*520*2bytes = 36190 ushorts(2-byte)

    image data 59946 - 783785 (last byte of file)

"""
def print_list(byte_list, bits=8, dec_not_hex=True, address=None):
    """
    TODO: is this doing proper little-endian?
    """
    # log10(2**bits) = log10(2)*bits = 0.301*bits
    # log16(2**bits) = log16(2)*bits = 0.25*bits
    hex_digits = int(0.25 * bits)
    # add 3 chars for "0x" and ","
    # number of items in a line
    items = 72//(hex_digits+3)
    # round items down to multiple of 4
    items = items//4*4
    pr_str = "{:%dd},"%(hex_digits+2)
    pr_str_hex = "0x{:0%dx},"%(hex_digits)

    byte_groups = range(0, len(byte_list), items)
    byte_groups = [[x, min([x+items, len(byte_list)])] for x in byte_groups]

    if address is None:
        print("\t[", end="")
        first_loop = True
        for (i,byte_group) in enumerate(byte_groups):
            if first_loop:
                first_loop=False
            else:
                print("\t ", end="")

            # print decimal words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str.format(byte), end="")
            # print spacer
            print()
            print("         ", end="")
            # print hex words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str_hex.format(byte), end="")

            if i<len(byte_groups)-1:
                print()
        print("]")
    else:
        first_loop = True
        for (i,byte_group) in enumerate(byte_groups):
            # print address start
            if len(byte_groups) > 1:
                print("    %6d: "%(address+i*items*bits/8), end="")
            else:
                print("            ", end="")
            # print decimal words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str.format(byte), end="")
            print()

            # print spacer
            print("            ", end="")
            # print hex words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str_hex.format(byte), end="")
            print()


def str_safe_bytes(byte_stream):
    table_from = bytes(range(256))
    table_to = b'\x20' + b'\xff'*31 + bytes(range(32,127)) + b'\xff'*129
    trans_table = byte_stream.maketrans( table_from, table_to )
    safe_byte_stream = byte_stream.translate(trans_table)
    return safe_byte_stream
    

def debug_generic(byte_stream, byte_start, note_str, format_str, quiet=False):
    bytes_per = struct.calcsize(format_str)
    num_shorts = len(byte_stream)//(bytes_per)
    out_shorts = struct.unpack("<"+format_str*num_shorts, byte_stream)
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx-1), end="")
        print("\t"+note_str+":")
        print_list(
                out_shorts,
                bits=bytes_per*8,
                address=byte_start
                )
        print()
    return (out_shorts, byte_idx)


def debug_ints(byte_stream, byte_start, note_str, quiet=False):
    (out_ints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "i", quiet=quiet)
    return (out_ints, byte_idx)


def debug_uints(byte_stream, byte_start, note_str, quiet=False):
    (out_uints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "I", quiet=quiet)
    return (out_uints, byte_idx)


def debug_ushorts(byte_stream, byte_start, note_str, quiet=False):
    (out_shorts, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "H", quiet=quiet)
    return (out_shorts, byte_idx)


def debug_bytes(byte_stream, byte_start, note_str, quiet=False):
    (out_bytes, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "B", quiet=quiet)
    return (out_bytes, byte_idx)

def debug_string(byte_stream, byte_start, note_str, multiline=False, quiet=False):
    chars_in_line = 30
    out_string = byte_stream.decode("utf-8","replace")
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx - 1), end="")
        print("\t"+note_str+":")
        if multiline:
            for i in range(1+len(byte_stream)//chars_in_line):
                byte_substream = byte_stream[i*chars_in_line:(i+1)*chars_in_line]
                byte_substring = str_safe_bytes(byte_substream)
                out_substring = byte_substring.decode("utf-8","replace")
                print("    %5d: "%(byte_start+i*chars_in_line), end="")
                for char in out_substring:
                    print(" %s"%(char),end="")
                print()
                print("           "+byte_substream.hex())
        else:
            if len(out_string)>0 and out_string[-1]=='\x00':
                print("\t"+out_string[:-1])
            else:
                print("\t"+out_string)
    return (out_string, byte_idx)


def debug_nullterm_string(in_bytes, byte_start, note_str, quiet=False):
    byte_idx = byte_start
    while in_bytes[byte_idx] != 0:
        byte_idx += 1
    return debug_string(
            in_bytes[byte_start:byte_idx+1],
            byte_start, note_str, quiet=quiet
            )


def is_valid_string(byte_stream):
    try:
        out_string = byte_stream.decode("utf-8","strict")
    except:
        return False
    return True


def read_field(in_bytes, byte_idx, note_str="??", field_data={}):
    # 0     Jump Field - nop filler data
    #       Around data block boundaries
    #       Contains info about data block, at end and beginning of data block
    # 2     nop field - payload is all 0's, otherwise normal header

    # 16    String field - text label assigned to previous data through data_id
    #       Last 4 bytes of field header of this field is data_id that matches
    #       data_id uint in field_type=100 payload

    # 100   Data field - contains multiple data assigned to future text labels
    #       Last 4 bytes of field headers of field_type=16 is data_id that match
    #       data_id uints in this field payload
    #       Every 36 bytes is data item
    #       Bytes 12-15 are uint data_id tag
    # 101   Data field - contains multiple data assigned to future text labels
    #       Last 4 bytes of field headers of field_type=16 is data_id that match
    #       data_id uints in this field payload
    #       Every 20 bytes is data item
    #       Bytes 16-19 are uint data_id tag
    # 102   Data field - contains multiple data assigned to future text labels
    #       Last 4 bytes of field headers of field_type=16 is data_id that match
    #       data_id uints in this field payload
    #       Every 16 bytes is data item
    #       Bytes 12-15 are uint data_id tag
    # 131   Data field - contains multiple data assigned to future text labels
    #       Last 4 bytes of field headers of field_type=16 is data_id that match
    #       data_id uints in this field payload
    #       Every 12 bytes is data item
    #       Bytes 4-7 are uint data_id tag
    # 1000  Not fully understood - Irregular data block
    #       Sometimes for field_type= 16, sometimes not (??)
    #       Is format fixed based on which data block?
    # 1007  Not fully understood - Irregular data block
    #       Is format fixed based on which data block?
    # 1022  No data items, only data_id tags?
    #       4 uints in payload, first 3 uints are data_id tags
    #       Every 4 bytes is data item, last 4 bytes are not used (??)
    #       Bytes 0-3 are uint data_id tag


    # 126   Data Block 6
    #       1st uint a pointer to byte val=6180 4 uints before end of Jump Field,
    #       right before field_type=102, data corresponding to text label
    #       "Audit Trail"
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=140's data block
    # 127   Data Block 7
    #       1st uint a pointer to byte val=1020 4 uints before end of Jump Field,
    #       right before field_type=1000 with "Audit Trail" text inside
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=126's data block
    # 128   Data Block 8
    #       1st uint a pointer to byte val=7293 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=127's data block
    # 129   Data Block 9
    #       1st uint a pointer to byte val=1533 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=128's data block
    # 130   Data Block 10 - Image Data
    #       1st uint a pointer to byte val=68 4 uints before end of Jump Field,
    #       right at IMAGE DATA START
    #       ends at end of image data (could be end of file)
    #       Image data pointer
    #       uint[0] = img data start, uint[1] = img data length
    #       this starts after end of field_type=129's data block
    # 132   Data Block 2
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=143's data block
    # 133   Data Block 3
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=132's data block
    # 140   Data Block 5
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=141's data block
    # 141   Data Block 4
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=133's data block
    # 142   Data Block 0
    #       1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of long zero fill after 160-380 fields
    # 143   Data Block 1
    #       1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=142's data block

    # Not understood yet:
    # 1004
    # 1008
    # 1010
    # 1011
    # 1015
    # 1020
    # 1024
    # 1030
    # 1040
    
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", quiet=True)
    field_type = out_ushorts[0]
    if field_type==0:
        return_vals = read_field_type0(
                in_bytes, byte_idx,
                note_str=note_str
                )
    elif field_type==16:
        return_vals = read_field_type16(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==100:
        return_vals = read_field_type100(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==101:
        return_vals = read_field_type101(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==102:
        return_vals = read_field_type102(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==129:
        return_vals = read_field_type129(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==130:
        return_vals = read_field_type130(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==131:
        return_vals = read_field_type131(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==1000:
        return_vals = read_field_type1000(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==1007:
        return_vals = read_field_type1007(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    elif field_type==1022:
        return_vals = read_field_type1022(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data
                )
    else:
        return_vals = read_field_generic(
                in_bytes, byte_idx,
                note_str=note_str
                )
    
    return return_vals

def read_field_generic(in_bytes, byte_idx, note_str="??"):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    #(out_bytes, _) = debug_bytes(
    #        in_bytes[byte_idx:byte_idx+8], byte_idx, "bytes")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, byte_idx+8, note_str, multiline=True)
    (out_bytes, _) = debug_bytes(
            field_payload, byte_idx+8, "bytes")
    if len(field_payload)%2 == 0:
        (out_ushorts, _) = debug_ushorts(
                field_payload, byte_idx+8, "ushorts")
    if len(field_payload)%4 == 0:
        (out_uints, _) = debug_uints(
                field_payload, byte_idx+8, "uints")
        if any([x>0x7FFFFFFF for x in out_uints]):
            # only print signed integers if one is different than uint
            (out_ints, _) = debug_ints(
                    field_payload, byte_idx+8, "ints")

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    return (byte_idx+field_len, field_info)


def read_field_type0(in_bytes, byte_idx, note_str="??"):
    # Finding the end of the jump algorithm
    # READ:
    #   ushort field_type=0
    #   ushort 8
    #   ushort 0
    #   ushort 0
    #   4*ushort
    #   ushort A
    #   if A==0 read 6*ushort, goto prev else exit, return this idx
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_type = 0 has either field_len=0 or field_len=8

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)

    print("\n**** JUMP FIELD ****\n")
    # experimental jump
    #   used to only do this for field_len==8, but it seems to work for
    #   field_len==0 also!!
    byte_idx = byte_idx + 8
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    byte_idx = byte_idx + 8
    test_byte_idx_start = byte_idx
    all_zeros = True
    while( True ):
        # do the next 7 shorts start with a '0' value? if so keep looping
        (test_ushorts, _) = debug_ushorts(
                in_bytes[byte_idx:byte_idx+14],
                byte_idx,
                "ushorts",
                quiet=True)
        if test_ushorts[0]!=0:
            # next ushort was not 0, so it is valid field_type
            break
        if test_ushorts.count(0)==len(test_ushorts) and all_zeros==True:
            pass
        elif test_ushorts.count(0)!=len(test_ushorts) and all_zeros==True:
            all_zeros = False
            if byte_idx > test_byte_idx_start:
                print("%6d-%6d:"%(test_byte_idx_start,byte_idx-1))
                print("\tAll zeros %d*(0,)"%(byte_idx-test_byte_idx_start))
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx, "ushorts")
        else:
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx, "ushorts")
        byte_idx = byte_idx + 14
        
    field_info['type'] = field_type
    if field_len==8:
        return (byte_idx, field_info)
    else:
        return (byte_idx+field_len, field_info)


def read_field_type16(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", quiet=True)
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints", quiet=True)
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]
    data_tag = out_uints[1]
    print("Field Header:")
    print("\t[{:6d}, {:6d}, {:10d}]".format(field_type, field_len, data_tag))
    print("\t[0x{:04x}, 0x{:04x}, 0x{:08x}]".format(field_type, field_len, data_tag))

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, byte_idx+8, "string")
    if not is_valid_string(field_payload):
        # some byte does not resolve to valid utf-8 character
        print("invalid string")
        (out_bytes, _) = debug_bytes(
                field_payload, byte_idx+8, "bytes")
    if field_len !=0:
        if data_tag in field_data:
            print_list(field_data[data_tag], bits=32)
        else:
            print("DATA NOT FOUND")

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    return (byte_idx+field_len, field_info)


def read_field_type100(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # parse out_uints into data dict with keys of data_id
    for i in range(len(out_uints)//9):
        field_data[out_uints[i*9+3]] = out_uints[i*9:(i+1)*9]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type101(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # parse out_uints into data dict with keys of data_id
    for i in range(len(out_uints)//5):
        field_data[out_uints[i*5+4]] = out_uints[i*5:(i+1)*5]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type102(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # parse out_uints into data dict with keys of data_id
    for i in range(len(out_uints)//4):
        field_data[out_uints[i*4+3]] = out_uints[i*4:(i+1)*4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type129(in_bytes, byte_idx, note_str="??", field_data={}):
    """
    field_type==129 contains the pointer to the start of the data block
    before the image data
    """
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # out_uints[0] = data start
    # out_uints[1] = data length
    # out_uints[2] = ???

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type130(in_bytes, byte_idx, note_str="??", field_data={}):
    """
    field_type==130 contains the pointer to the start of the image data
    """
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # out_uints[0] = image data start
    # out_uints[1] = image data length
    # out_uints[2] = ???

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type131(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # parse out_uints into data dict with keys of data_id
    for i in range(len(out_uints)//3):
        field_data[out_uints[i*3+1]] = out_uints[i*3:(i+1)*3]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1000(in_bytes, byte_idx, note_str="??", field_data={}):
    # TODO: extract data for future field_type=16
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+4], byte_idx, "type, len")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]
    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20
    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)

    (out_ushorts, _) = debug_bytes(
            in_bytes[byte_idx+4:byte_idx+8], byte_idx, "bytes")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx+4:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx+4:byte_idx+8], byte_idx, "uints")

    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, byte_idx+8, "string", multiline=True)
    (out_ushorts, _) = debug_ushorts(
            field_payload, byte_idx+8, "ushorts")
    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1007(in_bytes, byte_idx, note_str="??", field_data={}):
    # TODO: extract data for future field_type=16
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1022(in_bytes, byte_idx, note_str="??", field_data={}):
    field_info = {}
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    print("field_type= %d"%field_type)
    print("field_len = %d"%field_len)
    print()
    print("Field Payload:")

    # read payload 
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints")
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    # first three uints are data_id tags, no associated data
    field_data[out_uints[0]] = []
    field_data[out_uints[1]] = []
    field_data[out_uints[2]] = []

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def jump_idx(jump_from, jump_to, chk_field_start, chk_byte_idx):
    if chk_field_start==jump_from and chk_byte_idx==jump_from:
        print("---------------------------------------------------------")
        print("jump of delta {0:d}=0x{0:x}".format(jump_to-jump_from))

        # find how many zeros:
        test_byte_stream = in_bytes[jump_from:jump_to].lstrip(b'\x00')
        num_zeros = len(in_bytes[jump_from:jump_to])-len(test_byte_stream)
        if num_zeros > 0:
            print("%6d-%6d"%(jump_from,jump_from+num_zeros-1), end="")
            print("   All Zeros %d*(0,)"%(num_zeros))
            jump_from = jump_from+num_zeros

        #(out_bytes, _) = debug_bytes(
        #        in_bytes[jump_from:jump_to], jump_from, "jumped bytes")
        (out_shorts, _) = debug_ushorts(
                in_bytes[jump_from:jump_to], jump_from, "jumped shorts")
        return jump_to
    else:
        return byte_idx

def search_backwards(in_bytes, field_start, level=0, min_search_idx=0):
    idx = field_start - 2
    possibles=[]
    while(idx >= min_search_idx):
        (test_ushorts, _) = debug_ushorts(
                in_bytes[idx:idx+2], idx, "ushorts", quiet=True)
        test_ushort = test_ushorts[0]
        if idx - 2 + test_ushort == field_start:
            #read_field(in_bytes, idx-2, note_str="field")
            possibles.append(idx-2)
        idx = idx-1
    for possible_idx in possibles:
        print("  "*level+"idx=%d: possible field start, back from %d"%(possible_idx,field_start))
        search_backwards(
                in_bytes,
                possible_idx,
                level=level+1,
                min_search_idx=min_search_idx
                )


def parse_datablock(field_payload):
    (out_uints, _) = debug_uints(field_payload, 0, "", quiet=True)
    data_start = out_uints[0]
    data_len = out_uints[1]
    return(data_start, data_len)


def print_datablock(data_start, data_len, block_name):
    print()
    print()
    print()
    print("=====================================================================")
    print("DATA BLOCK %s"%block_name)
    print("Start: %d"%(data_start))
    print("End:   %d"%(data_start + data_len))
    print()

    byte_idx = data_start
    # read first 4 ushorts
    (out_uints, byte_idx) = debug_ushorts(in_bytes[byte_idx:byte_idx+8],
            byte_idx,
            "Data Block %s Header"%block_name
            )

    field_data = {}
    while( byte_idx < data_start + data_len ):
        field_start = byte_idx
        (byte_idx, field_info) = read_field(in_bytes, byte_idx, field_data=field_data)
        if 'data' in field_info:
            field_data = field_info['data']


filename = os.path.realpath(sys.argv[1])

print(filename)

with open(filename, 'rb') as in_fh:
    in_bytes = in_fh.read()

byte_idx = 160

#SEARCH DEBUG
#search_backwards(in_bytes, len(in_bytes)-1, min_search_idx=59881)
#exit()

# field_data is data from last field_type=100 field, to be used in
#   following field_type=16 fields
field_data = {}
img_data_start = 0xffffffff
while( byte_idx < len(in_bytes) ):
    field_start = byte_idx
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, field_data=field_data)
    if 'data' in field_info:
        field_data = field_info['data']
    if field_info['type']==127:
        (data07_start, data07_len) = parse_datablock(field_info['payload'])
        print("Field Type 127 - Data Block 07 (???)")
        print("    data starts at byte %d"%(data07_start))
        print("    data length is %d bytes"%(data07_len))
    if field_info['type']==128:
        (data08_start, data08_len) = parse_datablock(field_info['payload'])
        print("Field Type 128 - Data Block 08 (???)")
        print("    data starts at byte %d"%(data08_start))
        print("    data length is %d bytes"%(data08_len))
    if field_info['type']==129:
        (data09_start, data09_len) = parse_datablock(field_info['payload'])
        print("Field Type 129 - Data Block 09 (???)")
        print("    data starts at byte %d"%(data09_start))
        print("    data length is %d bytes"%(data09_len))
    if field_info['type']==130:
        (img_data_start, img_data_len) = parse_datablock(field_info['payload'])
        print("Field Type 130 - Data Block 10 (Image Data)")
        print("    data starts at byte %d"%(img_data_start))
        print("    data length is %d bytes"%(img_data_len))

    # break if we still aren't advancing
    if byte_idx==field_start:
        print("ERROR BREAK!!!!")
        print("--------------------------------------------------------------")
        break

    if byte_idx > img_data_start:
        print("--------------------------------------------------------------")
        print("We passed the start of img data, so BREAK!!")
        print("--------------------------------------------------------------")
        break

# parse data blocks

# Data Block 7
print_datablock(data07_start, data07_len, "7")

# Data Block 8
print_datablock(data08_start, data08_len, "8")

# Data Block 9
print_datablock(data09_start, data09_len, "9")

# Data Block 10 - Image Data
print("=====================================================================")
print("IMAGE DATA BLOCK")
print()
#print_datablock(img_data_start, img_data_len, "10")

img_data_end = img_data_start + img_data_len
print("Image Data: (%d-%d)"%(img_data_start,img_data_end-1))
#(img_ushorts, _) = debug_ushorts(
#        in_bytes[img_data_start:img_data_end],
#        img_data_start, "img_data")

#for img_ushort in img_ushorts:
#    print(img_ushort)

print()
print()

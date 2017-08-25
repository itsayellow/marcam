#!/usr/bin/env python3

# testbed to read *.1sc files

import os
import sys
import os.path
import struct

"""
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
field_type=129=0x81
    first int of payload is probably offset to get us to image data
        (from start of file?  from start of field?)
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
def print_list(byte_list, bits=8, dec_not_hex=True):
    # log10(2**bits) = log10(2)*bits = 0.301*bits
    # log16(2**bits) = log16(2)*bits = 0.25*bits
    hex_digits = int(0.25 * bits)
    # add 3 chars for "0x" and ","
    items = 72//(hex_digits+3)
    # get
    items = items//4*4
    if dec_not_hex:
        pr_str = "{:%dd},"%(hex_digits+2)
    else:
        pr_str = "0x{:0%dx},"%(hex_digits)

    byte_groups = range(0, len(byte_list), items)
    byte_groups = [[x, min([x+items, len(byte_list)])] for x in byte_groups]

    print("\t[", end="")
    first_loop = True
    for (i,byte_group) in enumerate(byte_groups):
        if first_loop:
            first_loop=False
        else:
            print("\t ", end="")

        for byte in byte_list[byte_group[0]:byte_group[1]]:
            print(pr_str.format(byte), end="")

        if i<len(byte_groups)-1:
            print()
    print("]")


def str_safe_bytes(byte_stream):
    table_from = bytes(range(256))
    table_to = b'\x20' + b'\xff'*31 + bytes(range(32,127)) + b'\xff'*129
    trans_table = byte_stream.maketrans( table_from, table_to )
    out_byte_stream = byte_stream.translate(trans_table)
    return out_byte_stream
    

def debug_generic(byte_stream, byte_start, note_str, format_str, quiet=False):
    bytes_per = struct.calcsize(format_str)
    num_shorts = len(byte_stream)//(bytes_per)
    out_shorts = struct.unpack("<"+format_str*num_shorts, byte_stream)
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx-1), end="")
        print("\t"+note_str+":")
        print_list(out_shorts, bits=bytes_per*8)
        print_list(out_shorts, bits=bytes_per*8, dec_not_hex=False)
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

def debug_string(byte_stream, byte_start, note_str, quiet=False):
    chars_in_line = 30
    out_string = byte_stream.decode("utf-8","replace")
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx - 1), end="")
        print("\t"+note_str+":")
        if len(byte_stream) > chars_in_line:
            for i in range(len(byte_stream)//chars_in_line):
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
    # 0     Jump Field - nop filler data (or used somehow?)
    # 2     nop field - payload is all 0's
    # 16    String field - text label assigned to previous data through data_id
    #       Last 4 bytes of field header of this field is data_id that matches
    #       data_id uint in field_type=100 payload
    # 100   Data field - contains multiple data assigned to future text labels
    #       Last 4 bytes of field headers of field_type=16 is data_id that match
    #       data_id uints in this field payload
    # 101   Data field - contains multiple data assigned to future text
    #       4 uint string matches data from field_type=100 assigned to
    #       field_type=16 text label
    # 102   Data field - contains multiple data assigned to future text
    #       4 uint string matches data from field_type=100 assigned to
    #       field_type=16 text label
    # 126   1st uint a pointer to byte val=6180 4 uints before end of Jump Field,
    #       right before field_type=102, data corresponding to text label
    #       "Audit Trail"
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=140's data block
    # 127   1st uint a pointer to byte val=1020 4 uints before end of Jump Field,
    #       right before field_type=1000 with "Audit Trail" text inside
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=126's data block
    # 128   1st uint a pointer to byte val=7293 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=127's data block
    # 129   1st uint a pointer to byte val=1533 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=128's data block
    # 130   1st uint a pointer to byte val=68 4 uints before end of Jump Field,
    #       right at IMAGE DATA START
    #       ends at end of image data (could be end of file)
    #       Image data pointer
    #       uint[0] = img data start, uint[1] = img data length
    #       this starts after end of field_type=129's data block
    # 131   ???
    # 132   1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=143's data block
    # 133   1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=132's data block
    # 140   1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=141's data block
    # 141   1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=133's data block
    # 142   1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of long zero fill after 160-380 fields
    # 143   1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=142's data block
    # 1000
    # 1004
    # 1007
    # 1008
    # 1010
    # 1011
    # 1015
    # 1020
    # 1022
    # 1024
    # 1030
    # 1040
    
    # field types:
    # may be zero-padding and not real field type
    # 0, 2,
    # string to go with data via id_tag
    # 16,
    # data for future field_type=16
    # 100, 101, 102,
    # 126, 127, 128, 129, 130, 131, 132, 133,
    # 140, 141, 142, 143,
    # 1000, 1007, 1008, 1010, 1011, 1015, 1020, 1022, 1024, 1030, 1040
    
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
            field_payload, byte_idx+8, note_str)
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
    # EXPERIMENTAL ALGORITHM FOR FINDING END OF JUMP
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
            print_list(field_data[data_tag], bits=32, dec_not_hex=True)
            print_list(field_data[data_tag], bits=32, dec_not_hex=False)
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
        field_data[out_uints[i*9+3]] = out_uints[i*9:i*9+9]

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
        field_data[out_uints[i*5+4]] = out_uints[i*5:i*5+5]

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
        field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

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

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

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

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1000(in_bytes, byte_idx, note_str="??", field_data={}):
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
            field_payload, byte_idx+8, "string")
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

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1007(in_bytes, byte_idx, note_str="??", field_data={}):
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

filename = os.path.realpath(sys.argv[1])

print(filename)

with open(filename, 'rb') as in_fh:
    in_bytes = in_fh.read()

byte_idx = 160
codeFound = False

#SEARCH DEBUG
#search_backwards(in_bytes, len(in_bytes)-1, min_search_idx=59881)
#exit()

# field_data is data from last field_type=100 field, to be used in
#   following field_type=16 fields
field_data = {}
img_data_idx_start = 0xffffffff
while( byte_idx < len(in_bytes) ):
    codeFound = False
    field_start = byte_idx
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, field_data=field_data)
    if 'data' in field_info:
        field_data = field_info['data']
    if field_info['type']==130:
        (out_uints, _) = debug_uints(field_info['payload'], 0, "", quiet=True)
        img_data_idx_start = out_uints[0]
        img_data_len = out_uints[1]
        print("Field Type 130")
        print("    img_data starts at byte %d"%(img_data_idx_start))
        print("    img_data length is %d bytes"%(img_data_len))

    # THESE JUMPS ARE OBSOLETE WITH field_type==0 JUMP LOGIC
    ## restart after garbage
    ## jump of 3768=0xeb8
    #byte_idx = jump_idx(380, 4148, field_start, byte_idx)

    ## jump of 118=0x76
    #byte_idx = jump_idx(7659, 7777, field_start, byte_idx)
    ## or:
    ## maybe wrong? field_type=0 with field_len=102 seems invalid
    ##byte_idx = jump_idx(7659, 7699, field_start, byte_idx)

    ## jump of 64=0x40
    #byte_idx = jump_idx(22710, 22774, field_start, byte_idx)
    ## jump of 36=0x24
    #byte_idx = jump_idx(23157, 23193, field_start, byte_idx)
    ## jump of 64=0x40
    #byte_idx = jump_idx(41995, 42059, field_start, byte_idx)

    ## jump of 106=0x6a
    #byte_idx = jump_idx(43570, 43676, field_start, byte_idx)
    ## or:
    ## maybe wrong?: field_type=29160, odd field_type
    ##byte_idx = jump_idx(43570, 44192, field_start, byte_idx) # may not be right

    ## jump of 64=0x40
    #byte_idx = jump_idx(49848, 49912, field_start, byte_idx)
    ## or:
    ##byte_idx = jump_idx(49848, 50050, field_start, byte_idx)
    ##byte_idx = jump_idx(49848, 50154, field_start, byte_idx)

    ## jump of 120=0x78
    #byte_idx = jump_idx(50924, 51044, field_start, byte_idx)
    ## or:
    ### jump of 132=0x84
    ##byte_idx = jump_idx(50924, 51056, field_start, byte_idx)

    ## jump of 64=0x40
    #byte_idx = jump_idx(58329, 58393, field_start, byte_idx)

    # NOTES:
    # image starts somewhere around 59946 in test.1sc
    # I think field_type==100 is data for preceding/following text fields

    # break if we still aren't advancing
    if byte_idx==field_start:
        print("BREAK!!!!")
        print("--------------------------------------------------------------")
        break

    if byte_idx > img_data_idx_start:
        print("--------------------------------------------------------------")
        print("We passed the img data, so BREAK!!")
        print("--------------------------------------------------------------")
        break

    if field_info['type']==0x81:
        print("Code Found")
        (out_uints, _) = debug_uints(
                field_info['payload'], field_start+8, "uints")
        interesting_field_start = field_start
        interesting1 = out_uints[0]
        #break

# jump to image 59946 - 783785 (last byte of file)
# jump of 28=0x1c
byte_idx = jump_idx(59918, 59946, field_start, byte_idx)

(out_ushorts, _) = debug_ushorts(
        in_bytes[59946:len(in_bytes)],
        59946, "img_data")

print("interesting1 = "+repr(interesting1))
print("interesting_field_start = "+repr(interesting_field_start))
print("interesting1 - 8161 = "+repr(interesting1-8161))

if (interesting1 - 8161) > 0:
    byte_idx = interesting1 - 8161
    print("byte_idx = "+repr(byte_idx))

    (byte_idx, field_info) = read_field(in_bytes, byte_idx, "Scanner Name")
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, "Number of Pixels")
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, "Image Area")
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, "Scan Memory Size")

(img_ushorts, _) = debug_ushorts(
        in_bytes[59918:len(in_bytes)], 59918, "ushorts", quiet=True)

for img_ushort in img_ushorts:
    print(img_ushort)
    
#  protected void initFile(String id) throws FormatException, IOException {
#    super.initFile(id);
#    in = new RandomAccessInputStream(id);
#
#    // if string at byte 48 is "Intel Format" then this is little-endian
#    // little endian means LSByte is first, then next MSByte, then next...
#    String check = in.readString(48);
#    if (check.indexOf("Intel Format") != -1) {
#      // order specifies little-endian if true, otw big-endian
#      in.order(true);
#    }
#
#    // seek - Seeks to the given offset within the stream.
#    // start at byte 160
#    in.seek(START_OFFSET);
#
#    boolean codeFound = false;
#    int skip = 0;
#    long baseFP = 0;
#
#    while (!codeFound) {
#      // readShort - Read two input bytes and return a short value.
#      short code = in.readShort();
#
#      if (code == 0x81) codeFound = true;
#      short length = in.readShort();
#
#      // skipBytes - Skip n bytes within the stream
#      in.skipBytes(2 + 2 * length);
#      if (codeFound) {
#        // getFilePointer - Gets the current (absolute) file pointer.
#        baseFP = in.getFilePointer() + 2;
#        if (length > 1) {
#          in.seek(in.getFilePointer() - 2);
#        }
#        // readInt - Read four input bytes and return an int value.
#        skip = in.readInt() - 32;
#      }
#      else {
#        if (length == 1) in.skipBytes(12);
#        else if (length == 2) in.skipBytes(10);
#      }
#    }
#
#    diff = BASE_OFFSET - baseFP;
#    skip += diff;
#
#    double physicalWidth = 0d, physicalHeight = 0d;
#    if (getMetadataOptions().getMetadataLevel() != MetadataLevel.MINIMUM) {
#      if (baseFP + skip - 8187 > 0) {
#        in.seek(baseFP + skip - 8187);
#        // readCString - Read a string of arbitrary length, terminated by a
#        //      null char.
#        String scannerName = in.readCString();
#
#        in.skipBytes(8);
#
#        // readCString - Read a string of arbitrary length, terminated by a
#        //      null char.
#        in.readCString();
#
#        in.skipBytes(8);
#
#        // readCString - Read a string of arbitrary length, terminated by a
#        //      null char.
#        String imageArea = in.readCString();
#
#        imageArea = imageArea.substring(imageArea.indexOf(':') + 1).trim();
#        int xIndex = imageArea.indexOf('x');
#        if (xIndex > 0) {
#          int space = imageArea.indexOf(' ');
#          if (space >= 0) {
#            String width = imageArea.substring(1, space);
#            int nextSpace = imageArea.indexOf(" ", xIndex + 2);
#            if (nextSpace > xIndex) {
#              String height = imageArea.substring(xIndex + 1, nextSpace);
#              physicalWidth = Double.parseDouble(width.trim()) * 1000;
#              physicalHeight = Double.parseDouble(height.trim()) * 1000;
#            }
#          }
#        }
#      }
#    }
#
#    in.seek(baseFP + skip - 298);
#    String date = in.readString(17);
#    date = DateTools.formatDate(date, "dd-MMM-yyyy HH:mm");
#    in.skipBytes(73);
#    String scannerName = in.readCString();
#    addGlobalMeta("Scanner name", scannerName);
#
#    in.seek(baseFP + skip);
#
#    CoreMetadata m = core.get(0);
#
#    m.sizeX = in.readShort() & 0xffff;
#    m.sizeY = in.readShort() & 0xffff;
#    if (getSizeX() * getSizeY() > in.length()) {
#      in.order(true);
#      in.seek(in.getFilePointer() - 4);
#      m.sizeX = in.readShort();
#      m.sizeY = in.readShort();
#    }
#    in.skipBytes(2);
#
#    int bpp = in.readShort();
#    m.pixelType = FormatTools.pixelTypeFromBytes(bpp, false, false);
#
#    offset = in.getFilePointer();
#
#    m.sizeZ = 1;
#    m.sizeC = 1;
#    m.sizeT = 1;
#    m.imageCount = 1;
#    m.dimensionOrder = "XYCZT";
#    m.rgb = false;
#    m.interleaved = false;
#    m.indexed = false;
#    m.littleEndian = in.isLittleEndian();
#
#    MetadataStore store = makeFilterMetadata();
#    MetadataTools.populatePixels(store, this);
#
#    if (date != null) {
#      store.setImageAcquisitionDate(new Timestamp(date), 0);
#    }
#    if (getMetadataOptions().getMetadataLevel() != MetadataLevel.MINIMUM) {
#      Length sizeX =
#        FormatTools.getPhysicalSizeX(physicalWidth / getSizeX());
#      Length sizeY =
#        FormatTools.getPhysicalSizeY(physicalHeight / getSizeY());
#
#      if (sizeX != null) {
#        store.setPixelsPhysicalSizeX(sizeX, 0);
#      }
#      if (sizeY != null) {
#        store.setPixelsPhysicalSizeY(sizeY, 0);
#      }
#    }
#  }
#

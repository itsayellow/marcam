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
def print_list(byte_list, bits=8, dec_not_hex=True, address=None,
        file=sys.stdout):
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
        print("\t[", end="", file=file)
        first_loop = True
        for (i,byte_group) in enumerate(byte_groups):
            if first_loop:
                first_loop=False
            else:
                print("\t ", end="", file=file)

            # print decimal words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str.format(byte), end="", file=file)
            # print spacer
            print(file=file)
            print("         ", end="", file=file)
            # print hex words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str_hex.format(byte), end="", file=file)

            if i<len(byte_groups)-1:
                print(file=file)
        print("]",file=file)
    else:
        first_loop = True
        for (i,byte_group) in enumerate(byte_groups):
            # print address start
            if len(byte_groups) > 1:
                print("    %6d: "%(address+i*items*bits/8), end="", file=file)
            else:
                print("            ", end="", file=file)
            # print decimal words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str.format(byte), end="", file=file)
            print(file=file)

            # print spacer
            print("            ", end="", file=file)
            # print hex words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str_hex.format(byte), end="", file=file)
            print(file=file)


def str_safe_bytes(byte_stream):
    table_from = bytes(range(256))
    table_to = b'\x20' + b'\xff'*31 + bytes(range(32,127)) + b'\xff'*129
    trans_table = byte_stream.maketrans( table_from, table_to )
    safe_byte_stream = byte_stream.translate(trans_table)
    return safe_byte_stream
    

def debug_generic(byte_stream, byte_start, note_str, format_str, quiet=False,
        file=sys.stdout):
    bytes_per = struct.calcsize(format_str)
    num_shorts = len(byte_stream)//(bytes_per)
    out_shorts = struct.unpack("<"+format_str*num_shorts, byte_stream)
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx-1), end="", file=file)
        print("\t"+note_str+":", file=file)
        print_list(
                out_shorts,
                bits=bytes_per*8,
                address=byte_start,
                file=file
                )
    return (out_shorts, byte_idx)


def debug_ints(byte_stream, byte_start, note_str, quiet=False, file=sys.stdout):
    (out_ints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "i", quiet=quiet, file=file)
    return (out_ints, byte_idx)


def debug_uints(byte_stream, byte_start, note_str, quiet=False, file=sys.stdout):
    (out_uints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "I", quiet=quiet, file=file)
    return (out_uints, byte_idx)


def debug_ushorts(byte_stream, byte_start, note_str, quiet=False, file=sys.stdout):
    (out_shorts, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "H", quiet=quiet, file=file)
    return (out_shorts, byte_idx)


def debug_bytes(byte_stream, byte_start, note_str, quiet=False, file=sys.stdout):
    (out_bytes, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "B", quiet=quiet, file=file)
    return (out_bytes, byte_idx)

def debug_string(byte_stream, byte_start, note_str, multiline=False,
        quiet=False, file=sys.stdout):
    chars_in_line = 30
    out_string = byte_stream.decode("utf-8","replace")
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        print("%6d-%6d"%(byte_start,byte_idx - 1), end="", file=file)
        print("\t"+note_str+":", file=file)
        if multiline:
            for i in range(1+len(byte_stream)//chars_in_line):
                byte_substream = byte_stream[i*chars_in_line:(i+1)*chars_in_line]
                byte_substring = str_safe_bytes(byte_substream)
                out_substring = byte_substring.decode("utf-8","replace")
                print("    %5d: "%(byte_start+i*chars_in_line), end="", file=file)
                for char in out_substring:
                    print(" %s"%(char),end="", file=file)
                print(file=file)
                print("           "+byte_substream.hex(), file=file)
        else:
            if len(out_string)>0 and out_string[-1]=='\x00':
                print("\t"+out_string[:-1], file=file)
            else:
                print("\t"+out_string, file=file)
    return (out_string, byte_idx)


def debug_nullterm_string(in_bytes, byte_start, note_str, quiet=False,
        file=sys.stdout):
    byte_idx = byte_start
    while in_bytes[byte_idx] != 0:
        byte_idx += 1
    return debug_string(
            in_bytes[byte_start:byte_idx+1],
            byte_start, note_str, quiet=quiet, file=file
            )


def is_valid_string(byte_stream):
    try:
        out_string = byte_stream.decode("utf-8","strict")
    except:
        return False
    return True


def read_field(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    # 0     Jump Field - nop filler data
    #       Around data block boundaries
    #       Contains info about data block, at end and beginning of data block
    # 2     nop field - payload is all 0's, otherwise normal header
    # 1004  nop field - payload is all 0's, otherwise normal header

    # 126   Data Block 6 Info
    #       1st uint a pointer to byte val=6180 4 uints before end of Jump Field,
    #       right before field_type=102, data corresponding to text label
    #       "Audit Trail"
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=140's data block
    # 127   Data Block 7 Info
    #       1st uint a pointer to byte val=1020 4 uints before end of Jump Field,
    #       right before field_type=1000 with "Audit Trail" text inside
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=126's data block
    # 128   Data Block 8 Info
    #       1st uint a pointer to byte val=7293 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=127's data block
    # 129   Data Block 9 Info
    #       1st uint a pointer to byte val=1533 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=128's data block
    # 130   Data Block 10 - Image Data Info
    #       1st uint a pointer to byte val=68 4 uints before end of Jump Field,
    #       right at IMAGE DATA START
    #       ends at end of image data (could be end of file)
    #       Image data pointer
    #       uint[0] = img data start, uint[1] = img data length
    #       this starts after end of field_type=129's data block
    # 132   Data Block 2 Info
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=143's data block
    # 133   Data Block 3 Info
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=132's data block
    # 140   Data Block 5 Info
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=141's data block
    # 141   Data Block 4 Info
    #       1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=133's data block
    # 142   Data Block 0 Info
    #       1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of long zero fill after 160-380 fields
    # 143   Data Block 1 Info
    #       1st uint a pointer to byte val=40 4 uints before end of Jump Field,
    #       ends at another spot 4 uints before end of Jump Field
    #       uint[0] = data block start, uint[1] = data length
    #       this starts after end of field_type=142's data block

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
    # 1022  No data items, only data_id tags?
    #       4 uints in payload, first 3 uints are data_id tags
    #       Every 4 bytes is data item, last 4 bytes are not used (??)
    #       Bytes 0-3 are uint data_id tag

    # 1000  pointed from data in 100 (and other types?)
    #       Sometimes for field_type= 16, sometimes not (??)
    #       Is format fixed based on which data block?

    # Not understood yet:
    # 1007  Not fully understood - Irregular data block
    #       Is format fixed based on which data block?
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
                note_str=note_str,
                file=file
                )
    elif field_type==16:
        return_vals = read_field_type16(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==100:
        return_vals = read_field_type100(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==101:
        return_vals = read_field_type101(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==102:
        return_vals = read_field_type102(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==129:
        return_vals = read_field_type129(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==130:
        return_vals = read_field_type130(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==131:
        return_vals = read_field_type131(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==1000:
        return_vals = read_field_type1000(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==1007:
        return_vals = read_field_type1007(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    elif field_type==1022:
        return_vals = read_field_type1022(
                in_bytes, byte_idx,
                note_str=note_str,
                field_data=field_data,
                file=file
                )
    else:
        return_vals = read_field_generic(
                in_bytes, byte_idx,
                note_str=note_str,
                file=file
                )
    
    return return_vals


def print_field_header(in_bytes, byte_idx, file=sys.stdout):
    print("---------------------------------------------------------------", file=file)
    print("byte_idx = "+repr(byte_idx), file=file)

    # read header
    (header_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", quiet=True)
    (header_uints, _) = debug_uints(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "uints", quiet=True)
    field_type = header_ushorts[0]
    field_len = header_ushorts[1]
    field_id = header_uints[1]

    # field_len of 1 or 2 means field_len=20
    if field_len==1 or field_len==2:
        field_len = 20

    # print header
    print("Field Header:", file=file)
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+4], byte_idx, "type, len", file=file)
    print(file=file)
    #(out_bytes, _) = debug_bytes(
    #        in_bytes[byte_idx+4:byte_idx+8], byte_idx+4, "bytes", file=file)
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx+4:byte_idx+8], byte_idx+4, "ushorts", file=file)
    (out_uints, _) = debug_uints(
            in_bytes[byte_idx+4:byte_idx+8], byte_idx+4, "uints", file=file)
    print(file=file)
    print("field_type= %d"%field_type, file=file)
    print("field_id = 0x{0:08x} ({0:d})".format(field_id), file=file)
    print("field_len = %d"%field_len, file=file)
    print("field_payload_len = %d"%(field_len-8), file=file)
    print(file=file)

    #print("Field Header:", file=file)
    #print("\t[{:6d}, {:6d}, {:10d}]".format(field_type, field_len, data_tag), file=file)
    #print("\t[0x{:04x}, 0x{:04x}, 0x{:08x}]".format(field_type, field_len, data_tag), file=file)

    return (field_type, field_len, header_ushorts, header_uints)

def read_field_generic(in_bytes, byte_idx, note_str="??", file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, byte_idx+8, note_str, multiline=True, file=file)
    (out_bytes, _) = debug_bytes(
            field_payload, byte_idx+8, "bytes", file=file)
    if len(field_payload)%2 == 0:
        (out_ushorts, _) = debug_ushorts(
                field_payload, byte_idx+8, "ushorts", file=file)
    if len(field_payload)%4 == 0:
        (out_uints, _) = debug_uints(
                field_payload, byte_idx+8, "uints", file=file)
        if any([x>0x7FFFFFFF for x in out_uints]):
            # only print signed integers if one is different than uint
            (out_ints, _) = debug_ints(
                    field_payload, byte_idx+8, "ints", file=file)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    return (byte_idx+field_len, field_info)


def read_field_type0(in_bytes, byte_idx, note_str="??", file=sys.stdout):
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
    print("---------------------------------------------------------------", file=file)
    print("byte_idx = "+repr(byte_idx), file=file)

    # read header
    print("Field Header:", file=file)
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", file=file)
    field_type = out_ushorts[0]
    field_len = out_ushorts[1]

    # field_type = 0 has either field_len=0 or field_len=8

    print("field_type= %d"%field_type, file=file)
    print("field_len = %d"%field_len, file=file)
    print("field_payload_len = %d"%(field_len-8), file=file)

    print("\n**** JUMP FIELD ****\n", file=file)
    # experimental jump
    #   used to only do this for field_len==8, but it seems to work for
    #   field_len==0 also!!
    byte_idx = byte_idx + 8
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", file=file)
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
                print("%6d-%6d:"%(test_byte_idx_start,byte_idx-1), file=file)
                print("\tAll zeros %d*(0,)"%(byte_idx-test_byte_idx_start), file=file)
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx, "ushorts", file=file)
        else:
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx, "ushorts", file=file)
        byte_idx = byte_idx + 14
        
    field_info['type'] = field_type
    if field_len==8:
        return (byte_idx, field_info)
    else:
        return (byte_idx+field_len, field_info)


def read_field_type16(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)
    data_tag = header_uints[1]

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, byte_idx+8, "string", file=file)
    print(file=file)
    if not is_valid_string(field_payload):
        # some byte does not resolve to valid utf-8 character
        print("invalid string", file=file)
        (out_bytes, _) = debug_bytes(
                field_payload, byte_idx+8, "bytes", file=file)
    #
    #if field_len !=0:
    #    if data_tag in field_data:
    #        #(out_uints, _) = debug_uints(
    #        #        field_data[data_tag], byte_idx+8, "bytes", quiet=True)
    #        (field_bytes, _) = debug_string(
    #                field_data[data_tag][0], 0, "bytes", multiline=True,
    #                file=file)
    #        (field_ushorts, _) = debug_ushorts(
    #                field_data[data_tag][0], 0, "ushorts",
    #                file=file)
    #        from_field_type = field_data[data_tag][1]
    #        from_field_at = field_data[data_tag][2]
    #        from_field_at2 = field_data[data_tag][3]
    #        print(file=file)
    #        print("from_field=%d @ %d + %d"%(from_field_type,from_field_at,from_field_at2-from_field_at),
    #                file=file)
    #        if from_field_type==100:
    #            # uint0: ??
    #            # uint1: num_words in future data field
    #            # uint2: data_offset in future data field
    #            # uint5: bytes_per_word
    #            data_start = field_ushorts[4]
    #            bytes_per_word = field_ushorts[10]
    #            num_words = field_ushorts[2]
    #            data_end = data_start + num_words*bytes_per_word - 1
    #            print("data_start=%d"%data_start, file=file)
    #            print("bytes_per_word=%d"%bytes_per_word, file=file)
    #            print("num_words=%d"%num_words, file=file)
    #            print("data_end=%d"%data_end, file=file)
    #        if from_field_type==131:
    #            # only unique value is ushort[4]
    #            print("unique ushort=%d"%field_ushorts[4], file=file)
    #    else:
    #        print("DATA NOT FOUND", file=file)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    return (byte_idx+field_len, field_info)


def get_payload_chunks(field_payload, byte_idx, field_type,
        chunk_size, data_id_byte, file=sys.stdout):
    for i in range(len(field_payload)//chunk_size):
        (out_ushorts, _) = debug_ushorts(
                field_payload[i*chunk_size:(i+1)*chunk_size],
                byte_idx + 8 + i*chunk_size,
                "ushorts",
                file=file)
        (out_uints, _) = debug_uints(
                field_payload[i*chunk_size:(i+1)*chunk_size],
                byte_idx + 8 + i*chunk_size,
                "uints",
                file=file,
                quiet=True)
        if any([x>0x7FFFFFFF for x in out_uints]):
            (out_ints, _) = debug_ints(
                    field_payload, byte_idx+8, "ints", file=file)

        # parse out_uints into data dict with keys of data_id
        # every chunk_size bytes, uint[bytes[12:15]] is key
        field_data[out_uints[data_id_byte]] = [
                field_payload[i*chunk_size:(i+1)*chunk_size],
                field_type,
                byte_idx,
                byte_idx + 8 + i*chunk_size
                ]
    return field_data


def read_field_type100(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    #chunk_size = 36
    #data_id_byte = 3
    new_field_data = get_payload_chunks(
            field_payload, byte_idx, 100,
            36, 3,
            file=file
            )
    field_data.update(new_field_data)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type101(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    #chunk_size = 20
    #data_id_byte = 4
    new_field_data = get_payload_chunks(
            field_payload, byte_idx, 101,
            20, 4,
            file=file
            )
    field_data.update(new_field_data)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type102(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    #chunk_size = 16
    #data_id_byte = 3
    new_field_data = get_payload_chunks(
            field_payload, byte_idx, 102,
            16, 3,
            file=file
            )
    field_data.update(new_field_data)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type129(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    """
    field_type==129 contains the pointer to the start of the data block
    before the image data
    """
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints", file=file)
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints", file=file)

    # out_uints[0] = data start
    # out_uints[1] = data length
    # out_uints[2] = ???

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type130(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    """
    field_type==130 contains the pointer to the start of the image data
    """
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints", file=file)
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints", file=file)

    # out_uints[0] = image data start
    # out_uints[1] = image data length
    # out_uints[2] = ???

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type131(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    #chunk_size = 12
    #data_id_byte = 1
    new_field_data = get_payload_chunks(
            field_payload, byte_idx, 131,
            12, 1,
            file=file
            )
    field_data.update(new_field_data)

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1000(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    # TODO: extract data for future field_type=16
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, 0, "string", multiline=True, file=file)
    #(out_string, _) = debug_string(
    #        field_payload, byte_idx+8, "string", multiline=True, file=file)
    (out_ushorts, _) = debug_ushorts(
            field_payload, byte_idx+8, "ushorts", file=file)
    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints", file=file)
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints", file=file)

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1007(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    # TODO: extract data for future field_type=16
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, 0, "string", multiline=True, file=file)
    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints", file=file)
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints", file=file)

    # TODO: what is the format of this??
    #for i in range(len(out_uints)//4):
    #    field_data[out_uints[i*4+3]] = out_uints[i*4:i*4+4]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def read_field_type1022(in_bytes, byte_idx, note_str="??", field_data={},
        file=sys.stdout):
    field_info = {}
    # read header
    (field_type, field_len, header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file)

    # read payload 
    print("Field Payload:", file=file)
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    (out_string, _) = debug_string(
            field_payload, 0, "string", multiline=True, file=file)
    (out_uints, _) = debug_uints(
            field_payload, byte_idx+8, "uints", file=file)
    if any([x>0x7FFFFFFF for x in out_uints]):
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints", file=file)

    # first three uints are data_id tags, no associated data
    field_data[out_uints[0]] = [b'', 1022, byte_idx, byte_idx+8]
    field_data[out_uints[1]] = [b'', 1022, byte_idx, byte_idx+8+4]
    field_data[out_uints[2]] = [b'', 1022, byte_idx, byte_idx+8+8]

    field_info['type'] = field_type
    field_info['payload'] = field_payload
    field_info['data'] = field_data
    return (byte_idx+field_len, field_info)


def jump_idx(jump_from, jump_to, chk_field_start, chk_byte_idx,
        file=sys.stdout):
    if chk_field_start==jump_from and chk_byte_idx==jump_from:
        print("---------------------------------------------------------", file=file)
        print("jump of delta {0:d}=0x{0:x}".format(jump_to-jump_from), file=file)

        # find how many zeros:
        test_byte_stream = in_bytes[jump_from:jump_to].lstrip(b'\x00')
        num_zeros = len(in_bytes[jump_from:jump_to])-len(test_byte_stream)
        if num_zeros > 0:
            print("%6d-%6d"%(jump_from,jump_from+num_zeros-1), end="", file=file)
            print("   All Zeros %d*(0,)"%(num_zeros), file=file)
            jump_from = jump_from+num_zeros

        #(out_bytes, _) = debug_bytes(
        #        in_bytes[jump_from:jump_to], jump_from, "jumped bytes",
        #        file=file)
        (out_shorts, _) = debug_ushorts(
                in_bytes[jump_from:jump_to], jump_from, "jumped shorts",
                file=file)
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
        print("  "*level+"idx=%d: possible field start, back from %d"%(possible_idx,field_start), file=file)
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


def print_datablock(data_start, data_len, block_name, file=sys.stdout):
    print("=====================================================================",
            file=file)
    print("DATA BLOCK %s"%block_name, file=file)
    print("Start: %d"%(data_start), file=file)
    print("End:   %d"%(data_start + data_len), file=file)
    print(file=file)

    byte_idx = data_start
    # read first 4 ushorts
    (out_uints, byte_idx) = debug_ushorts(in_bytes[byte_idx:byte_idx+8],
            byte_idx,
            "Data Block %s Header"%block_name,
            file=file
            )
    print("Length of data block (minus this block header): %d bytes"%out_uints[0],
            file=file
            )
    print("Number of non-type-16 data fields): %d"%out_uints[2],
            file=file
            )

    field_data = {}
    while( byte_idx < data_start + data_len ):
        field_start = byte_idx
        (byte_idx, field_info) = read_field(in_bytes, byte_idx,
                field_data=field_data, file=file)
        if 'data' in field_info:
            field_data = field_info['data']


filename = os.path.realpath(sys.argv[1])

try:
    out_fh = open("dump.txt","w")
except:
    print("Error opening dump.txt")

print(filename, file=out_fh)

with open(filename, 'rb') as in_fh:
    in_bytes = in_fh.read()

byte_idx = 160

#SEARCH DEBUG
#search_backwards(in_bytes, len(in_bytes)-1, min_search_idx=59881)
#exit()

# field_data is data from last field_type=100 field, to be used in
#   following field_type=16 fields
field_data = {}
data_start = {}
data_len = {}

# init img data start at max 32-bit value
data_start[10] = 0xffffffff

while( byte_idx < len(in_bytes) ):
    field_start = byte_idx
    (byte_idx, field_info) = read_field(in_bytes, byte_idx, field_data=field_data,
            file=out_fh)
    if 'data' in field_info:
        field_data = field_info['data']
    block_ptr_types = {
            142: 0,
            143: 1,
            132: 2,
            133: 3,
            141: 4,
            140: 5,
            126: 6,
            127: 7,
            128: 8,
            129: 9,
            130: 10,
            }
    if field_info['type'] in block_ptr_types:
        block_num = block_ptr_types[field_info['type']]

        (data_start[block_num], data_len[block_num]) = parse_datablock(
            field_info['payload'])

        print("Field Type %d - Data Block %02d"%(field_info['type'],block_num),
                file=out_fh)
        print("    data starts at byte %d"%(data_start[block_num]),
                file=out_fh)
        print("    data length is %d bytes"%(data_len[block_num]),
                file=out_fh)

    # break if we still aren't advancing
    if byte_idx==field_start:
        print("ERROR BREAK!!!!", file=out_fh)
        print("--------------------------------------------------------------",
                file=out_fh)
        break

    if byte_idx > data_start[10]:
        print("--------------------------------------------------------------",
                file=out_fh)
        print("We passed the start of img data, so BREAK!!",
                file=out_fh)
        print("--------------------------------------------------------------",
                file=out_fh)
        break

out_fh.close()

# parse data blocks -9

for i in range(0,10):
    # Data Block
    try:
        out_fh = open("data%02d.txt"%i,"w")
    except:
        print("Error opening dump.txt", file=sys.stderr)
    print_datablock(data_start[i], data_len[i], "%d"%i, file=out_fh)
    out_fh.close()

# Data Block 10 - Image Data
try:
    out_fh = open("data10_img.txt","w")
except:
    print("Error opening dump.txt")
print("=====================================================================",
        file=out_fh)
print("IMAGE DATA BLOCK", file=out_fh)
print(file=out_fh)
#print_datablock(data_start[10], data_len[10], "10", file=out_fh)
data_end = data_start[10] + data_len[10]
print("Image Data: (%d-%d)"%(data_start[10],data_end-1), file=out_fh)
#(img_ushorts, _) = debug_ushorts(
#        in_bytes[data_start[10]:data_end],
#        data_start[10], "img_data", file=out_fh)
#for img_ushort in img_ushorts:
#    print(img_ushort, file=out_fh)
print(file=out_fh)
print(file=out_fh)
out_fh.close()

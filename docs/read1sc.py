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
    <4-byte uint field_id>
Payload
    <bytes or ushort or uint until end of field>

--------------------------
102  ->  101 ->  100 ->  16
    \->  16 \->  16

1015 -> 1008 -> 1007 -> 16
    \-> 1024 -> 1022 -> 16
    \-> 2

1000 -> 1020 -> 1011 -> 1010 -> 1040 -> 131  -> 16
    |       |               |       |       \-> 1000 -> ...
    |       |               |       \-> 1000 -> ...
    |       |               \-> 1000 -> ...
    |       \-> 1000 -> ...
    \-> 1030 -> 1040 -> ...
    |       \-> 1000 -> ...
    \-> 1000 -> ...
    \-> 16

--------------------------
0     Jump Field - nop filler data
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      Around data block boundaries
      Contains info about data block, at end and beginning of data block

--------------------------
126   Data Block 6 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=6180 4 uints before end of Jump Field,
      right before field_type=102, data corresponding to text label
      "Audit Trail"
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=140's data block

127   Data Block 7 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=1020 4 uints before end of Jump Field,
      right before field_type=1000 with "Audit Trail" text inside
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=126's data block

128   Data Block 8 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=7293 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=127's data block

129   Data Block 9 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=1533 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=128's data block

130   Data Block 10 - Image Data Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=68 4 uints before end of Jump Field,
      right at IMAGE DATA START
      ends at end of image data (could be end of file)
      Image data pointer
      uint[0] = img data start, uint[1] = img data length
      this starts after end of field_type=129's data block

132   Data Block 2 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=143's data block

133   Data Block 3 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=132's data block

140   Data Block 5 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=141's data block

141   Data Block 4 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=?? 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=133's data block

142   Data Block 0 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=40 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of long zero fill after 160-380 fields

143   Data Block 1 Info
      NO references to other fields
      NOT referenced by other field
      field_id = 0
      field_len = 20 (header_ushorts[1] = 1)
      1st uint a pointer to byte val=40 4 uints before end of Jump Field,
      ends at another spot 4 uints before end of Jump Field
      uint[0] = data block start, uint[1] = data length
      this starts after end of field_type=142's data block

--------------------------
16    String field - text label assigned to previous data through data_id
      NO references to other fields
      YES referenced by: 100, 101, 102, 131, 1000
      field_id: MSShort: one of {0x0085, 0x0086, 0x0087, 0x0088, 0x008a, 0x014a,
        0x014c, 0x014d, 0x0919, 0x091b, 0x1004, 0x1043, 0x1045, 0x107b, 0x107d,
        0x1083, 0x1097, 0x1099, 0x10b9, 0x10d9, 0x11e4, 0x1289, 0x1441}

--------------------------
2     nop field? - payload is all 0's, otherwise normal header
      NO references to other fields
      YES referenced by: 1015
      field_id = one of { 0x1099c4a8, 0x10b9d4a8, 0x10d9e4a8, 0x11e4a4a8,
        0x128944a8, 0x144144a8}
      field_len = 208

100   Data field - contains multiple data assigned to future text labels
      YES references to: 16,
      YES referenced by: 101,
      Last 4 bytes of field headers of field_type=16 is data_id that match
      data_id uints in this field payload
      Every 36 bytes is data item
      Bytes 12-15 are uint data_id tag

101   Data field - contains multiple data assigned to future text labels
      YES references to: 16, 100
      YES referenced by: 102
      Last 4 bytes of field headers of field_type=16 is data_id that match
      data_id uints in this field payload
      Every 20 bytes is data item
      Bytes 16-19 are uint data_id tag

102   Data field - contains multiple data assigned to future text labels
      YES references to: 16, 101
      NOT referenced by other field
      Last 4 bytes of field headers of field_type=16 is data_id that match
      data_id uints in this field payload
      Every 16 bytes is data item
      Bytes 12-15 are uint data_id tag

131   Data field - contains multiple data assigned to future text labels
      YES references to: 16, 1000
      YES referenced by: 1040
      Last 4 bytes of field headers of field_type=16 is data_id that match
      data_id uints in this field payload
      Every 12 bytes is data item
      Bytes 4-7 are uint data_id tag

1000  pointed from data in 100 (and other types?)
      YES references to: 16, 1000, 1020, 1030
      YES referenced by: 131, 1000, 1010, 1020, 1030, 1040,
      Sometimes for field_type= 16, sometimes not (??)
      Is format fixed based on which data block?

1004  nop field? - payload is all 0's, otherwise normal header
      NO references to other fields
      NOT referenced by other field

1007  Not fully understood - Irregular data block
      YES references to: 16
      YES referenced by: 1008
      Is format fixed based on which data block?

1008
      YES references to: 1007
      YES referenced by: 1015

1010
      YES references to: 1000, 1040
      YES referenced by: 1011

1011
      YES references to: 1010
      YES referenced by: 1020

1015
      YES references to: 1008, 1024, 2
      NOT referenced by other field

1020
      YES references to: 1000, 1011
      YES referenced by: 1000

1022  No data items, only data_id tags?
      YES references to: 16
      YES referenced by: 1024
      4 uints in payload, first 3 uints are data_id tags
      Every 4 bytes is data item, last 4 bytes are not used (??)
      Bytes 0-3 are uint data_id tag

1024
      YES references to: 1022
      YES referenced by: 1015

1030
      YES references to: 1000, 1040
      YES referenced by: 1000

1040
      YES references to: 131, 1000
      YES referenced by: 1010, 1030
--------------------------
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
        var_tab=False, file=sys.stdout):
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
                if var_tab is False:
                    print("    %6d: "%(address+i*items*bits/8), end="", file=file)
                else:
                    print("%s%4d: "%(var_tab,address+i*items*bits/8), end="", file=file)
            else:
                if var_tab is False:
                    print("            ", end="", file=file)
                else:
                    print("%s      "%(var_tab), end="", file=file)
            # print decimal words
            for byte in byte_list[byte_group[0]:byte_group[1]]:
                print(pr_str.format(byte), end="", file=file)
            print(file=file)

            # print spacer
            if var_tab is False:
                print("            ", end="", file=file)
            else:
                print("%s      "%(var_tab), end="", file=file)
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
    

def debug_generic(byte_stream, byte_start, note_str, format_str,
        var_tab=False, quiet=False, file=sys.stdout):
    bytes_per = struct.calcsize(format_str)
    num_shorts = len(byte_stream)//(bytes_per)
    out_shorts = struct.unpack("<"+format_str*num_shorts, byte_stream)
    byte_idx = byte_start + len(byte_stream)
    if not quiet:
        if var_tab is not False:
            print("%s%d-%d: %s"%(var_tab, byte_start, byte_idx-1, note_str),
                    file=file)
        else:
            print("%6d-%6d: %s"%(byte_start, byte_idx-1, note_str), file=file)
        print_list(
                out_shorts,
                bits=bytes_per*8,
                address=byte_start,
                var_tab=var_tab,
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


def debug_ushorts(byte_stream, byte_start, note_str, var_tab=False,
        quiet=False, file=sys.stdout):
    (out_shorts, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "H", var_tab=var_tab,
            quiet=quiet, file=file)
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
        print("%6d-%6d: %s"%(byte_start,byte_idx - 1,note_str), file=file)
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


def print_field_header(in_bytes, byte_idx, file=sys.stdout, quiet=False):
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

    # print header (unless quiet)
    if not quiet:
        print("---------------------------------------------------------------",
                file=file)
        print("byte_idx = "+repr(byte_idx), file=file)
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
        print("field_type= %4d"%field_type, file=file)
        print("field_id = 0x{0:08x} ({0:d})".format(field_id), file=file)
        print("field_len = %4d"%field_len, file=file)
        print("field_payload_len = %4d"%(field_len-8), file=file)
        print(file=file)

    return (field_type, field_len, field_id, header_ushorts, header_uints)


def read_field(in_bytes, byte_idx, note_str="??", field_data={}, field_ids={},
        file=sys.stdout, quiet=False):
    field_info = {}
    # read header
    (field_type, field_len, field_id,
            header_ushorts, header_uints) = print_field_header(
            in_bytes, byte_idx, file=file, quiet=quiet)

    # get field_len if jump field
    if field_type==0:
        field_len = process_payload_type0(in_bytes, byte_idx+8, quiet=True)

    # get payload bytes
    field_payload = in_bytes[byte_idx+8:byte_idx+field_len]

    # check for references
    references = []
    if len(field_payload) % 4 == 0:
        (out_uints, _) = debug_uints( field_payload, byte_idx+8, "", quiet=True)
        references = [x for x in out_uints if x in field_ids]
        if references and not quiet:
            print("Links to: ", end="", file=file )
            for ref in references:
                print("%d (type %d),"%(ref,field_ids[ref]['type']),
                        end="", file=file )
            print("\n", file=file)

    # report payload if not quiet
    if not quiet:
        print("Field Payload:", file=file)

        if field_type==0:
            field_len = process_payload_type0(in_bytes, byte_idx+8, file=file)
        elif field_type==16:
            process_payload_type16(field_payload, byte_idx+8, file=file)
        else:
            process_payload_generic(field_payload, byte_idx+8, note_str,
                    file=file)

    field_info['type'] = field_type
    field_info['id'] = field_id
    field_info['payload'] = field_payload
    field_info['references'] = references

    return (byte_idx+field_len, field_info)


def process_payload_generic(field_payload, payload_idx, note_str,
        file=sys.stdout, quiet=False):
    # string also shows bytes in hex
    (out_string, _) = debug_string(
            field_payload, payload_idx, note_str, multiline=True,
            file=file, quiet=quiet)
    if len(field_payload)%2 == 0:
        (out_ushorts, _) = debug_ushorts(
                field_payload, payload_idx, "ushorts",
                file=file, quiet=quiet)
    if len(field_payload)%4 == 0:
        (out_uints, _) = debug_uints(
                field_payload, payload_idx, "uints",
                file=file, quiet=quiet)
        if any([x>0x7FFFFFFF for x in out_uints]):
            # only print signed integers if one is different than uint
            (out_ints, _) = debug_ints(
                    field_payload, payload_idx, "ints",
                    file=file, quiet=quiet)


def process_payload_type0(in_bytes, payload_idx, file=sys.stdout, quiet=False):
    # Finding the end of the jump algorithm
    # READ:
    #   ushort field_type=0
    #   ushort 8
    #   ushort 0
    #   ushort 0
    #   4*ushort
    #   ushort A
    #   if A==0 read 6*ushort, goto prev else exit, return this idx

    if not quiet:
        print("\n**** JUMP FIELD ****\n", file=file)
    # used to only do this for field_len==8, but it seems to work for
    #   field_len==0 also!!
    byte_idx = payload_idx
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", file=file, quiet=quiet)
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
                if not quiet:
                    print("%6d-%6d:"%(test_byte_idx_start,byte_idx-1),
                            file=file)
                    print("\tAll zeros %d*(0,)"%(byte_idx-test_byte_idx_start),
                            file=file)
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx,
                    "ushorts", file=file, quiet=quiet)
        else:
            (out_ushorts, _) = debug_ushorts(
                    in_bytes[byte_idx:byte_idx+14], byte_idx,
                    "ushorts", file=file, quiet=quiet)
        byte_idx = byte_idx + 14

    field_len = byte_idx - (payload_idx - 8)
    return field_len


def process_payload_type16(field_payload, payload_idx, file=sys.stdout):
    (out_string, _) = debug_string(
            field_payload, payload_idx, "string", file=file)
    print(file=file)
    if not is_valid_string(field_payload):
        # some byte does not resolve to valid utf-8 character
        print("invalid string", file=file)
        (out_bytes, _) = debug_bytes(
                field_payload, payload_idx, "bytes", file=file)


#def read_field(in_bytes, byte_idx, note_str="??", field_data={}, field_ids={},
#        file=sys.stdout):
#    (out_ushorts, _) = debug_ushorts(
#            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts", quiet=True)
#    field_type = out_ushorts[0]
#    if field_type==0:
#        return_vals = read_field_type0(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                file=file
#                )
#    elif field_type==16:
#        return_vals = read_field_type16(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==100:
#        return_vals = read_field_type100(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==101:
#        return_vals = read_field_type101(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==102:
#        return_vals = read_field_type102(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==129:
#        return_vals = read_field_type129(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==130:
#        return_vals = read_field_type130(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==131:
#        return_vals = read_field_type131(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==1000:
#        return_vals = read_field_type1000(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==1007:
#        return_vals = read_field_type1007(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    elif field_type==1022:
#        return_vals = read_field_type1022(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                field_data=field_data,
#                file=file
#                )
#    else:
#        return_vals = read_field_generic(
#                in_bytes, byte_idx,
#                note_str=note_str,
#                file=file
#                )
#    
#    return return_vals


def get_payload_chunks(field_payload, byte_idx, field_type,
        chunk_size, data_id_byte, file=sys.stdout):
    field_data = {}
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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
    (field_type, field_len, field_id, header_ushorts, header_uints) = print_field_header(
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


def print_datablock(in_bytes, data_start, data_len, block_name, field_ids={},
        file=sys.stdout):
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
    # TODO: is this correct?
    print("Number of non-type-16 data fields: %d"%out_uints[2],
            file=file
            )

    field_data = {}
    while( byte_idx < data_start + data_len):
        (out_ushorts, _) = debug_ushorts(in_bytes[byte_idx:byte_idx+2],
                byte_idx, "", quiet=True)
        # if we get to the field_type=0 field, we're at end of block
        if out_ushorts[0] == 0:
            break

        (byte_idx, field_info) = read_field(in_bytes, byte_idx,
                field_data=field_data, field_ids=field_ids, file=file)
        if 'data' in field_info:
            field_data = field_info['data']

    print("--------------------------------------------------------------",
            file=file)
    print("Data Block %s Footer"%block_name, file=file)

    (out_ushorts, byte_idx) = debug_ushorts(in_bytes[byte_idx:byte_idx+8],
            byte_idx,
            "",
            file=file
            )
    while (byte_idx < data_start + data_len):
        (out_ushorts, byte_idx) = debug_ushorts(in_bytes[byte_idx:byte_idx+14],
                byte_idx,
                "",
                file=file
                )


def report_whole_file(in_bytes, field_ids, filedir, filename):
    try:
        out_fh = open(os.path.join(filedir,"dump.txt"),"w")
    except:
        print("Error opening dump.txt")

    print(filename, file=out_fh)

    # field_data is data from last field_type=100 field, to be used in
    #   following field_type=16 fields
    byte_idx = 160
    field_data = {}
    data_start = {}
    data_len = {}
    # init img data start at max 32-bit value
    data_start[10] = 0xffffffff

    while byte_idx < len(in_bytes):
        field_start = byte_idx
        (byte_idx, field_info) = read_field(
                in_bytes, byte_idx, field_data=field_data, field_ids=field_ids,
                file=out_fh)

        # record blocks start, end
        block_ptr_types = { 142:0, 143:1, 132:2, 133:3, 141:4,
                140:5, 126:6, 127:7, 128:8, 129:9, 130:10, }
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
            print("-----------------------------------------------------------",
                    file=out_fh)
            break

        if byte_idx > data_start[10]:
            print("-----------------------------------------------------------",
                    file=out_fh)
            print("We passed the start of img data, so BREAK!!",
                    file=out_fh)
            print("-----------------------------------------------------------",
                    file=out_fh)
            break

    out_fh.close()


def report_datablocks(in_bytes, data_start, data_len, field_ids, filedir):
    # parse data blocks 0-9
    for i in range(0,10):
        # Data Block
        try:
            out_fh = open(os.path.join(filedir,"data%02d.txt"%i),"w")
        except:
            print("Error opening data%02d.txt"%i, file=sys.stderr)
            raise
        print_datablock(
                in_bytes,
                data_start[i], data_len[i], "%d"%i,
                field_ids=field_ids, file=out_fh)
        out_fh.close()

    # Data Block 10 - Image Data
    try:
        out_fh = open(os.path.join(filedir,"data10_img.txt"),"w")
    except:
        print("Error opening data10_img.txt")
    print("===================================================================",
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


def indent_str(recurse_level):
    return "    "*recurse_level


def recurse_fields(field_id, field_ids, recurse_level, file=sys.stdout):
    this_field = field_ids[field_id]
    this_payload = this_field['payload']
    ind = indent_str(recurse_level)
    print("%sfield_type=%4d"%(ind, this_field['type']), end="", file=file)
    print("  field_id=0x{0:08x} ({0:d})".format(this_field['id']),
            file=file)
    if this_field.get('references',None):
        if len(this_payload)%4 == 0:
            (out_uints, _) = debug_uints(this_payload, 0, "", quiet=True)

            last_i = 0
            for (i,x) in enumerate(out_uints):
                if x in this_field['references']:
                    if last_i<i*4:
                        debug_ushorts(
                                this_payload[last_i:i*4], last_i, "",
                                var_tab=ind, file=file)
                    ref = x
                    last_i = (i+1)*4
                    print("%s%d-%d:"%(ind, i*4,i*4+3), file=file)
                    recurse_fields(ref, field_ids, recurse_level+1, file=file)
            if last_i<len(this_payload):
                debug_ushorts(this_payload[last_i:], last_i, "", var_tab=ind,
                        file=file)
        else:
            raise(Exception("references, but payload not a multiple of 4!!"))
    else:
        if this_field['type'] == 16:
            print(ind+this_payload[:-1].decode('utf-8','ignore'), file=file)
    print(file=file)


def report_hierarchy(field_ids, is_referenced, filedir, file=sys.stdout):
    try:
        out_fh = open(os.path.join(filedir,"hierarchy.txt"),"w")
    except:
        print("Error opening hierarchy.txt")
        raise

    field_ids_norefs = [x for x in field_ids if not is_referenced.get(x,False)]
    field_ids_norefs = [x for x in field_ids_norefs if field_ids[x]['type'] != 16]
    field_ids_norefs.sort()
    for field_id in field_ids_norefs:
        recurse_fields(field_id, field_ids, 0, file=out_fh)
        print(file=out_fh)

    out_fh.close()


def parse_file(filename):
    print(filename)

    filename = os.path.realpath(filename)
    filedir = os.path.dirname(filename)

    with open(filename, 'rb') as in_fh:
        in_bytes = in_fh.read()

    byte_idx = 160

    #SEARCH DEBUG
    #search_backwards(in_bytes, len(in_bytes)-1, min_search_idx=59881)
    #exit()

    # dict of keys: field_ids, items: field_payloads
    field_ids = {}

    # PASS 1
    #   get all fields, field_ids, field_data

    # reset loop variables
    byte_idx = 160
    data_start = {}
    data_len = {}
    # init img data start at max 32-bit value
    data_start[10] = 0xffffffff

    while byte_idx < len(in_bytes):
        field_start = byte_idx

        (byte_idx, field_info) = read_field(
                in_bytes, byte_idx,
                note_str="",
                quiet=True
                )

        # record data blocks start, end
        block_ptr_types = { 142:0, 143:1, 132:2, 133:3, 141:4,
                140:5, 126:6, 127:7, 128:8, 129:9, 130:10, }
        if field_info['type'] in block_ptr_types:
            block_num = block_ptr_types[field_info['type']]
            (data_start[block_num], data_len[block_num]) = parse_datablock(
                field_info['payload'])

        if field_info['id'] != 0:
            field_ids[field_info['id']] = field_info

        # break if we still aren't advancing
        if byte_idx==field_start:
            break

        if byte_idx > data_start[10]:
            break

    # reset byte_idx
    byte_idx = 160

    # keep track of all fields that were referenced
    is_referenced = {}

    # now that we know all data_ids, find all references
    while byte_idx < len(in_bytes):
        field_start = byte_idx

        (byte_idx, field_info) = read_field(
                in_bytes, byte_idx,
                note_str="",
                quiet=True,
                field_ids=field_ids
                )

        if field_info['id'] != 0:
            # update references field using field_info
            field_ids[field_info['id']] = field_info

            for ref in field_info['references']:
                is_referenced[ref] = True

        # break if we still aren't advancing
        if byte_idx==field_start:
            break

        if byte_idx > data_start[10]:
            break

    # PASS 2
    #   report on whole file to dump.txt
    report_whole_file(in_bytes, field_ids, filedir, filename)

    # PASS 3
    #   report data blocks in separate files
    report_datablocks(in_bytes, data_start, data_len, field_ids, filedir)

    # PASS 4
    #   report on hierarchy
    report_hierarchy(field_ids, is_referenced, filedir)


def main(args):
    for filename in args:
        parse_file(filename)


if __name__ == "__main__":
    main(sys.argv[1:])
    exit(0)

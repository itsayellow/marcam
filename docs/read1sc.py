#!/usr/bin/env python3

# testbed to read *.1sc files

import os
import sys
import os.path
import struct

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


def debug_generic(byte_stream, byte_start, note_str, format_str):
    bytes_per = struct.calcsize(format_str)
    num_shorts = len(byte_stream)//(bytes_per)
    out_shorts = struct.unpack("<"+format_str*num_shorts, byte_stream)
    byte_idx = byte_start + len(byte_stream)
    print("%6d-%6d"%(byte_start,byte_idx-1), end="")
    print("\t"+note_str+":")
    print_list(out_shorts, bits=bytes_per*8)
    print_list(out_shorts, bits=bytes_per*8, dec_not_hex=False)
    return (out_shorts, byte_idx)


def debug_ints(byte_stream, byte_start, note_str):
    (out_ints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "i")
    return (out_ints, byte_idx)


def debug_uints(byte_stream, byte_start, note_str):
    (out_uints, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "I")
    return (out_uints, byte_idx)


def debug_ushorts(byte_stream, byte_start, note_str):
    (out_shorts, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "H")
    return (out_shorts, byte_idx)


def debug_bytes(byte_stream, byte_start, note_str):
    (out_bytes, byte_idx) = debug_generic(
            byte_stream, byte_start, note_str, "B")
    return (out_bytes, byte_idx)


def debug_string(byte_stream, byte_start, note_str):
    out_string = byte_stream.decode("utf-8","ignore")
    byte_idx = byte_start + len(byte_stream)
    print("%6d-%6d"%(byte_start,byte_idx - 1), end="")
    print("\t"+note_str+":")
    print("\t"+out_string)
    return (out_string, byte_idx)


def debug_nullterm_string(in_bytes, byte_start, note_str):
    byte_idx = byte_start
    while in_bytes[byte_idx] != 0:
        byte_idx += 1
    return debug_string(in_bytes[byte_start:byte_idx+1], byte_start, note_str)


def is_valid_string(byte_stream):
    try:
        out_string = byte_stream.decode("utf-8","strict")
    except:
        return False
    return True


def read_field(in_bytes, byte_idx, note_str="??"):
    print("---------------------------------------------------------------")
    print("byte_idx = "+repr(byte_idx))

    # read header
    print("Field Header:")
    #(out_bytes, _) = debug_bytes(
    #        in_bytes[byte_idx:byte_idx+8], byte_idx, "bytes")
    (out_ushorts, _) = debug_ushorts(
            in_bytes[byte_idx:byte_idx+8], byte_idx, "ushorts")
    #(out_uints, _) = debug_uints(
    #        in_bytes[byte_idx:byte_idx+8], byte_idx, "uints")
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
        (out_ints, _) = debug_ints(
                field_payload, byte_idx+8, "ints")

    return (field_type, field_payload, byte_idx+field_len)


def jump_idx(jump_from, jump_to, chk_field_start, chk_byte_idx):
    if chk_field_start==jump_from and chk_byte_idx==jump_from:
        print("jump....jump....jump....jump....jump")
        return jump_to
    else:
        return byte_idx

filename = os.path.realpath(sys.argv[1])

print(filename)

with open(filename, 'rb') as in_fh:
    in_bytes = in_fh.read()

byte_idx = 160
codeFound = False

while( byte_idx < len(in_bytes) ):
    codeFound = False
    field_start = byte_idx
    (field_type, field_payload, byte_idx) = read_field(in_bytes, byte_idx )

    # restart after garbage
    byte_idx = jump_idx(380, 4924, field_start, byte_idx)
    byte_idx = jump_idx(7659, 11013, field_start, byte_idx)
    byte_idx = jump_idx(22710, 23002, field_start, byte_idx)
    byte_idx = jump_idx(23157, 24325, field_start, byte_idx)
    byte_idx = jump_idx(41995, 42771, field_start, byte_idx)
    byte_idx = jump_idx(43570, 44500, field_start, byte_idx)
    byte_idx = jump_idx(49848, 50224, field_start, byte_idx)
    byte_idx = jump_idx(50924, 52908, field_start, byte_idx)
    byte_idx = jump_idx(58329, 59881, field_start, byte_idx)

    # NOTES:
    # image starts somewhere around 59946 in test.1sc
    # I think field_type==100 is data for preceding/following text fields

    # break if we still aren't advancing
    if byte_idx==field_start:
        print("BREAK!!!!")
        print("--------------------------------------------------------------")
        break

    if field_type==0x81:
        print("Code Found")
        (out_uints, _) = debug_uints(
                field_payload, field_start+8, "uints")
        interesting_field_start = field_start
        interesting1 = out_uints[0]
        #break

print("interesting1 = "+repr(interesting1))
print("interesting_field_start = "+repr(interesting_field_start))
print("interesting1 - 8161 = "+repr(interesting1-8161))

if (interesting1 - 8161) > 0:
    byte_idx = interesting1 - 8161
    print("byte_idx = "+repr(byte_idx))

    (field_type, scanner_name_str, byte_idx) = read_field(
            in_bytes, byte_idx, note_str="Scanner Name")

    (field_type, num_pixels_str, byte_idx) = read_field(
            in_bytes, byte_idx, note_str="Number of Pixels")

    (field_type, image_area_str, byte_idx) = read_field(
            in_bytes, byte_idx, note_str="Image Area")

    (field_type, scan_mem_str, byte_idx) = read_field(
            in_bytes, byte_idx, note_str="Scan Memory Size")


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

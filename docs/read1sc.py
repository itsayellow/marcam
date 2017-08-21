#!/usr/bin/env python3

# testbed to read *.1sc files

import os
import sys
import os.path
import struct

def print_list(byte_list, line_len=8, bits=8, dec_not_hex=True):
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


def debug_signed_ints(byte_stream, byte_idx, note_str, num=1):
    out_int = struct.unpack("<"+"i"*num,in_bytes[byte_idx:byte_idx+4*num])
    byte_idx +=4*num
    print("%6d-%6d"%(byte_idx-4,byte_idx-1), end="")
    print("\t"+note_str+":")
    print_list(out_int, bits=32)
    print_list(out_int, bits=32, dec_not_hex=False)
    return (out_int, byte_idx)


def debug_unsigned_ints(byte_stream, byte_idx, note_str, num=1):
    out_int = struct.unpack("<"+"I"*num,in_bytes[byte_idx:byte_idx+4*num])
    byte_idx +=4*num
    print("%6d-%6d"%(byte_idx-4,byte_idx-1), end="")
    print("\t"+note_str+":")
    print_list(out_int, bits=32)
    print_list(out_int, bits=32, dec_not_hex=False)
    return (out_int, byte_idx)


def debug_unsigned_shorts(byte_stream, byte_idx, note_str, num=1):
    out_shorts = struct.unpack("<"+"H"*num,in_bytes[byte_idx:(byte_idx+2*num)])
    byte_idx +=2*num
    print("%6d-%6d"%(byte_idx-2*num,byte_idx-1), end="")
    print("\t"+note_str+":")
    print_list(out_shorts, bits=16)
    print_list(out_shorts, bits=16, dec_not_hex=False)
    return (out_shorts, byte_idx)


def debug_string(byte_stream, byte_idx_start, byte_idx_end, note_str):
    byte_string = byte_stream[byte_idx_start:byte_idx_end+1]
    byte_idx = byte_idx_end + 1
    print("%6d-%6d"%(byte_idx_start,byte_idx_end), end="")
    print("\t"+note_str+":" )
    print("\t"+byte_string.decode("utf-8","ignore"))
    return (byte_string, byte_idx)


def debug_bytes(byte_stream, byte_idx_start, byte_idx_end, note_str):
    byte_string = byte_stream[byte_idx_start:byte_idx_end+1]
    byte_string_nums = [x for x in byte_string]
    byte_idx = byte_idx_end + 1
    print("%6d-%6d"%(byte_idx_start,byte_idx_end), end="")
    print("\t"+note_str+":" )
    print_list(byte_string_nums)
    print_list(byte_string_nums, dec_not_hex=False)
    return (byte_string, byte_idx)


def debug_nullterm_string(byte_stream, byte_idx_start, note_str):
    byte_idx = byte_idx_start
    while byte_stream[byte_idx] != 0:
        byte_idx += 1
    return debug_bytes(byte_stream, byte_idx_start, byte_idx, note_str)


filename = os.path.realpath(sys.argv[1])

print(filename)

with open(filename, 'rb') as in_fh:
    in_bytes = in_fh.read()

byte_idx = 160
codeFound = False

while( True ):
    codeFound = False
    # <2-byte code><2-byte length><2*(length+1)-byte payload>
    print("---------------------------------------------------------")
    (code, byte_idx) = debug_unsigned_shorts(in_bytes, byte_idx, "code")
    code = code[0]
    if code==0x81:
        codeFound = True

    # short length = in.readShort();
    (length, byte_idx) = debug_unsigned_shorts(in_bytes, byte_idx, "length")
    length = length[0]

    # Matt DEBUG: store start of rest of field
    byte_idx_payload_start = byte_idx

    if codeFound:
        print("Code Found")

        # baseFP = in.getFilePointer() + 2;
        baseFP = byte_idx + 2 + 2 + 2*length
        print("baseFP: %d"%baseFP)

        #if (length > 1) {in.seek(in.getFilePointer() - 2);}
        if length > 1:
            print("length > 1 so adjust byte_idx = byte_idx-2")
            byte_idx += -2 +2 + 2*length

        # readInt - Read four input bytes and return an int value.
        # skip = in.readInt() - 32;
        (skip, byte_idx) = debug_signed_ints(in_bytes, byte_idx, "skip")
        skip = skip[0] - 32

    byte_idx = byte_idx_payload_start
    if length==1 or length==2:
        # in.skipBytes(2 + 2 * length);
        byte_idx += 16
    else:
        # in.skipBytes(2 + 2 * length);
        byte_idx += 2 + 2*length

    if byte_idx > len(in_bytes):
        print("EOF reached")
        break

    debug_bytes(in_bytes, byte_idx_payload_start, byte_idx-1, "bytes")
    debug_unsigned_shorts(in_bytes, byte_idx_payload_start, "shorts", num=8)
    debug_unsigned_ints(in_bytes, byte_idx_payload_start, "unsigned ints", num=8)
    debug_signed_ints(in_bytes, byte_idx_payload_start, "ints", num=8)
    debug_string(in_bytes, byte_idx_payload_start, byte_idx-1, "string")

    if codeFound:
        break

# BASE_OFFSET = 352
# diff = BASE_OFFSET - baseFP;
# skip += diff;
diff = 352 - baseFP
skip = skip + diff

print("baseFP + skip = "+repr(baseFP + skip))

if (baseFP + skip - 8187) > 0:
    #in.seek(baseFP + skip - 8187)
    byte_idx = baseFP + skip - 8187
    print("byte_idx = "+repr(byte_idx))

    # HACK: TODO: setting this hard coded right now (???)
    #   TODO: figure out how to get to here later
    # need 50232 for test.1sc
    byte_idx = baseFP + skip - 8473

    # readCString - Read a string of arbitrary length, terminated by a
    #      null char.
    #scannerName = in.readCString()
    (scanner_name, byte_idx) = debug_nullterm_string(
            in_bytes, byte_idx, "Scanner Name"
            )
  
    #in.skipBytes(8)
    byte_idx += 8
  
    # readCString - Read a string of arbitrary length, terminated by a
    #      null char.
    #in.readCString()
    (number_of_pixels, byte_idx) = debug_nullterm_string(
            in_bytes, byte_idx, "Number of Pixels"
            )
  
    #in.skipBytes(8)
    byte_idx += 8
  
    # readCString - Read a string of arbitrary length, terminated by a
    #      null char.
    (image_area, byte_idx) = debug_nullterm_string(
            in_bytes, byte_idx, "Image Area"
            )
  
    #imageArea = imageArea.substring(imageArea.indexOf(':') + 1).trim()
    #int xIndex = imageArea.indexOf('x')
    #if (xIndex > 0) {
    #    int space = imageArea.indexOf(' ')
    #    if (space >= 0) {
    #        String width = imageArea.substring(1, space)
    #        int nextSpace = imageArea.indexOf(" ", xIndex + 2)
    #        if (nextSpace > xIndex) {
    #            String height = imageArea.substring(xIndex + 1, nextSpace)
    #            physicalWidth = Double.parseDouble(width.trim()) * 1000
    #            physicalHeight = Double.parseDouble(height.trim()) * 1000


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

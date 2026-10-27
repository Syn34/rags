import os
# Minimal Rift Apart TOC reader (format per Ripped Apart docs/source).
import struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crc64_table import TABLE

def crc64_path(s):
    crc = 0xc96c5795d7870f42
    for ch in s:
        b = ord('/') if ch == '\\' else ord(ch.lower())
        crc = TABLE[(crc & 0xff) ^ b] ^ (crc >> 8)
    return (crc >> 2) | (1 << 63)

L_ASSET_IDS, L_ASSET_META, L_FILE_META, L_HEADER, L_HDRDATA = 0x506d7b8a, 0x65bcf461, 0x398abff0, 0xede8ada9, 0x654bded9

def parse_toc(data):
    base = 8
    magic, typ, fsize, n, _ = struct.unpack_from('<4sIIHH', data, base)
    assert magic == b'1TAD', magic
    lumps = {}
    for i in range(n):
        c, o, s = struct.unpack_from('<III', data, base + 16 + 12*i)
        lumps[c] = data[base+o: base+o+s]
    ids = struct.unpack('<%dQ' % (len(lumps[L_ASSET_IDS])//8), lumps[L_ASSET_IDS])
    meta = [struct.unpack_from('<IIII', lumps[L_ASSET_META], 16*i) for i in range(len(lumps[L_ASSET_META])//16)]
    arch = [lumps[L_FILE_META][0x42*i:0x42*(i+1)].split(b'\0')[0].decode('latin1') for i in range(len(lumps[L_FILE_META])//0x42)]
    groups = [0]*len(ids)
    hd = lumps[L_HEADER]
    for g in range(len(hd)//8):
        first, cnt = struct.unpack_from('<II', hd, 8*g)
        for j in range(first, first+cnt): groups[j] = g
    return ids, meta, arch, groups, lumps[L_HDRDATA]

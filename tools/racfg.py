# Rift Apart "Config Built File" parser/serializer (reverse engineered).
import struct, zlib
MAGIC = 0x03150044
T_INT, T_STR, T_OBJ, T_BOOL, T_EMPTY = 0x00, 0x0a, 0x0d, 0x0f, 0x13
SIZED = {0x01: 2, 0x02: 4}

def pad4(n): return (n + 3) & ~3

class Node:
    def __init__(self): self.fields = []   # list of [keyhash, type, keyoff, values]

def parse_node(d, p):
    magic, cnt, size = struct.unpack_from('<III', d, p)
    assert magic == MAGIC, hex(p)
    end = p + 12 + size
    hdr = [struct.unpack_from('<II', d, p + 12 + 8*i) for i in range(cnt)]
    offs = struct.unpack_from('<%dI' % cnt, d, p + 12 + 8*cnt)
    q = p + 12 + 12*cnt
    n = Node()
    for (kh, tw), ko in zip(hdr, offs):
        typ, count = tw >> 24, (tw & 0xffffff) >> 4
        assert tw & 0xf == 0, hex(tw)
        vals = []
        if typ == T_OBJ:
            for _ in range(count):
                q = pad4(q)
                z = struct.unpack_from('<I', d, q)[0]; assert z == 0, (hex(q), z)
                child, q = parse_node(d, q + 4)
                vals.append(child)
        elif typ == T_STR:
            for _ in range(count):
                q = pad4(q)
                ln, crc, h = struct.unpack_from('<IIQ', d, q)
                s = d[q+16:q+16+ln]; assert d[q+16+ln] == 0
                vals.append((s, crc, h)); q = pad4(q + 16 + ln + 1)
        elif typ in (T_BOOL, T_INT):
            vals = list(d[q:q+count]); q = q + count
        elif typ in SIZED:
            sz = SIZED[typ]
            while q % sz: q += 1
            vals = [d[q+sz*i:q+sz*(i+1)] for i in range(count)]; q += sz*count
        elif typ == T_EMPTY:
            assert count == 0
            q = pad4(q); vals = [d[q:q+4]]; q += 4
        else:
            raise ValueError('type %x at %x' % (typ, p))
        n.fields.append([kh, tw, ko, vals])
    q = pad4(q)
    assert q == end, (hex(q), hex(end), hex(p))
    return n, end

def ser_node(n, base_len):
    # base_len: absolute offset where this node will be written (for alignment)
    out = bytearray()
    cnt = len(n.fields)
    body = bytearray()
    for kh, tw, ko, vals in n.fields:
        typ = tw >> 24
        if typ != T_EMPTY:
            tw = (typ << 24) | (len(vals) << 4)
        body += struct.pack('<II', kh, tw)
    body += struct.pack('<%dI' % cnt, *[f[2] for f in n.fields])
    def cur(): return base_len + 12 + len(body)
    for kh, tw, ko, vals in n.fields:
        typ = tw >> 24
        if typ == T_OBJ:
            for c in vals:
                while cur() % 4: body += b'\0'
                body += b'\0\0\0\0'
                body += ser_node(c, cur())
        elif typ == T_STR:
            for s, crc, h in vals:
                while cur() % 4: body += b'\0'
                body += struct.pack('<IIQ', len(s), crc, h) + s + b'\0'
                while cur() % 4: body += b'\0'
        elif typ in (T_BOOL, T_INT):
            body += bytes(vals)
        elif typ == T_EMPTY:
            while cur() % 4: body += b'\0'
            body += vals[0]
        elif typ in SIZED:
            while cur() % SIZED[typ]: body += b'\0'
            body += b''.join(vals)
    while cur() % 4: body += b'\0'
    return struct.pack('<III', MAGIC, cnt, len(body)) + body

def parse_file(data):
    """data = full asset incl. 0x24 toc header."""
    H = 0x24
    magic, typ, fsize, nl, ns = struct.unpack_from('<4sIIHH', data, H)
    assert magic == b'1TAD'
    lumps = [list(struct.unpack_from('<III', data, H + 16 + 12*i)) for i in range(nl)]
    first = min(l[1] for l in lumps)
    strtab = data[H + 16 + 12*nl: H + first]
    secs = {}
    for c, o, s in lumps:
        secs[c] = data[H + o: H + o + s]
    return dict(hdr=data[:H], typ=typ, lumps=lumps, strtab=strtab, secs=secs, nl=nl, ns=ns)

def parse_tree(sec):
    z = struct.unpack_from('<I', sec, 0)[0]; assert z == 0
    root, end = parse_node(sec, 4)
    assert end == len(sec), (end, len(sec))
    return root


def ighash(b):
    """Insomniac's CRC32 name hash (used for config keys, node types and pin names)."""
    return (~zlib.crc32(b, (~0xedb88320) & 0xffffffff)) & 0xffffffff

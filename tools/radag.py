import struct, zlib
def parse_dag(data):
    base = 0xc
    magic, typ, fsize, n, _ = struct.unpack_from('<4sIIHH', data, base)
    if magic != b'1TAD':
        raise ValueError(magic)
    L = {}
    for i in range(n):
        c, o, s = struct.unpack_from('<III', data, base + 16 + 12*i)
        L[c] = (base + o, s)
    def lump(c): o, s = L[c]; return data[o:o+s]
    ids = struct.unpack('<%dQ' % (L[0x933c0d32][1]//8), lump(0x933c0d32))
    names = struct.unpack('<%dI' % (L[0xd101a6cc][1]//4), lump(0xd101a6cc))
    heads = struct.unpack('<%di' % (L[0xf958372e][1]//4), lump(0xf958372e))
    links = struct.unpack('<%di' % (L[0xbc91d1cc][1]//4), lump(0xbc91d1cc))
    def name(i):
        a = base + names[i]; e = data.index(b'\0', a); return data[a:e].decode('latin1')
    def deps(i):
        h = heads[i]; out = []
        if h < 0: return out
        while links[h] > -1: out.append(links[h]); h += 1
        return out
    return ids, name, deps

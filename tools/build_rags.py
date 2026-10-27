"""Builds RiftApartGS.rcmod from an installed copy of Ratchet & Clank: Rift Apart (PC).

In New Game+ (Challenge Mode) the Hall of Heroes level script skips its "add Burst Pistol to
inventory" action, because the player already owns the weapon. This edits that script so the
Challenge branch also runs two new AddToInventoryAction nodes: Hoverboots, then the Omniglove
(Phantom Dash), before continuing with the original NG+ sequence.

Usage:
    pip install lz4
    python build_rags.py "C:/Program Files (x86)/Steam/steamapps/common/Ratchet & Clank - Rift Apart" RiftApartGS.rcmod

The game folder must contain an unmodded `toc` (or pass --toc pointing at a clean copy).
"""
import argparse, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz4.block
from ratoc import parse_toc, crc64_path
from racfg import ighash

ZONE_PATH = ('levels/i29/overlay/storymission/mis_intro_parade_hall_of_heroes/'
             'i29_malinon_intro_gp_parade_hall_of_heroes.zone')
LUMP_PINS, LUMP_NODES, LUMP_POOL = 0xbeab52e7, 0x5e54accf, 0x2300d240
ITEM_PISTOL = b'configs/equipment/wpn_burstpistol_item.config'
ITEM_HOVERBOOTS = b'configs/equipment/gdgt_hoverboots_item.config'
ITEM_OMNIGLOVE = b'configs/equipment/gdgt_versaglove_item.config'   # Phantom Dash
NONE = 0xffff
ID1, ID2, A, B, C, D, E, F, TYP, DOFF, DSZ = range(11)   # node record fields

MOD_INFO = ['RiftApartGS', '1.0',
            'In New Game+ (Challenge Mode), picking up the Blast Pistol in the Hall of Heroes '
            'also gives you the Hoverboots and Phantom Dash.',
            'Syn34']


def read_asset(game_dir, toc_path, path):
    """Return (toc_header_bytes, asset_bytes) for an asset, reading only the DSAR blocks it needs."""
    ids, meta, arch, groups, hdrdata = parse_toc(open(toc_path, 'rb').read())
    i = ids.index(crc64_path(path))
    size, ai, off, ho = meta[i]
    hdr = hdrdata[ho:ho + 0x24] if ho != 0xffffffff else b''
    with open(os.path.join(game_dir, arch[ai].replace('\\', os.sep)), 'rb') as f:
        magic, ver, count, _ = struct.unpack('<4sIII', f.read(16)); f.read(16)
        assert magic == b'DSAR'
        table = f.read(32 * count)
        out = bytearray()
        for k in range(count):
            doff, coff, dsz, csz, mode = struct.unpack_from('<QQIIB', table, 32 * k)
            if doff < off + size and doff + dsz > off:
                if mode != 3:
                    raise SystemExit('block %d uses compression mode %d (only LZ4 supported)' % (k, mode))
                f.seek(coff)
                block = lz4.block.decompress(f.read(csz), uncompressed_size=dsz)
                s, e = max(doff, off), min(doff + dsz, off + size)
                out += block[s - doff:e - doff]
    assert len(out) == size
    return bytes(hdr), bytes(out)


def patch_zone(z):
    dat_size = struct.unpack_from('<I', z, 8)[0]
    dat, trailer = bytearray(z[:dat_size]), z[dat_size:]
    magic, typ, fs, nl, ns = struct.unpack_from('<4sIIHH', dat, 0)
    lumps = [list(struct.unpack_from('<III', dat, 16 + 12 * i)) for i in range(nl)]
    L = {c: (o, s) for c, o, s in lumps}
    o, s = L[LUMP_NODES]; nodes = [list(struct.unpack_from('<QQHHHHHHIII', dat, o + 40 * i)) for i in range(s // 40)]
    o, s = L[LUMP_PINS];  pins = [list(struct.unpack_from('<III', dat, o + 12 * i)) for i in range(s // 12)]
    o, s = L[LUMP_POOL];  pool = bytearray(dat[o:o + s])

    T_ADD, T_DIFF = ighash(b'AddToInventoryAction'), ighash(b'GetDifficultyAction')
    H_SUCCESS, H_FULL, H_CHALLENGE = ighash(b'Success'), ighash(b'InventoryFull'), ighash(b'Challenge')
    H_NOTCHALLENGE = ighash(b'NotChallenge')

    def exec_links(i):
        n = nodes[i]
        return range(n[B], n[B] + n[C]) if n[B] != NONE else range(0)

    def data_links(i):
        n = nodes[i]
        return range(n[D], n[D] + n[E]) if n[D] != NONE else range(0)

    # locate: GetDifficulty node, the pistol AddToInventory it triggers on NotChallenge,
    # the node feeding that AddToInventory its Hero actor, and the Challenge-branch target.
    give = next(i for i, n in enumerate(nodes) if n[TYP] == T_ADD and ITEM_PISTOL in pool[n[DOFF]:n[DOFF] + n[DSZ]])
    diff = next(i for i, n in enumerate(nodes) if n[TYP] == T_DIFF and
                any(pins[k][0] == H_NOTCHALLENGE and pins[k][1] == give for k in exec_links(i)))
    hero_src, hero_pin = next((i, k) for i in range(len(nodes)) for k in data_links(i) if pins[k][1] == give)
    ch_pin = next(k for k in exec_links(diff) if pins[k][0] == H_CHALLENGE and nodes[pins[k][1]][TYP] != T_ADD
                  and pins[k][1] != give and ighash(b'GateAction') != nodes[pins[k][1]][TYP])
    relay, h_in, h_actor = pins[ch_pin][1], pins[ch_pin][2], pins[hero_pin][2]
    na, nb = len(nodes), len(nodes) + 1

    # 1) Hero data links for the two new nodes, right after the existing one (keeps pins grouped by owner)
    ins = hero_pin + 1
    pins[ins:ins] = [[pins[hero_pin][0], na, h_actor], [pins[hero_pin][0], nb, h_actor]]
    for n in nodes:
        if n[B] != NONE and n[B] >= ins: n[B] += 2
        if n[D] != NONE and n[D] >= ins: n[D] += 2
    nodes[hero_src][E] += 2
    ch_pin = ch_pin + 2 if ch_pin >= ins else ch_pin

    # 2) Challenge -> new node A (instead of straight to the relay)
    pins[ch_pin][1] = na
    # 3) A -> relay and A -> B, on both Success and InventoryFull
    a_start = len(pins)
    pins += [[H_SUCCESS, relay, h_in], [H_FULL, relay, h_in], [H_SUCCESS, nb, h_in], [H_FULL, nb, h_in]]
    nodes[relay][A] += 1

    # 4) config blobs: copy of the pistol one with a different item path
    blob = bytes(pool[nodes[give][DOFF]:nodes[give][DOFF] + nodes[give][DSZ]])

    def make_blob(path):
        assert len(path) == len(ITEM_PISTOL)
        b = bytearray(blob); i = b.index(ITEM_PISTOL)
        struct.pack_into('<IQ', b, i - 12, ighash(path), crc64_path(path.decode()))
        b[i:i + len(path)] = path
        return bytes(b)

    assert len(pool) % 4 == 0
    doff_a = len(pool); pool += make_blob(ITEM_HOVERBOOTS)
    doff_b = len(pool); pool += make_blob(ITEM_OMNIGLOVE)
    rng = random.Random(0x5EED)
    used = {n[ID1] for n in nodes}

    def new_id():
        while True:
            v = rng.getrandbits(63) | (1 << 63)
            if v not in used: used.add(v); return v

    ia, ib = new_id(), new_id()
    g = nodes[give]
    nodes.append([ia, ia, 1, a_start, 4, NONE, 0, g[F], g[TYP], doff_a, len(blob)])
    nodes.append([ib, ib, 2, NONE, 0, NONE, 0, g[F], g[TYP], doff_b, len(blob)])

    # invariants of the graph format
    bs = [n[B] for n in nodes if n[B] != NONE]; ds = [n[D] for n in nodes if n[D] != NONE]
    assert bs == sorted(bs) and ds == sorted(ds)
    assert sum(n[C] + n[E] for n in nodes) == len(pins)
    inc = [0] * len(nodes)
    for i in range(len(nodes)):
        for k in exec_links(i): inc[pins[k][1]] += 1
    assert all(inc[i] == nodes[i][A] for i in range(len(nodes)))

    # rebuild container (lump data order kept, 16-byte alignment)
    new = {c: dat[o:o + s] for c, o, s in lumps}
    new[LUMP_PINS] = b''.join(struct.pack('<III', *p) for p in pins)
    new[LUMP_NODES] = b''.join(struct.pack('<QQHHHHHHIII', *n) for n in nodes)
    new[LUMP_POOL] = bytes(pool)
    order = sorted(lumps, key=lambda l: l[1])
    out = bytearray(dat[:order[0][1]]); tab = {}
    for c, o, s in order:
        while len(out) % 16: out += b'\0'
        tab[c] = (len(out), len(new[c])); out += new[c]
    struct.pack_into('<4sIIHH', out, 0, magic, typ, len(out), nl, ns)
    for i, (c, o, s) in enumerate(lumps):
        struct.pack_into('<III', out, 16 + 12 * i, c, *tab[c])
    return bytes(out), trailer


def write_rcmod(path, entries):
    """entries: list of (asset_path, toc_header, data). Format read by Ripped Apart's mod manager."""
    head = b''.join(s.encode() + b'\0' for s in MOD_INFO)
    pos = len(head) + 4
    blob, dirents = b'', b''
    for asset_path, hdr, data in entries:
        asset = hdr + data
        dirents += struct.pack('<IIQBB', pos, len(asset), crc64_path(asset_path), 0, 0)
        blob += asset; pos += len(asset)
    with open(path, 'wb') as f:
        f.write(head + struct.pack('<I', pos) + blob + dirents)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('game_dir')
    ap.add_argument('out', nargs='?', default='RiftApartGS.rcmod')
    ap.add_argument('--toc', help='path to an unmodded toc (default: <game_dir>/toc)')
    a = ap.parse_args()
    toc = a.toc or os.path.join(a.game_dir, 'toc')
    hdr, zone = read_asset(a.game_dir, toc, ZONE_PATH)
    dat, trailer = patch_zone(zone)
    hdr = bytearray(hdr)
    struct.pack_into('<I', hdr, 4, len(dat))
    assert struct.unpack_from('<I', hdr, 8)[0] == len(trailer)
    write_rcmod(a.out, [(ZONE_PATH, bytes(hdr), dat + trailer)])
    print('wrote', a.out)


if __name__ == '__main__':
    main()

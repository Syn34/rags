import os
# Reads the script node graph of a Rift Apart .zone level file.
# Usage: python zonegraph.py [--exe RiftApart.exe] level.zone ...
#   --exe resolves node/pin name hashes using the strings in the game executable.
import sys, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from racfg import parse_node, T_OBJ, T_STR
from racfg import ighash
names = {}
def load_names(exe_path):
    exe = open(exe_path, 'rb').read()
    for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{3,80}', exe):
        names[ighash(m.group())] = m.group().decode()
N = lambda h: names.get(h, hex(h))
def load(path):
    z = open(path, 'rb').read()
    fs = struct.unpack_from('<I', z, 8)[0]; nl = struct.unpack_from('<H', z, 12)[0]
    L = {}
    for i in range(nl):
        c, o, s = struct.unpack_from('<III', z, 16 + 12*i); L[c] = (o, s)
    o, s = L[0x5e54accf]; nodes = [struct.unpack_from('<QQHHHHHHIII', z, o + 40*i) for i in range(s // 40)]
    o, s = L[0xbeab52e7]; pins = [struct.unpack_from('<III', z, o + 12*i) for i in range(s // 12)]
    return z, L, nodes, pins
def strings_of(z, L, n):
    if n[10] == 0: return []
    po = L[0x2300d240][0]
    try: nd, _ = parse_node(z, po + n[9] + 4)
    except Exception: return ['?']
    out = []
    def walk(x):
        for kh, tw, ko, vals in x.fields:
            if tw >> 24 == T_OBJ: [walk(c) for c in vals]
            elif tw >> 24 == T_STR: out.extend(v[0].decode('latin1') for v in vals)
    walk(nd); return out
def links(nodes, pins, i):
    n = nodes[i]; r = []
    if n[3] != 0xffff: r += [('exec',) + tuple(pins[k]) for k in range(n[3], n[3] + n[4])]
    if n[5] != 0xffff: r += [('data',) + tuple(pins[k]) for k in range(n[5], n[5] + n[6])]
    return r
if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['--exe']:
        load_names(args[1]); args = args[2:]
    for path in args:
        z, L, nodes, pins = load(path)
        print('#####', path.split('/')[-1], len(nodes), 'nodes')
        for i, n in enumerate(nodes):
            ss = strings_of(z, L, n)
            if any(('hoverboot' in s.lower() or 'versaglove' in s.lower()) for s in ss):
                print(i, N(n[8]), ss)
                for kind, x, y, w in links(nodes, pins, i):
                    print('     ', kind, N(x), '->', y, N(nodes[y][8]) if y < len(nodes) else '(non-node)', N(w))
                inc = [(j, N(nodes[j][8]), N(x)) for j in range(len(nodes)) for kind, x, y, w in links(nodes, pins, j) if y == i and kind == 'exec']
                print('      triggered by:', inc)

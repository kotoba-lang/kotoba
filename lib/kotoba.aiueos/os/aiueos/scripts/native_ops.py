"""Read the Browser surface's draw ops as one glyph per op.

The frame folds two adjacent glyphs of one run into a kind 3 op (a = gi0 + 65536 * gi1, b = gw0 + 256 * gw1; the second glyph
at x + gw0). A gate that looks for a glyph draw op expands the list first, so it sees what the pixels show.
"""

def expand(ops):
    out = []
    for op in ops:
        op = list(op)
        if op[0] == 3:
            _, x, y, a, b, rgb = op
            gw0 = b & 255
            out.append([2, x, y, a & 0xffff, gw0, rgb])
            out.append([2, x + gw0, y, a >> 16, b >> 8, rgb])
        else:
            out.append(op)
    return out

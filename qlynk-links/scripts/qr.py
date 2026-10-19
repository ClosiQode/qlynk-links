"""Minimal QR code encoder (byte mode), standard library only.

Produces SVG and PNG files. Based on the algorithm described in ISO/IEC 18004
(same approach as Project Nayuki's public-domain-style reference implementation).
No network access: the QR code is computed locally.
"""

import struct
import zlib

# Error correction codewords per block, and number of blocks, indexed [level][version]
_ECC_PER_BLOCK = {
    'L': (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    'M': (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    'Q': (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    'H': (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}
_NUM_BLOCKS = {
    'L': (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    'M': (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    'Q': (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    'H': (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}
_FORMAT_BITS = {'L': 1, 'M': 0, 'Q': 3, 'H': 2}

_MASKS = (
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


def _bit(x, i):
    return (x >> i) & 1 != 0


def _gf_mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data, divisor):
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _raw_modules(ver):
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        result -= (25 * n - 10) * n - 55
        if ver >= 7:
            result -= 36
    return result


def _data_codewords(ver, ecl):
    return _raw_modules(ver) // 8 - _ECC_PER_BLOCK[ecl][ver] * _NUM_BLOCKS[ecl][ver]


def _alignment_positions(ver, size):
    if ver == 1:
        return []
    n = ver // 7 + 2
    step = (ver * 8 + n * 3 + 5) // (n * 4 - 4) * 2
    return list(reversed([size - 7 - i * step for i in range(n - 1)] + [6]))


class QrCode:
    def __init__(self, text, ecl='M', mask=None):
        data = text.encode('utf-8')
        for ver in range(1, 41):
            cc_bits = 8 if ver <= 9 else 16
            capacity = _data_codewords(ver, ecl) * 8
            if len(data) < (1 << cc_bits) and 4 + cc_bits + 8 * len(data) <= capacity:
                break
        else:
            raise ValueError('Text too long for a QR code')
        self.version = ver
        self.size = ver * 4 + 17
        self.ecl = ecl

        bits = []

        def put(val, n):
            bits.extend((val >> i) & 1 for i in range(n - 1, -1, -1))

        put(0b0100, 4)
        put(len(data), cc_bits)
        for b in data:
            put(b, 8)
        put(0, min(4, capacity - len(bits)))
        put(0, -len(bits) % 8)
        pad = 0xEC
        while len(bits) < capacity:
            put(pad, 8)
            pad ^= 0xEC ^ 0x11
        codewords = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

        n = self.size
        self.modules = [[False] * n for _ in range(n)]
        self._func = [[False] * n for _ in range(n)]
        self._draw_function_patterns()
        self._draw_codewords(self._add_ecc(codewords))

        if mask is None:
            best = None
            for m in range(8):
                self._apply_mask(m)
                self._draw_format(m)
                score = self._penalty()
                if best is None or score < best[0]:
                    best = (score, m)
                self._apply_mask(m)
            mask = best[1]
        self.mask = mask
        self._apply_mask(mask)
        self._draw_format(mask)

    def _set(self, x, y, dark):
        self.modules[y][x] = dark
        self._func[y][x] = True

    def _draw_function_patterns(self):
        n = self.size
        for i in range(n):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = _alignment_positions(self.version, n)
        last = len(pos) - 1
        for i, ay in enumerate(pos):
            for j, ax in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format(0)
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                bit = _bit(bits, i)
                a, b = n - 11 + i % 3, i // 3
                self._set(a, b, bit)
                self._set(b, a, bit)

    def _draw_format(self, mask):
        data = _FORMAT_BITS[self.ecl] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        n = self.size
        for i in range(6):
            self._set(8, i, _bit(bits, i))
        self._set(8, 7, _bit(bits, 6))
        self._set(8, 8, _bit(bits, 7))
        self._set(7, 8, _bit(bits, 8))
        for i in range(9, 15):
            self._set(14 - i, 8, _bit(bits, i))
        for i in range(8):
            self._set(n - 1 - i, 8, _bit(bits, i))
        for i in range(8, 15):
            self._set(8, n - 15 + i, _bit(bits, i))
        self._set(8, n - 8, True)

    def _add_ecc(self, data):
        ver, ecl = self.version, self.ecl
        num_blocks = _NUM_BLOCKS[ecl][ver]
        ecc_len = _ECC_PER_BLOCK[ecl][ver]
        raw = _raw_modules(ver) // 8
        num_short = num_blocks - raw % num_blocks
        short_len = raw // num_blocks
        divisor = _rs_divisor(ecc_len)
        blocks, k = [], 0
        for i in range(num_blocks):
            dat = data[k:k + short_len - ecc_len + (0 if i < num_short else 1)]
            k += len(dat)
            ecc = _rs_remainder(dat, divisor)
            if i < num_short:
                dat.append(0)
            blocks.append(dat + ecc)
        result = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                if i != short_len - ecc_len or j >= num_short:
                    result.append(blk[i])
        return result

    def _draw_codewords(self, data):
        n, i = self.size, 0
        total = len(data) * 8
        for right in range(n - 1, 0, -2):
            if right <= 6:
                right -= 1
            upward = (right + 1) & 2 == 0
            for vert in range(n):
                y = n - 1 - vert if upward else vert
                for j in range(2):
                    x = right - j
                    if not self._func[y][x] and i < total:
                        self.modules[y][x] = _bit(data[i >> 3], 7 - (i & 7))
                        i += 1

    def _apply_mask(self, mask):
        fn = _MASKS[mask]
        for y in range(self.size):
            row, func = self.modules[y], self._func[y]
            for x in range(self.size):
                if not func[x] and fn(x, y):
                    row[x] = not row[x]

    def _penalty(self):
        n, m, score = self.size, self.modules, 0
        lines = m + [[m[y][x] for y in range(n)] for x in range(n)]
        for line in lines:
            run = 1
            for a, b in zip(line, line[1:]):
                if a == b:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run = 1
            if run >= 5:
                score += run - 2
        for y in range(n - 1):
            for x in range(n - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(sum(row) for row in m)
        total = n * n
        score += ((abs(dark * 20 - total * 10) + total - 1) // total - 1) * 10
        return score

    # Output -----------------------------------------------------------------

    def to_svg(self, border=4, dark='#000000', light='#ffffff'):
        n = self.size + border * 2
        parts = []
        for y in range(self.size):
            for x in range(self.size):
                if self.modules[y][x]:
                    parts.append('M%d,%dh1v1h-1z' % (x + border, y + border))
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 %d %d" '
            'shape-rendering="crispEdges">\n'
            '<rect width="100%%" height="100%%" fill="%s"/>\n'
            '<path d="%s" fill="%s"/>\n</svg>\n' % (n, n, light, ''.join(parts), dark)
        )

    def to_png(self, scale=10, border=4, dark=(0, 0, 0), light=(255, 255, 255)):
        n = (self.size + border * 2) * scale
        rows = []
        for py in range(n):
            y = py // scale - border
            row = bytearray(b'\x00')
            for px in range(n):
                x = px // scale - border
                on = 0 <= x < self.size and 0 <= y < self.size and self.modules[y][x]
                row += bytes(dark if on else light)
            rows.append(bytes(row))

        def chunk(tag, body):
            return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body) & 0xFFFFFFFF)

        return (b'\x89PNG\r\n\x1a\n'
                + chunk(b'IHDR', struct.pack('>IIBBBBB', n, n, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(b''.join(rows), 9))
                + chunk(b'IEND', b''))


def hex_to_rgb(value):
    value = value.lstrip('#')
    if len(value) != 6:
        raise ValueError('Colour must look like #1a2b3c')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

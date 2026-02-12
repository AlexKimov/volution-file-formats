from typing import BinaryIO
import struct

def unswizzle_8bit_palette(palette_bytes: bytes) -> bytes:
    result = bytearray(len(palette_bytes))
    block_size = len(palette_bytes) // 8
    sub_sizes = [block_size - (i * (block_size // 4)) for i in range(4)]

    for block_start in range(0, len(palette_bytes), sub_sizes[0]):
        src_positions = [
            block_start,
            block_start + sub_sizes[2],
            block_start + sub_sizes[3],
            block_start + sub_sizes[1]
        ]
        dest_positions = [
            block_start,
            block_start + sub_sizes[3],
            block_start + sub_sizes[2],
            block_start + sub_sizes[1]
        ]

        for src_pos, dest_pos in zip(src_positions, dest_positions):
            result[dest_pos:dest_pos + sub_sizes[3]] = \
                palette_bytes[src_pos:src_pos + sub_sizes[3]]

    return bytes(result)


def change_pixel_order(data: bytes, depth: int = 32) -> bytes:
    if depth == 32:
        result = bytearray(data)
        for i in range(0, len(data), 4):
            result[i], result[i + 2] = data[i + 2], data[i]
        return bytes(result)

    if depth == 16:
        result = bytearray(len(data))
        for i in range(0, len(data), 2):
            pixel = struct.unpack('<H', data[i:i + 2])[0]
            a = (pixel & 0x8000) >> 15
            r = (pixel & 0x7C00) >> 10
            g = (pixel & 0x03E0) >> 5
            b = pixel & 0x001F
            new_pixel = (a << 15) | (b << 10) | (g << 5) | r
            result[i:i + 2] = struct.pack('<H', new_pixel)
        return bytes(result)

    return data
    
def get_cstring(data):
    name = ""
    null_pos = data.find(b'\x00')
    name = data[:null_pos].decode('ascii', errors='ignore') \
    if null_pos != -1 else data.decode('ascii', errors='ignore')
    
    return name

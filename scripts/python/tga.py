import os
import struct
from typing import Optional, Tuple, BinaryIO


class TGAFile:
    # TGA Header offsets
    ID_LEN = 0
    CMAP_TYPE = 1
    IMG_TYPE = 2
    CMAP_START = 3
    CMAP_LEN = 5
    CMAP_DEPTH = 7
    X_ORIGIN = 8
    Y_ORIGIN = 10
    WIDTH = 12
    HEIGHT = 14
    DEPTH = 16
    DESCRIPTOR = 17

    # Image Types
    TYPE_NONE = 0
    TYPE_PALETTED = 1
    TYPE_TRUECOLOR = 2

    def __init__(
        self, 
        width: int = 0, 
        height: int = 0, 
        depth: int = 32, 
        image_data: bytes = b'', 
        palette: bytes = b'',
        palette_size = 256,        
        palette_depth = 32,        
        origin_bottom_left: bool = True):
        """
        Initialize a TGA object.
        
        Args:
            width: Image width
            height: Image height
            depth: Bits per pixel (8, 16, 24, 32)
            image_data: Raw pixel data
            palette: Raw palette data (for palettized images)
            origin_bottom_left: If True, data is assumed bottom-up (TGA standard). 
                                 If False, data is top-down (common in memory).
        """
        self.width = width
        self.height = height
        self.depth = depth # Bits per pixel
        
        self.image_data = image_data
        self.palette = palette
        if depth == 8 and not self.palette:
            self.image_data = image_data[1024:]
            self.palette = image_data[:1024]
        
        self.palette_size = palette_size        
        self.palette_depth = palette_depth         
        
        self.origin_bottom_left = origin_bottom_left
        
        # Calculated fields
        self.image_type = self._determine_image_type()

    def _determine_image_type(self) -> int:
        types = {
            8: self.TYPE_PALETTED, 
            16: self.TYPE_TRUECOLOR, 
            32: self.TYPE_TRUECOLOR}
        return types[self.depth]
        
    @staticmethod
    def from_bytes(file_bytes: bytes) -> 'TGAFile':
        if len(file_bytes) < 18:
            raise ValueError("File too small to be a TGA")

        tga = TGAFile()
        
        # Read Header
        tga.id_len = file_bytes[0]
        tga.cmap_type = file_bytes[1]
        tga.img_type = file_bytes[2]
        
        # Parse color map
        tga.cmap_start = struct.unpack('<H', file_bytes[3:5])[0]
        tga.cmap_len = struct.unpack('<H', file_bytes[5:7])[0]
        tga.cmap_depth = file_bytes[7]
        
        # Parse image dimensions
        tga.x_origin = struct.unpack('<H', file_bytes[8:10])[0]
        tga.y_origin = struct.unpack('<H', file_bytes[10:12])[0]
        tga.width = struct.unpack('<H', file_bytes[12:14])[0]
        tga.height = struct.unpack('<H', file_bytes[14:16])[0]
        tga.depth = file_bytes[16]
        
        descriptor = file_bytes[17]
        # Bit 5: 0 = top-left, 1 = bottom-left
        tga.origin_bottom_left = (descriptor & 0x20) != 0
        # Bits 0-3: alpha channel bits
        tga.alpha_bits = descriptor & 0x0F

        # Read ID Field
        offset = 18 + tga.id_len
        
        # Read Palette if present
        if tga.cmap_type == 1:
            palette_size = tga.cmap_len * (tga.cmap_depth >> 3)
            tga.palette = file_bytes[offset:offset + palette_size]
            offset += palette_size
        
        # Read Image Data
        img_data_size = tga.width * tga.height * (tga.depth >> 3)
        tga.image_data = file_bytes[offset:offset + img_data_size]
        
        return tga        

    def open(self, file_path: str) -> bool:
        """Save the TGA to a file."""
        try:
            with open(file_path, 'rb') as f:
                self.from_bytes(f.read())
            return True
        except IOError as e:
            print(f"Error opening TGA {file_path}: {e}")
            return False

    def save(self, file_path: str) -> bool:
        try:
            with open(file_path, 'wb') as f:
                self.write_to_stream(f)
            return True
        except IOError as e:
            print(f"Error saving TGA to {file_path}: {e}")
            return False

    def write_to_stream(self, stream: BinaryIO):
        # 1. ID Length (0)
        stream.write(b'\x00')
        
        # 2. Color Map Type (1 if palettized, else 0)
        cmap_type = 1 if self.depth == 8 else 0
        stream.write(struct.pack('B', cmap_type))
        
        # 3. Image Type (2 for TrueColor, 1 for Palettized)
        stream.write(struct.pack('B', self.image_type))
        
        # 4. Color Map Spec (5 bytes)
        if cmap_type == 1:
            stream.write(struct.pack('<H', 0)) # Start index
            stream.write(struct.pack('<H', self.palette_size)) # Length (256 colors)
            stream.write(struct.pack('B', self.palette_depth)) # Depth (32-bit palette entries)
        else:
            stream.write(b'\x00\x00\x00\x00\x00')
            
        # 5. Origin (4 bytes)
        stream.write(struct.pack('<H', 0)) # X
        stream.write(struct.pack('<H', 0)) # Y
        
        # 6. Dimensions (4 bytes)
        stream.write(struct.pack('<H', self.width))
        stream.write(struct.pack('<H', self.height))
        
        # 7. Pixel Depth (1 byte)
        stream.write(struct.pack('B', self.depth))
        
        # 8. Descriptor (1 byte)
        # Bit 5: Origin (1 = Bottom-Left/Right, which is TGA standard)
        # Bits 0-3: Alpha bits
        descriptor = 0x20 if self.origin_bottom_left else 0x00
        if self.depth == 32:
            descriptor |= 0x08 # 8 bits of alpha
        elif self.depth == 16:
            descriptor |= 0x01 # 1 bit of alpha (for R5G5B5A1)
            
        stream.write(struct.pack('B', descriptor))
        
        # Write Palette if needed
        if cmap_type == 1 and self.palette:
            # Ensure palette is 256 * 4 bytes
            padded_palette = self.palette.ljust(256 * 4, b'\x00')
            stream.write(padded_palette[:256 * 4])
            
        # Write Image Data
        # TGA standard is Bottom-Left. If our data is Top-Left, we must flip it.
        data_to_write = self.image_data
        if not self.origin_bottom_left and self.height > 1:
            # Flip rows vertically
            row_size = self.width * (self.depth // 8)
            rows = [data_to_write[i:i+row_size] for i in range(0, len(data_to_write), row_size)]
            rows.reverse()
            data_to_write = b''.join(rows)
            
        stream.write(data_to_write)
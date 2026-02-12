import os
import struct
from typing import Optional, Tuple, BinaryIO
from enum import IntEnum
from dataclasses import dataclass


@dataclass
class TGAHeader:
    id_len: int = 0
    cmap_type: int = 0
    img_type: int = 0
    cmap_start: int = 0
    cmap_len: int = 0
    cmap_depth: int = 0
    x_origin: int = 0
    y_origin: int = 0
    width: int = 0
    height: int = 0
    depth: int = 32
    descriptor: int = 0
    
    
class ImageType(IntEnum):
    NONE = 0
    PALETTED = 1
    TRUECOLOR = 2   
    
    
class TGAFile:
    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        depth: int = 32,
        image_data: bytes = b'',
        palette: bytes = b'',
        palette_size: int = 256,
        palette_depth: int = 32,
        origin_bottom_left: bool = True
    ):
        self.width = width
        self.height = height
        self.depth = depth
        self.image_data = image_data
        self.palette = palette
        self.palette_size = palette_size
        self.palette_depth = palette_depth
        self.origin_bottom_left = origin_bottom_left
        self.image_type = self._determine_image_type()

    @property
    def filesize(self) -> int:
        header_size = 18
        palette_bytes = self.palette_size * (self.palette_depth // 8) if self.depth == 8 else 0
        image_bytes = self.width * self.height * (self.depth // 8)
        return header_size + palette_bytes + image_bytes

    def _determine_image_type(self) -> ImageType:
        if self.depth == 8:
            return ImageType.PALETTED
        return ImageType.TRUECOLOR

    @classmethod
    def from_bytes(cls, data: bytes) -> 'TGAFile':
        if len(data) < 18:
            raise ValueError("File too small to be a valid TGA")

        header = cls._parse_header(data)
        
        offset = 18 + header.id_len
        
        palette = b''
        if header.cmap_type == 1:
            palette_size = header.cmap_len * (header.cmap_depth // 8)
            palette = data[offset:offset + palette_size]
            offset += palette_size

        image_size = header.width * header.height * (header.depth // 8)
        image_data = data[offset:offset + image_size]

        return cls(
            width = header.width,
            height = header.height,
            depth = header.depth,
            image_data = image_data,
            palette = palette,
            palette_size = header.cmap_len,
            palette_depth = header.cmap_depth,
            origin_bottom_left = bool(header.descriptor & 0x20)
        )

    @staticmethod
    def _parse_header(data: bytes) -> TGAHeader:
        return TGAHeader(
            id_len = data[0],
            cmap_type = data[1],
            img_type = data[2],
            cmap_start = struct.unpack('<H', data[3:5])[0],
            cmap_len = struct.unpack('<H', data[5:7])[0],
            cmap_depth = data[7],
            x_origin = struct.unpack('<H', data[8:10])[0],
            y_origin = struct.unpack('<H', data[10:12])[0],
            width = struct.unpack('<H', data[12:14])[0],
            height = struct.unpack('<H', data[14:16])[0],
            depth = data[16],
            descriptor=data[17]
        )

    def load(self, file_path: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                tga = self.from_bytes(f.read())
                self.__dict__.update(tga.__dict__)
            return True
        except (IOError, ValueError) as e:
            print(f"Error loading TGA {file_path}: {e}")
            return False

    def save(self, file_path: str) -> bool:
        try:
            with open(file_path, 'wb') as f:
                self._write(f)
            return True
        except IOError as e:
            print(f"Error saving TGA to {file_path}: {e}")
            return False

    def _write(self, stream: BinaryIO) -> None:
        stream.write(self._build_header())
        
        if self.depth == 8 and self.palette:
            padded_palette = self.palette.ljust(self.palette_size * 4, b'\x00')
            stream.write(padded_palette[:self.palette_size * 4])

        data = self._prepare_image_data()
        stream.write(data)

    def _build_header(self) -> bytes:
        cmap_type = 1 if self.depth == 8 else 0
        descriptor = 0x20 if self.origin_bottom_left else 0x00
        
        if self.depth == 32:
            descriptor |= 0x08
        elif self.depth == 16:
            descriptor |= 0x01

        header_bytes = b'\x00'
        header_bytes += struct.pack('B', cmap_type)
        header_bytes += struct.pack('B', self.image_type)
        
        if cmap_type == 1:
            header_bytes += struct.pack('<HHB', 0, self.palette_size, self.palette_depth)
        else:
            header_bytes += b'\x00' * 5
            
        header_bytes += struct.pack('<HHHH', 0, 0, self.width, self.height)
        header_bytes += struct.pack('BB', self.depth, descriptor)
        
        return header_bytes

    def _prepare_image_data(self) -> bytes:
        if self.origin_bottom_left or self.height <= 1:
            return self.image_data

        row_size = self.width * (self.depth // 8)
        rows = [self.image_data[i:i + row_size] 
                for i in range(0, len(self.image_data), row_size)]
        return b''.join(reversed(rows))


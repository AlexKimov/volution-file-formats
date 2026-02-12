import os
import sys
import struct
import struct
import argparse
from typing import Optional, Tuple, BinaryIO, Iterator, List
from dataclasses import dataclass, field
from tga import TGAFile
import utils


@dataclass
class PEGFileEntry:
    width: int = 0
    height: int = 0
    type: int = 0
    subtype: int = 0
    frame_num: int = 0 # 0, 1
    u1: int = 1 # 1
    anim_delay: int = 0 # 0
    mipmaps: int = 1   
    u2: int = 0
    name: str = ""
    offset: int = 0

    @classmethod
    def from_file(cls, reader: BinaryIO) -> 'PEGFileEntry':
        width, height, img_type, subtype, u1, frame_num, anim_delay, mipmaps, u2 = \
            struct.unpack('<HHBBBBBBH', reader.read(12))
        
        name = utils.get_cstring(reader.read(48))       
        offset = struct.unpack('<I', reader.read(4))[0]
        
        return cls(
            width = width, 
            height = height, 
            type = img_type, 
            subtype = subtype,
            frame_num = frame_num, 
            u1 = u1,
            anim_delay = anim_delay,           
            mipmaps = mipmaps, 
            u2 = u2, 
            name = name, 
            offset = offset
        )


@dataclass        
class RF2ImageFileFrame:
    data: bytes
    palette: bytes
    

@dataclass        
class RF2ImageFile:
    name: str = ""
    width: int = 0
    height: int = 0
    depth: int = 0
    palette_depth: int = 0
    frames: List[RF2ImageFileFrame] = field(default_factory=list)
     

class PEGImageArchive:
    MAGIC = b'GEKV'
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.entries: List[PEGFileEntry] = []
        self.image_data: List[bytes] = []
        
        self.version = 6
        self.entries_data_size = 0
        self.files_data_size = 0
        self.num_images = 0
        self.dummy = 0
        self.frame_num = 0
        self.unk = 16
    
    def read(self) -> None:
        with open(self.file_path, 'rb') as f:
            self._parse_header(f)
            self._read_entries(f)

    def _parse_header(self, f: BinaryIO) -> None:
        magic = f.read(4)
        if magic != self.MAGIC:
            raise ValueError(f"Invalid PEG file (magic: {magic})")
        
        (self.version, self.entries_data_size, self.files_data_size,
         self.num_images, self.dummy, self.frame_num, self.unk) = \
            struct.unpack('<IIIIIII', f.read(28))

    def _read_entries(self, f: BinaryIO) -> None:
        for _ in range(self.num_images):
            self.entries.append(PEGFileEntry.from_file(f))

    def extract_images(self) -> Iterator[RF2ImageFile]:
        with open(self.file_path, 'rb') as f:
            for entry in self.entries:
                yield self._read_image_data(f, entry)

    def _read_image_data(self, f: BinaryIO, entry: PEGFileEntry) -> Tuple[str, int, int, int, int, bytes]:
        f.seek(entry.offset)
        depth = 0
        palette_depth = 32
        image_data = None

        depth = 32        
        palette_data = None        
        try:
            if entry.type == 7:  # RGBA32
                depth = 32
                
            elif entry.type == 4:  # Palettized 8-bit               
                if entry.subtype == 1:  # 16-bit palette
                    palette_depth = 16
                depth = 8               
            elif entry.type == 3:  # RGBA5551
                depth = 16
                               
            else:
                raise ValueError(f"Unsupported texture type: {entry.type}")

            image = RF2ImageFile(name = entry.name, width = entry.width, \
                height = entry.height, depth = depth, palette_depth = palette_depth)
            for _ in range(entry.frame_num):
                if depth == 8:
                    palette_bytes = utils.change_pixel_order(f.read(256 * palette_depth // 8), palette_depth)
                    palette_data = utils.unswizzle_8bit_palette(palette_bytes)                    
                    image_data = f.read(entry.width * entry.height)
                else:
                    image_data = utils.change_pixel_order(f.read(entry.width * entry.height * (depth // 8)), depth)
                
                image.frames.append(RF2ImageFileFrame(image_data, palette_data))
                
            return image

        except Exception as e:
            raise ValueError(f"Failed to decode image '{entry.name}': {e}")

    def write(self) -> None:
        with open(self.file_path, 'wb') as f:
            self._write_header(f)
            self._write_entries(f)
            self._write_image_data(f)

    def _write_header(self, f: BinaryIO) -> None:
        f.write(self.MAGIC)
        f.write(struct.pack('<III', 
            self.version, 
            len(self.entries) * 64, 
            sum(len(data) for data in self.image_data)))
        f.write(struct.pack('<I', len(self.entries)))
        f.write(struct.pack('<III', 0, 0, 0))

    def _write_entries(self, f: BinaryIO) -> None:
        current_offset = 28 + len(self.entries) * 64
        
        for i, entry in enumerate(self.entries):
            entry.offset = current_offset
            size = len(self.image_data[i])
            
            f.seek(28 + i * 64)
            f.write(struct.pack('<HHBBBBBBH', 
                entry.width, entry.height, entry.type, entry.subtype,
                entry.u1, entry.frame_num, entry.anim_delay, entry.mipmaps, entry.u2))
            
            name_bytes = entry.name.encode('ascii', errors='ignore')[:47]
            f.write(name_bytes.ljust(48, b'\x00'))
            f.write(struct.pack('<I', entry.offset))
            
            current_offset += size

    def _write_image_data(self, f: BinaryIO) -> None:
        f.seek(self.entries[-1].offset if self.entries else 28)
        for data in self.image_data:
            f.write(data)


class PEGProcessor:
    @staticmethod
    def get_peg_meta(peg_folder: str) -> None:
        if not os.path.isdir(peg_folder):
            raise FileNotFoundError(f"PEG folder not found: {peg_folder}") 
        
        peg_files = [f for f in os.listdir(peg_folder) if f.lower().endswith('.peg')]
        
        filename = 'meta.txt'
        with open(filename, 'w') as meta_file:
            for peg_file in peg_files:
                peg_path = os.path.join(peg_folder, peg_file)
                print(f"Processing: {peg_path}")            
                try:                 
                    archive = PEGImageArchive(peg_path)
                    archive.read()
                    meta_file.write(f"{peg_file} {archive.num_images} {archive.frame_num}\n")                                            
                       
                except Exception as e:
                    print(f"  [ERROR] Failed to process {peg_file}: {e}") 
                
    @staticmethod
    def unpack(peg_folder: str, output_folder: str) -> None:
        if not os.path.isdir(peg_folder):
            raise FileNotFoundError(f"PEG folder not found: {peg_folder}")

        os.makedirs(output_folder, exist_ok=True)
        peg_files = [f for f in os.listdir(peg_folder) if f.lower().endswith('.peg')]
        
        if not peg_files:
            print(f"No .peg files found in '{peg_folder}'")
            return

        total_failed = 0
        
        for peg_file in peg_files:
            peg_path = os.path.join(peg_folder, peg_file)
            print(f"\nProcessing: {peg_file}")
            
            try:
                archive = PEGImageArchive(peg_path)
                archive.read()
                
                archive_name = os.path.splitext(peg_file)[0]
                archive_output_dir = os.path.join(output_folder, archive_name)
                os.makedirs(archive_output_dir, exist_ok = True)
                
                failed = PEGProcessor._extract_archive(archive, archive_output_dir)
                total_failed += failed
                
            except Exception as e:
                print(f"  [ERROR] Failed to process {peg_file}: {e}")
                total_failed += 1

        print(f"\nCompleted with {total_failed} failures.")

    @staticmethod
    def _extract_archive(archive: PEGImageArchive, output_dir: str) -> int:
        failed = 0
        
        with open(os.path.join(output_dir, 'meta.txt'), 'w') as meta_file:
            for i, entry in enumerate(archive.entries):
                meta_file.write(f"{i:<5} {entry.name:<30} {entry.width:<6} "
                               f"{entry.height:<6} {entry.type:<4} "
                               f"{entry.subtype:<4} {entry.u1:<4} "
                               f"{entry.frame_num:<4} {entry.anim_delay:<4} {entry.mipmaps:<4} {entry.u2:<4}\n")

        for image in archive.extract_images():
            try:
                name = image.name
                if not image.name.lower().endswith('.tga'):
                    name = f"{image.name}.tga"
             
                tga = TGAFile(
                    width = image.width,
                    height = image.height,
                    depth = image.depth,
                    palette = image.frames[0].palette,
                    origin_bottom_left = False,
                    image_data = image.frames[0].data,
                    palette_depth = image.palette_depth
                )
                
                if len(image.frames) == 1:
                    output_path = os.path.join(output_dir, name)                  
                    failed += 1 - tga.save(output_path)
                    print(f"  Extracted: {name}")
                else:
                    filepath_without_ext = os.path.splitext(name)[0]
                    for i, frame in enumerate(image.frames):                       
                        name = f"{filepath_without_ext}___frame_{i + 1}.tga"
                        output_path = os.path.join(output_dir, name)
                        tga.image_data = frame.data
                        tga.pallete = frame.palette
                        failed += 1 - tga.save(output_path)
                        
                    print(f"  Extracted: {name}")
                
            except Exception as e:
                print(f"  [ERROR] Failed to extract {name}: {e}")
                failed += 1
                
        return failed
         

    @staticmethod
    def pack(input_dir: str) -> None:
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        folders = [f for f in os.listdir(input_dir) 
                  if os.path.isdir(os.path.join(input_dir, f))]
        
        if not folders:
            raise ValueError(f"No directories found in: {input_dir}")

        for dir_name in folders:
            peg_dir = os.path.join(input_dir, dir_name)
            archive = PEGImageArchive(f"{peg_dir}.peg")
            
            try:
                PEGProcessor._pack_directory(peg_dir, archive)
                archive.write()
                print(f"Created: {archive.file_path} Files: {num_images}")
                
            except Exception as e:
                print(f"[ERROR] Failed to create {archive.file_path}: {e}")

    @staticmethod
    def _pack_directory(directory: str, archive: PEGImageArchive) -> None:
        failed = 0
        
        files = []
        vbm_list = {}
        for filename in os.listdir(directory):
            if not filename.lower().endswith('.tga'):
                continue
                
            if "___frame_" in filename:
                name = filename.split("___frame")[0]
                if name in vtb_list:
                    vbm_list[name] += 1            
                if not name in files:               
                    image = RF2ImageFile()
                    name
                    width
                    height
                    depth
                    palette_depth
                    vbm_list[name] = 1
                    
                    files.append(name)                
            else:        
                files.append(filename)
            
            for filename in files:
                if filename.lower().endswith('.vbm'):
                    name = f"{filename}___frame_"
                    
                    for i in range(len(vbm_list[filename].frames)):
                        filepath = f"{name}{i}.tga"
                        if not tga.load(filepath):
                            print(f"Can't load: {filepath}.")
                            failed += 1
                            continue 
                        
                        vbm_list[filename].frames[i] = tga.data, tga.palette))
                        vbm_list[filename].frames[i] = tga.palette))
                        
                      
                                                
                    
                filepath = os.path.join(directory, filename)
                tga = TGAFile()
            
                if not tga.load(filepath):
                    print(f"Can't load: {filepath}.")
                    failed += 1
                    continue
            
                subtype = 0
                if tga.depth == 8:
                    subtype = 2 if tga.palette_depth == 32 else 1
            
                entry = PEGFileEntry(
                    width = tga.width,
                    height = tga.height,
                    type = PEGProcessor._get_image_type(tga.depth),
                    subtype = subtype,
                    u1 = 1,
                    frame_num = 0,                
                    anim_delay = 0,
                    mipmaps = 1,    
                    u2 = 0,
                    name = os.path.basename(filename)
                )
            
                archive.entries.append(entry)
                archive.image_data.append(tga.image_data) 

        print(f"\nCompleted with {failed} failures.")            
    @staticmethod
    def _get_image_type(depth: int) -> int:
        return {32: 7, 16: 3, 8: 4}.get(depth, 0)


def main():
    parser = argparse.ArgumentParser(
        description="Unpack and pack .peg files from Red Faction 2."
    )
    
    subparsers = parser.add_subparsers(dest = 'command', required = True)
    
    unpack_parser = subparsers.add_parser('unpack', help = 'Unpack .peg archives')
    unpack_parser.add_argument('peg_folder', help = 'Folder containing .peg files')
    unpack_parser.add_argument('output_folder', help = 'Output folder for extracted files')
    
    pack_parser = subparsers.add_parser('pack', help = 'Pack TGA files into .peg archives')
    pack_parser.add_argument('input_folder', help = 'Folder containing TGA files organized by archive')
 
    meta_parser = subparsers.add_parser('meta', help = 'Grab header data from peg files.')
    meta_parser.add_argument('peg_folder', help = 'Folder containing .peg files')
    
    args = parser.parse_args()
    
    try:
        if args.command == 'unpack':
            PEGProcessor.unpack(args.peg_folder, args.output_folder)
        elif args.command == 'pack':
            PEGProcessor.pack(args.input_folder)
        elif args.command == 'meta':
            PEGProcessor.get_peg_meta(args.peg_folder)            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

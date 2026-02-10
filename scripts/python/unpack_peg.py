import os
import sys
import struct
import argparse
from tga import *

def unswizzle_8bit_palette(palette_bytes: bytes) -> bytes:
    result = bytearray(len(palette_bytes))
    
    bk_size = len(palette_bytes) >> 3    
    bs = [bk_size - (i * (bk_size >> 2)) for i in range(4)] # 128, 96, 64, 32 or 64, 48, 32, 16
    
    for block_start in range(0, len(palette_bytes), bs[0]):
        src_positions = [block_start, block_start + bs[2], block_start + bs[3], block_start + bs[1]]
        dest_positions = [block_start, block_start + bs[3], block_start + bs[2], block_start + bs[1]]
        
        for src_pos, dest_pos in zip(src_positions, dest_positions):
            result[dest_pos:dest_pos + bs[3]] = palette_bytes[src_pos:src_pos + bs[3]]    
    
    return bytes(result)

def change_pixel_order(data, depth = 32):
    out = bytearray(data)
   
    if depth == 32: 
        for i in range(0, len(data), 4):
            out[i]   = data[i + 2] # B -> R
            out[i + 2] = data[i]   # R -> B
    
    elif depth == 16:         
        for i in range(0, len(data), 2):
            pixel = struct.unpack('<H', data[i:i+2])[0]
        
            a = (pixel & 0x8000) >> 15
            r = (pixel & 0x7C00) >> 10
            g = (pixel & 0x03E0) >> 5
            b = (pixel & 0x001F)
        
            pix = (a << 15) | (b << 10) | (g << 5) | r
            out[i: i + 2] = struct.pack('<H', pix)
                  
    return out
    

class PEGFileEntry:
    def __init__(self, reader):
        self.file_handle = reader
        self.offset = 0
        self.width = 0
        self.height = 0
        self.type = 0
        self.subtype = 0
        self.u1 = 0
        self.u2 = 0
        self.flags = 0
        self.name = ""

    def read(self):   
        self.width, self.height, self.type, self.subtype,  self.u1,  self.u2, self.flags = \
            struct.unpack('<HHBBBBI', self.file_handle.read(12))
        
        name_bytes = self.file_handle.read(48)
        null_pos = name_bytes.find(b'\x00')
        self.name = name_bytes[:null_pos].decode('ascii', errors='ignore') \
            if null_pos != -1 else name_bytes.decode('ascii', errors='ignore')

        self.offset = struct.unpack('<I', self.file_handle.read(4))[0]

class PEGImageArchive:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file_handle = open(file_path, 'rb')
        self.entries = []
        self.num_images = 0
        
    def parse_header(self):
        self.file_handle.seek(0)
        magic = self.file_handle.read(4)
        if magic != b'GEKV': # 0x564B4347
            self.file_handle.close()
            raise ValueError(f"Not a valid PEG file (incorrect magic number): {magic}")
        
        self.file_handle.seek(12, 1)
        self.num_images = struct.unpack('<I', self.file_handle.read(4))[0]
        self.file_handle.seek(32, 0)
        
    def read_entries(self):
        for _ in range(self.num_images):
            entry = PEGFileEntry(self.file_handle)
            entry.read()
            self.entries.append(entry)

    def get_images(self):
        for entry in self.entries:
            self.file_handle.seek(entry.offset, 0)
            image_data = None
            depth = 0
            palette_depth = 32
            
            try:
                if entry.type == 7: # Uncompressed RGBA 32-bit
                    data_size = entry.width * entry.height * 4
                    image_data = change_pixel_order(self.file_handle.read(data_size))
                    
                    depth = 32
                elif entry.type == 4: # Palettized 8-bit
                    palette_data = None
                    
                    if entry.subtype == 2: # 1024-byte palette
                        palette_bytes = self.file_handle.read(1024)
                        palette_bytes = change_pixel_order(palette_bytes)
                        palette_data = unswizzle_8bit_palette(palette_bytes)                       
                    elif entry.subtype == 1: # 512-byte palette 
                        palette_bytes = self.file_handle.read(512)
                        palette_bytes = change_pixel_order(palette_bytes, 16)
                        palette_data = unswizzle_8bit_palette(palette_bytes)
                        palette_depth = 16 
                          
                    pixel_data_size = entry.width * entry.height                   
                    image_data = palette_data + self.file_handle.read(pixel_data_size)
                    
                    depth = 8
                elif entry.type == 3: # RGBA 5551 16-bit
                    data_size = entry.width * entry.height * 2
                    depth = 16                    
                    image_data = change_pixel_order(self.file_handle.read(data_size), 16)
                else:
                    print(f"  [ERROR] Unsupported texture type {flags_type} for '{entry.name}'")
                    continue
              
                yield entry.name, entry.width, entry.height, depth, palette_depth, image_data

            except Exception as e:
                print(f"  [ERROR] Failed to decode image '{entry.name}': {e}")
                continue

    def close(self):
        self.file_handle.close()
        
    def read(self):       
        self.parse_header()
        self.read_entries()
            
            
# --- Main Script Logic ---

def main():
    parser = argparse.ArgumentParser(
        description="Unpack .peg files from Red Faction 2.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("peg_folder", 
        help = "The folder containing the .peg files to process.")
    parser.add_argument("output_folder", 
        help = "The main folder where all unpacked archives will be saved.")
    
    args = parser.parse_args()

    output_folder = args.output_folder
    peg_folder = args.peg_folder
     
    if not os.path.isdir(peg_folder):
        print(f"Error: PEG folder not found at '{peg_folder}'")
        sys.exit(1)

    os.makedirs(output_folder, exist_ok=True)
    print(f"Output will be saved to: {os.path.abspath(output_folder)}")

    peg_files = [f for f in os.listdir(peg_folder) if f.lower().endswith('.peg')]
    if not peg_files:
        print(f"No .peg files found in '{peg_folder}'")
        return

    print(f"Found {len(peg_files)} PEG file(s) to process.")

    for peg_file in peg_files:
        peg_path = os.path.join(peg_folder, peg_file)
        print(f"\n--- Processing: {peg_file} ---")
        
        failed_to_export = 0
        try:
            peg_archive = PEGImageArchive(peg_path)
            peg_archive.read()
            
            print(f"Found {peg_archive.num_images} embedded images.")
            
            archive_name = os.path.splitext(peg_file)[0]
            archive_output_dir = os.path.join(output_folder, archive_name)
            os.makedirs(archive_output_dir, exist_ok = True)
            print(f"Created output directory: {archive_output_dir}")

            metadata_path = os.path.join(archive_output_dir, 'metadata.txt')
            with open(metadata_path, 'w', encoding='utf-8') as meta_file:
                for i, entry in enumerate(peg_archive.entries):
                    meta_file.write(f"{i:<5} {entry.name:<30} {entry.width:<6} {entry.height:<6} {entry.type:<4} {entry.subtype:<0}\n")
            
            print(f"Saved metadata to: {metadata_path}")

            for name, width, height, depth, palette_depth, image_data in peg_archive.get_images():
                print(f"  -> Extracting '{name}")
                
                if image_data:
                    clean_name = os.path.splitext(name)[0]
                    output_filename = f"{clean_name}.tga"
                    output_path = os.path.join(archive_output_dir, output_filename)
                    
                    tga = TGAFile(
                        width = width, 
                        height = height, 
                        depth = depth, 
                        image_data = image_data, 
                        origin_bottom_left = False,  # We are providing Top-Left data
                        palette_depth = palette_depth 
                    )
                                     
                    if tga.save(output_path):
                        print(f"     Saved to: {output_path}")
                    else:
                        print(f"     [SKIPPED] Failed to save TGA file.")
                        failed_to_export += 1
                else:
                    print(f"     [SKIPPED] Failed to decode image data.")
                    failed_to_export += 1

            peg_archive.close()

        except Exception as e:
            print(f"\n[FATAL ERROR] Failed to process {peg_file}: {e}")
            import traceback
            traceback.print_exc()

    print("\n--- All files processed. ---")
    print(f"\n Problems: {failed_to_export} files.")

if __name__ == "__main__":
    main()

"""
Read Faction 2 All_Levels.packfile Packer/Unpacker

Usage:
    process_packfile.py unpack <toc_group_file> [output_dir]
    process_packfile.py pack <input_dir> [output_toc] [output_packfile]

Examples:
    process_packfile.py unpack All_Levels.toc_group extracted/
    process_packfile.py pack extracted/ All_Levels.toc_group All_Levels.packfile
"""

import os
import struct
import sys
import argparse
import json
from pathlib import Path


PACKFILE_NAME = "All_Levels.packfile"
TOC_FILENAME = "All_Levels.toc_group"
TOC_DIR = "pc_media\\All_Levels\\"
TOC_NAME = "All_Levels"
TOC_REL_PATH = "pc_media\\All_Levels\\All_Levels.packfile"
OUT_DIR = "extracted/"


class Entry:
    def __init__(self, filename, length, offset):
        self.filename = filename
        self.length = length  
        self.offset = offset
        

def read_null_terminated_string(file_obj):
    chars = []
    while True:
        char = file_obj.read(1)
        if not char or char == b'\x00':
            break
        chars.append(char)
    return b''.join(chars).decode('utf-8', errors='ignore')

def write_null_terminated_string(file_obj, string):
    file_obj.write(string.encode('utf-8'))
    file_obj.write(b'\x00')
  
def unpack(toc_group_file, output_dir = None):
    if not os.path.exists(toc_group_file):
        raise FileNotFoundError(f"toc_group file not found: {toc_group_file}")
    
    with open(toc_group_file, 'rb') as f:
        # Read header
        name = read_null_terminated_string(f)
        if name != TOC_NAME:
            raise Exception(f"Wrong {TOC_FILENAME} file. First string must be {TOC_NAME} not {name}")
        dir = read_null_terminated_string(f)
        type, unk = struct.unpack('<II', f.read(8))
        packfile_path = read_null_terminated_string(f)
        
        # Read number of files
        num_files = struct.unpack('<I', f.read(4))[0]
        
        file_entries = []
        for _ in range(num_files):
            filename = read_null_terminated_string(f)
            length, offset = struct.unpack('<II', f.read(8))
            print(filename)
            file_entries.append(Entry(filename, length, offset))
       
    path = Path(toc_group_file).parent.parent.absolute()
    script_path = os.path.abspath(__file__)   
    packfile_path = os.path.join(path.as_posix(), packfile_path)

    if not os.path.exists(packfile_path):
        packfile_path = os.path.join(os.path.dirname(script_path), PACKFILE_NAME)
        if not os.path.exists(packfile_path):
            raise FileNotFoundError(f"Packfile not found: {packfile_path}")
    
    # Create output directory
    if output_dir is None:
        os.path.join(os.path.dirname(script_path), OUT_DIR)
    os.makedirs(output_dir, exist_ok = True)
    
    # Extract files
    extracted_files = 0
    with open(packfile_path, 'rb') as packfile:
        for entry in file_entries:
            packfile.seek(entry.offset)
            file_data = packfile.read(entry.length)
            
            output_path = os.path.join(output_dir, entry.filename)
            
            with open(output_path, 'wb') as out_file:
                out_file.write(file_data)
            
            extracted_files += 1
            print(f"Extracted: {entry.filename} ({entry.length} bytes)")
    
    print(f"\nExtracted {extracted_files} files to: {output_dir}")
    return output_dir

def pack(input_dir, output_toc = None, output_packfile = None): 
    input_dir = Path(input_dir)
    
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    if not input_dir.is_dir():
        raise Exception(f"Input path is not a directory: {input_dir}")
    
    script_path = os.path.abspath(__file__)
    
    # Determine output file names
    if output_toc is None:
        output_toc = os.path.join(os.path.dirname(script_path), TOC_FILENAME)
    
    if output_packfile is None:
        output_packfile = os.path.join(os.path.dirname(script_path), PACKFILE_NAME)
    
    os.makedirs(os.path.dirname(output_packfile), exist_ok = True)
    os.makedirs(os.path.dirname(output_toc), exist_ok = True)
    
    # Prepare file entries
    file_entries = []
    offset = 0

    for file_path in input_dir.rglob('*'):
        if file_path.is_file():
            size = file_path.stat().st_size
            file_entries.append(Entry(file_path.name, size, offset))
            offset += size
            
    # Write packfile
    with open(output_packfile, 'wb') as packfile:
        for entry in file_entries:      
            with open(os.path.join(input_dir, entry.filename), 'rb') as infile:
                packfile.write(infile.read())
    
    # Write toc_group file
    with open(output_toc, 'wb') as toc_file:
        # Write header
        write_null_terminated_string(toc_file, TOC_NAME)
        write_null_terminated_string(toc_file, TOC_DIR)
        toc_file.write(struct.pack('<I', 2))
        toc_file.write(struct.pack('<I', 1))
        
        write_null_terminated_string(toc_file, TOC_REL_PATH)
        
        # Write number of files
        toc_file.write(struct.pack('<I', len(file_entries)))
        
        # Write file entries
        for entry in file_entries:
            write_null_terminated_string(toc_file, entry.filename)
            toc_file.write(struct.pack('<I', entry.length))
            toc_file.write(struct.pack('<I', entry.offset))
    
    print(f"  toc_group: {output_toc}")
    print(f"  packfile: {output_packfile}")

def main():
    parser = argparse.ArgumentParser(description='Pack/Unpack .toc_group and .packfile archives')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Unpack command
    unpack_parser = subparsers.add_parser('unpack', help='Unpack archive')
    unpack_parser.add_argument('toc_group', help='Input .toc_group file')
    unpack_parser.add_argument('-o', '--output', help='Output directory')
    
    # Pack command
    pack_parser = subparsers.add_parser('pack', help='Pack files into archive')
    pack_parser.add_argument('input_dir', help='Directory containing files to pack')
    pack_parser.add_argument('--toc-output', help='Output .toc_group file')
    pack_parser.add_argument('--packfile-output', help='Output .packfile file')
    
    args = parser.parse_args()
    
    if args.command == 'unpack':
        unpack(args.toc_group, args.output)
    elif args.command == 'pack':
        pack(args.input_dir, args.toc_output, args.packfile_output)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
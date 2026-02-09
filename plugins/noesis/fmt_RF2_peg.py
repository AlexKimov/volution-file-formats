from inc_noesis import *

def registerNoesisTypes():
    handle = noesis.register("Red Faction 2 textures", ".peg")
    noesis.setHandlerTypeCheck(handle, pegCheckType)
    noesis.setHandlerLoadRGBA(handle, pegLoadRGBA)

    return 1
     
def unswizzle_8bit_palette(palette):
    if len(palette) != 1024:
        raise ValueError("Input must be 1024 bytes bytes, got {})".format(len(palette)))
    
    result = bytearray(1024)
    
    # Process each 128-byte block
    for block in range(0, 1024, 128):
        # Calculate source positions for this block
        src_positions = [
            block,           # 0-31
            block + 64,      # 64-95  
            block + 32,      # 32-63
            block + 96       # 96-127
        ]
        
        # Calculate destination positions
        dest_positions = [
            block,           # 0-31
            block + 32,      # 32-63
            block + 64,      # 64-95
            block + 96       # 96-127
        ]
        
        # Copy each 32-byte segment
        for src, dest in zip(src_positions, dest_positions):
            result[dest:dest + 32] = palette[src:src + 32]
    
    return result     
     
class PEGTexture:  
    def __init__(self, filename = "", width = 0, height = 0, data = None): 
        self.width = width         
        self.height = height      
        self.filename = filename     
        self.data = data      


class PEGFileEntry:
    def __init__(self, reader):
        self.filereader = reader
        self.offset = 0
        self.width = 0         
        self.height = 0    
        self.flags = 0            
        self.flags2 = 0       
        self.name = 0
        self.offset = 0

    def read(self):
        self.width = self.filereader.readUShort()            
        self.height = self.filereader.readShort()     
        self.flags = self.filereader.readUInt()                       
        self.flags2 = self.filereader.readUInt()            
        self.name = noeAsciiFromBytes(self.filereader.readBytes(48))  
        self.offset = self.filereader.readUInt()         
  
class PEGImage:
    def __init__(self, reader):
        self.filereader = reader
        self.entries = []
        self.num = 0
        
    def parseHeader(self):
        magic = self.filereader.readUInt()
        if magic != 1447773511:
            return 1
            
        self.filereader.seek(12, NOESEEK_REL)                 
        self.num = self.filereader.readUInt()  
        self.filereader.seek(32, NOESEEK_ABS) 

        return 0
        
    def getImages(self):
        for image in self.entries:
            self.filereader.seek(image.offset, NOESEEK_ABS) 
            if image.flags & 0xFF == 7:
                data = self.filereader.readBytes(image.width * image.height * 4)            
                imageDecodedData = rapi.imageDecodeRaw(data, image.width, image.height, "r8g8b8a8") 
            elif image.flags & 0xFF == 4:
                if ((image.flags & 0xFF00) >> 8) == 2:                            
                    data = self.filereader.readBytes(1024)
                elif ((image.flags & 0xFF00) >> 8) == 1:                
                    palData = self.filereader.readBytes(512)
                    data =  rapi.imageDecodeRaw(palData, 16, 16, "r5g5b5a1")
                    
                palData = unswizzle_8bit_palette(data)                     
                pixelData = self.filereader.readBytes(image.width * image.height)  
                
                imageDecodedData = rapi.imageDecodeRawPal(pixelData, palData, image.width, image.height, 8, "r8g8b8a8")
            elif image.flags & 0xFF == 3:
                data = self.filereader.readBytes(image.width * image.height * 2)            
                imageDecodedData = rapi.imageDecodeRaw(data, image.width, image.height, "r5g5b5a1")                 
            else:
                print("Unsupported texture type {}".format(image.flags & 0xFF))
                imageDecodedData = None
            
            # remove alpha channel
            for i in range(0, image.width * image.height * 4, 4):           
                if imageDecodedData[i + 3] == 128:
                   imageDecodedData[i + 3] = 255            
            yield PEGTexture(image.name, image.width, image.height, imageDecodedData)          
             
    def readEntries(self):
        for _ in range(self.num):
            fileEntry = PEGFileEntry(self.filereader)
            fileEntry.read()
            self.entries.append(fileEntry)            
                             
    def read(self):
        self.parseHeader()
        self.readEntries()
        
    
def pegCheckType(data):

    return 1  


def pegLoadRGBA(data, texList):
    # noesis.logPopup() 
    imageFile = PEGImage(NoeBitStream(data))       
    imageFile.read() 
      
    for image in imageFile.getImages(): 
        texture = NoeTexture(image.filename, image.width, image.height, image.data, noesis.NOESISTEX_RGBA32)       
        texList.append(texture)
        
    return 1

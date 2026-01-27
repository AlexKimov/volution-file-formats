from inc_noesis import *


def registerNoesisTypes():
    handle = noesis.register("Red Faction 2 textures", ".peg")
    noesis.setHandlerTypeCheck(handle, pegCheckType)
    noesis.setHandlerLoadRGBA(handle, pegLoadRGBA)

    return 1
     
     
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
        self.type = 0            
        self.colors = 0       
        self.name = 0

    def read(self):
        self.width = self.filereader.readUShort()            
        self.height = self.filereader.readShort()     
        self.type = self.filereader.readUInt()                       
        self.colors = self.filereader.readUInt()            
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
            
        self.filereader.seek(4, NOESEEK_REL)        
        self.offset = self.filereader.readUInt()     
        self.filereader.seek(4, NOESEEK_REL)     
        self.num = self.filereader.readUInt()  
        self.filereader.seek(32, NOESEEK_ABS) 

        return 0
        
    def getImages(self):
        # format = {16842759:"r8g8b8a8", 16777732:"r8g8b8a8", 16843268:"a8r8g8b8"}
        for image in self.entries:
            self.filereader.seek(image.offset, NOESEEK_ABS) 
            if image.type & 0xFF == 7:
                data = self.filereader.readBytes(image.width * image.height * 4)            
                imageDecodedData = rapi.imageDecodeRaw(data, image.width, image.height, "r8g8b8a8") 
            elif image.type & 0xFF == 4:
                if ((image.type & 0xFF00) >> 8) == 2:
                    palData = self.filereader.readBytes(1024) 
                    format = "r8g8b8a8"
                elif ((image.type & 0xFF00) >> 8) == 1: 
                    palData = self.filereader.readBytes(512)
                    format = "r5g5b5a1"
                pixelData = self.filereader.readBytes(image.width * image.height)  
                
                imageDecodedData = rapi.imageDecodeRawPal(pixelData, palData, image.width, image.height, 8, format)
            elif image.type & 0xFF == 3:
                data = self.filereader.readBytes(image.width * image.height * 2)            
                imageDecodedData = rapi.imageDecodeRaw(data, image.width, image.height, "r5g5b5a1") 
                
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
    #noesis.logPopup() 
    imageFile = PEGImage(NoeBitStream(data))       
    imageFile.read() 
      
    for image in imageFile.getImages(): 
        texture = NoeTexture(image.filename, image.width, image.height, image.data, noesis.NOESISTEX_RGBA32)       
        texList.append(texture)
        
    return 1

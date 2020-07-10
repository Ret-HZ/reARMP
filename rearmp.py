# -*- coding: utf-8 -*-
import binascii
import sys
import json
import struct
import functools
from collections import OrderedDict


hexFile = b''
rebuildFileTemp = b''
exportDict = OrderedDict()
stringOffsetTable = []
stringTable = []




def readFromPosition (offset, size, value_type):
    valueToRead=(binascii.unhexlify(hexFile[offset*2:(offset+size)*2]))
    valueToRead=struct.unpack(value_type,valueToRead)
    valueToRead=functools.reduce(lambda rst, d: rst * 10 + d, (valueToRead))
    if type(valueToRead) is bytes: #String gets unpacked as bytes, we want to convert it to a regular string
        valueToRead = valueToRead.decode()
    return valueToRead



def writeToPosition (target, offset, size, value):
    target = target[:offset*2] + value + target[(offset + size)*2:]
    return target
    


def swapEndian(hexStr, value_type):
    original_value = binascii.unhexlify(hexStr) # <-- your hex here
    value = struct.unpack(value_type, original_value)
    value = functools.reduce(lambda rst, d: rst * 10 + d, (value))
    return value



def calculateSeparator(end): #Calculates the amount of null bytes that need to be added
    last_part_offset = int(hex(int(end))[-1],16) #This is retarded

	#Check the last digit of the hex value to calculate the amount that needs to be filled for the next table to start
    if (last_part_offset<0x4): 
        return 0x4-last_part_offset
    elif (last_part_offset>=0x4 and last_part_offset<0x8):
        return 0x8-last_part_offset
    elif (last_part_offset>=0x8 and last_part_offset<0xC):
        return 0xC-last_part_offset
    elif (last_part_offset>=0xC and last_part_offset<0x10):
        return 0x10-last_part_offset
    else:
        return 1



def storeTable (startOffset, tableSize, tableContainer): #Stores every entry of the table into the selected variable
    byteGroup = ""
    table = hexFile[(startOffset*2) : (startOffset*2)+(tableSize*4)*2].decode('utf-8')

    for nibble in table:
        if (len(byteGroup) <8):
            byteGroup += nibble
			
        if (len(byteGroup) == 8):
            tableContainer.append(byteGroup)
            byteGroup= ""



def iterateStringTable (tableContainer):
    for offset in stringOffsetTable:
        offset = swapEndian(offset, "<I")
        table = hexFile[(offset*2):] #A bit of a dirty approach but it will do for now
        string_end = table.find(b'00') 
        if (string_end % 2 != 0): #If the last hex digit ends with 0, the pointer will be odd, so we compensate adding 1
            string_end += 1
        string = binascii.unhexlify (table[:string_end]).decode()
        tableContainer.append(string)



def exportFile ():
    with open(file_path, "rb") as f:
        file=f.read()
    global hexFile
    hexFile=(binascii.hexlify(file))

    fileSize =                      len(hexFile)
    pointerToMainTable =            readFromPosition (0x10, 0x4, "<i")
    rowCount =                      readFromPosition (pointerToMainTable + 0x0, 0x4, "<i")
    columnCount =                   readFromPosition (pointerToMainTable + 0x4, 0x4, "<i")
    textCount =                     readFromPosition (pointerToMainTable + 0x8, 0x4, "<i")
    pointerToStringOffsetTable =    readFromPosition (pointerToMainTable + 0x10, 0x4, "<i")
    pointerToBitArray1 =           readFromPosition (pointerToMainTable + 0x14, 0x4, "<i")
    pointerToBytesArray1 =          readFromPosition (pointerToMainTable + 0x18, 0x4, "<i")
    pointerToIntArray1 =            readFromPosition (pointerToMainTable + 0x1C, 0x4, "<i")
    pointerToTextOffsetTable =      readFromPosition (pointerToMainTable + 0x24, 0x4, "<i")
    pointerToStringOffsetTable2 =   readFromPosition (pointerToMainTable + 0x28, 0x4, "<i")
    pointerToIntArray2 =            readFromPosition (pointerToMainTable + 0x30, 0x4, "<i")
    pointerToIntArray3 =            readFromPosition (pointerToMainTable + 0x34, 0x4, "<i")
    pointerToBitsArray2 =           readFromPosition (pointerToMainTable + 0x38, 0x4, "<i")
    pointerToAnotherTable =         readFromPosition (pointerToMainTable + 0x3C, 0x4, "<i")
    pointerToBytesArray2 =          readFromPosition (pointerToMainTable + 0x48, 0x4, "<i")
    pointerToBytesArray3 =          readFromPosition (pointerToMainTable + 0x4C, 0x4, "<i")


    #DEBUG
    print ("File size: " + str(fileSize))
    print ("Pointer to Main Table: " + str(pointerToMainTable))
    print ("Row Count: " + str(rowCount))
    print ("Column Count: " + str(columnCount))
    print ("Text Count: " + str(textCount))
    print ("Pointer to String Offset Table: " + str(pointerToStringOffsetTable))
    print ("Pointer to Bits Array Table: " + str(pointerToBitArray1))
    print ("Pointer to Byte Array Table: " + str(pointerToBytesArray1))
    print ("Pointer to Int Array Table: " + str(pointerToIntArray1))
    print ("Pointer to Text Offset Table: " + str(pointerToTextOffsetTable))
    print ("Pointer to String Offset Table 2: " + str(pointerToStringOffsetTable2))
    print ("Pointer to Int Array Table 2: " + str(pointerToIntArray2))
    print ("Pointer to Int Array Table 3: " + str(pointerToIntArray3))
    print ("Pointer to Bit Array Table 2: " + str(pointerToBitsArray2))
    print ("Pointer to Another Table: " + str(pointerToAnotherTable))
    print ("Pointer to Byte Array Table 2: " + str(pointerToBytesArray2))
    print ("Pointer to Byte Array Table 3: " + str(pointerToBytesArray3))


    storeTable (pointerToStringOffsetTable, rowCount, stringOffsetTable)
    iterateStringTable (stringTable)

    # PREPARE THE EXPORT DICTIONARY AND SAVE AS JSON
    exportDict["ROW_COUNT"] = rowCount
    #exportDict["COLUMN_COUNT"] = columnCount

    for element in stringTable:
        element_index = stringTable.index(element)
        rowDict = OrderedDict()
        rowDict[element] = {}
        exportDict[element_index] = element


    with open(file_name +'.json', 'w') as file:
        json.dump(exportDict, file, indent=2)




def rebuildFile ():
    with open(file_path, 'r') as file:
        data = json.load(file)
        #print(data)
        global rebuildFileTemp
        stringOffsetTableTemp = []
        rebuildFileTemp += b'61726D70' #Add magic
        rebuildFileTemp += b'00000000'
        rebuildFileTemp += b'0C000100' 
        rebuildFileTemp += b'00000000'
        rebuildFileTemp += b'20000000' #Pointer to main table (will always be the same)
        rebuildFileTemp += b'00000000'*3 #Fill padding
        rebuildFileTemp += b'00000000'*20 #Set the main table to all zeros for now


        pointerToBitArray1 = len(rebuildFileTemp)/2
        rebuildFileTemp += b'FF' * int(data["ROW_COUNT"]/8 ) # Write a dummy bitarray1 with all the flags set to 1
        rebuildFileTemp = writeToPosition(rebuildFileTemp, 0x34, 0x4, int(pointerToBitArray1).to_bytes(4, 'little').hex().encode() )


        for x in range(data["ROW_COUNT"]): #Write row String table and store offsets for the String offset table
            stringOffsetTableTemp.append(len(rebuildFileTemp)/2)
            rebuildFileTemp += binascii.hexlify( data[str(x)].encode())
            rebuildFileTemp += b'00' #Null byte
        rebuildFileTemp += b'00' * calculateSeparator(len(rebuildFileTemp)/2) #Add null bytes at the end of the String table

        stringOffsetTableOffset = len(rebuildFileTemp)/2
        for x in range(data["ROW_COUNT"]): #Write String Offset table
            rebuildFileTemp += int(stringOffsetTableTemp[x]).to_bytes(4, 'little').hex().encode()    

        
        rebuildFileTemp = writeToPosition(rebuildFileTemp, 0x20, 0x4, data["ROW_COUNT"].to_bytes(4, 'little').hex().encode() ) #Add the number of rows to the main table
        rebuildFileTemp = writeToPosition(rebuildFileTemp, 0x30, 0x4, int(stringOffsetTableOffset).to_bytes(4, 'little').hex().encode() ) #Add the pointer to the String Offset table to the main table


        with open(file_name +'.bin', 'wb') as file:
            file.write(binascii.unhexlify(rebuildFileTemp))








file_path = sys.argv[1:][0]
file_name = file_path.split("\\")[-1]
file_extension = file_name.split(".")[-1]


def determineFileExtension(file_extension): #Switch case based on the file extension
    switch = {
        "bin" : exportFile,
        "json" : rebuildFile
    }
    func = switch.get(file_extension.lower(), lambda: "Extension not supported")
    return func()


determineFileExtension(file_extension)
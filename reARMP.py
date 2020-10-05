# -*- coding: utf-8 -*-
import binascii
import sys
import json
import math
import struct
import functools
from collections import OrderedDict


hexFile = b''
rebuildFileTemp = bytearray()



def readFromPosition (offset, size, value_type):
    valueToRead=(binascii.unhexlify(hexFile[offset*2:(offset+size)*2]))
    valueToRead=struct.unpack(value_type,valueToRead)
    valueToRead=functools.reduce(lambda rst, d: rst * 10 + d, (valueToRead))
    if type(valueToRead) is bytes: #String gets unpacked as bytes, we want to convert it to a regular string
        valueToRead = valueToRead.decode()
    return valueToRead



def readFromPositionTarget (target ,offset, size, value_type):
    valueToRead=(binascii.unhexlify(target[offset*2:(offset+size)*2]))
    valueToRead=struct.unpack(value_type,valueToRead)
    valueToRead=functools.reduce(lambda rst, d: rst * 10 + d, (valueToRead))
    return valueToRead



def writeToPosition (target, offset, size, value):
    target[offset:offset + size] = value
    return target



def swapEndian(hexStr, value_type):
    original_value = binascii.unhexlify(hexStr)
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



def iteratePlainTextTable (tableContainer, offsetTable): 
    for offset in offsetTable:
        offset = swapEndian(offset, "<I")
        table = hexFile[(offset*2):] #A bit of a dirty approach but it will do for now
        string_end = table.find(b'00')
        while string_end % 2 !=0:
            string_end = table.find(b'00', string_end+1)
        string = binascii.unhexlify (table[:string_end]).decode()
        tableContainer.append(string)



def getColumnValueTextTableIndex (pointerToTable, numberOfEntries, row_index):
    table = hexFile[(pointerToTable*2):(pointerToTable + numberOfEntries*4)*2]
    table = [table[i:i+(4*2)] for i in range(0, len(table), (4*2))]
    index = table[row_index]    
    if version == 1 and index == b'ffffffff':
        return -1
    else:
        index = swapEndian(index, "<I")
        return index
        


def iterateValueTable (pointerToTable, numberOfEntries, valueType, valueSize):
    table = hexFile[(pointerToTable*2):(pointerToTable + numberOfEntries*valueSize)*2]
    table = [table[i:i+(valueSize*2)] for i in range(0, len(table), (valueSize*2))]
    returnList = []
    for entry in table:
        value = binascii.unhexlify(entry)
        value = struct.unpack(valueType , value)
        value = functools.reduce(lambda rst, d: rst * 10 + d, (value))
        returnList.append(value)
    return returnList



def iterateValidityBoolTable (pointerToTable, numberOfEntries):
    table = hexFile[(pointerToTable*2):(pointerToTable + numberOfEntries*4)*2]
    table = [table[i:i+2] for i in range(0, len(table), 2)]
    returnList = []
    for entry in table:
        entry_binary = "{0:08b}".format(int(entry,16))
        returnList.append(entry_binary)
    return returnList



def iterateBitmaskTable (pointerToTable, numberOfEntries):
    table = hexFile[(pointerToTable*2):(pointerToTable + abs(math.ceil(numberOfEntries/8)))*2]
    table = [table[i:i+2] for i in range(0, len(table), 2)]
    returnList = []
    for entry in table:
        entry_binary = list("{0:08b}".format(int(entry,16)))
        entry_binary.reverse()
        returnList.extend(entry_binary)
    return returnList



def getColumnInfo (pointerToColumnDataTypes, pointerToColumnDataTypesAux, pointerToColumnValidity, columnCount, columnNames):
    columnInfo = OrderedDict()
    columnValidity = OrderedDict()
    columnTypes = OrderedDict()
    columnTypes2 = OrderedDict()
    types = iterateValueTable (pointerToColumnDataTypes, columnCount, "<b", 1)
    types2 = iterateValueTable (pointerToColumnDataTypesAux, columnCount, "<b", 1)
    if pointerToColumnValidity != -1:
        validity = iterateBitmaskTable (pointerToColumnValidity, columnCount)
    iterator = 0

    for column in columnNames:
        if pointerToColumnValidity != -1 and pointerToColumnValidity != 0:
            columnValidity[column] = validity[iterator]
        columnTypes[column] = types[iterator]
        columnTypes2[column] = types2[iterator]
        iterator += 1

    if pointerToColumnValidity != -1 and pointerToColumnValidity != 0:
        columnInfo["columnValidity"] = columnValidity
    columnInfo["columnTypes"] = columnTypes
    if version == 1:
        columnInfo["columnTypes2"] = columnTypes2
    return columnInfo



def getColumnInfoTable (pointerToTable, numberOfEntries):
    table = hexFile[(pointerToTable*2):(pointerToTable + numberOfEntries*16)*2]
    offset = 0
    returnList = []
    for column in range(numberOfEntries):
        typeValue = readFromPositionTarget(table, offset, 4, "<i")
        offsetShift = readFromPositionTarget(table, offset+4, 4, "<i")
        specialSize = readFromPositionTarget(table, offset+8, 4, "<i")
        columnData = [typeValue, offsetShift, specialSize]
        returnList.append(columnData)
        offset += 16
    return returnList



def exportTable(pointerToMainTable):
    exportDict = OrderedDict()
    rowNamesOffsetTable = []
    rowNamesTable = []
    columnNamesOffsetTable = []
    columnNames = []
    textOffsetTable = []
    textTable = []
    columnContentOffsetTable = []
    ValidityBoolTable = []
    rowIndices = []
    columnIndices = []
    unknownOffsetTable = []
    unknownBitmask = []

    rowCount =                          readFromPosition (pointerToMainTable + 0x0, 0x4, "<i")
    columnCount =                       readFromPosition (pointerToMainTable + 0x4, 0x4, "<i")
    textCount =                         readFromPosition (pointerToMainTable + 0x8, 0x4, "<i")
    pointerToRowNamesOffsetTable =      readFromPosition (pointerToMainTable + 0x10, 0x4, "<i")
    pointerToRowValidity =              readFromPosition (pointerToMainTable + 0x14, 0x4, "<i")
    pointerToColumnDataTypes =          readFromPosition (pointerToMainTable + 0x18, 0x4, "<i")
    pointerToColumnContentOffsetTable = readFromPosition (pointerToMainTable + 0x1C, 0x4, "<i")
    pointerToTextOffsetTable =          readFromPosition (pointerToMainTable + 0x24, 0x4, "<i")
    pointerToColumnNamesOffsetTable =   readFromPosition (pointerToMainTable + 0x28, 0x4, "<i")
    pointerToRowIndices =               readFromPosition (pointerToMainTable + 0x30, 0x4, "<i")
    pointerToColumnIndices =            readFromPosition (pointerToMainTable + 0x34, 0x4, "<i")
    pointerToColumnValidity =           readFromPosition (pointerToMainTable + 0x38, 0x4, "<i")
    pointerToSubTable =                 readFromPosition (pointerToMainTable + 0x3C, 0x4, "<i")
    pointerToBitmaskOffsetTable =       readFromPosition (pointerToMainTable + 0x44, 0x4, "<i")
    pointerToColumnDataTypesAux =       readFromPosition (pointerToMainTable + 0x48, 0x4, "<i")
    pointerToValidityBool =             readFromPosition (pointerToMainTable + 0x4C, 0x4, "<i")


    #DEBUG OUTPUT
    print ("Pointer to Main Table: " + str(pointerToMainTable))
    print ("Row Count: " + str(rowCount))
    print ("Column Count: " + str(columnCount))
    print ("Text Count: " + str(textCount))
    print ("Pointer to Row Names Offset Table: " + str(pointerToRowNamesOffsetTable))
    print ("Pointer to Row Validity Array: " + str(pointerToRowValidity))
    print ("Pointer to Column Data Types: " + str(pointerToColumnDataTypes))
    print ("Pointer to Column Content Offset Table: " + str(pointerToColumnContentOffsetTable))
    print ("Pointer to Text Offset Table: " + str(pointerToTextOffsetTable))
    print ("Pointer to Column Names Offset Table: " + str(pointerToColumnNamesOffsetTable))
    print ("Pointer to Row Index Array: " + str(pointerToRowIndices))
    print ("Pointer to Column Index Array: " + str(pointerToColumnIndices))
    print ("Pointer to Column Validity Array: " + str(pointerToColumnValidity))
    print ("Pointer to SubTable: " + str(pointerToSubTable))
    print ("Pointer to Unknown Bitmask Pointer Table: " + str(pointerToBitmaskOffsetTable))
    print ("Pointer to Auxiliary Column Data Types: " + str(pointerToColumnDataTypesAux))
    print ("Pointer to ValidityBool Array: " + str(pointerToValidityBool))

    print ("\nExporting...")

    #Strings 1 / Rows
    #Check if the file has named rows
    if pointerToRowNamesOffsetTable != 0:
        storeTable (pointerToRowNamesOffsetTable, rowCount, rowNamesOffsetTable) 
        iteratePlainTextTable (rowNamesTable, rowNamesOffsetTable)
        hasRowNames = True

    else: #If there are no named rows, a dummy will be placed instead
        for row in range(0, rowCount):
            rowNamesTable.append('')
        hasRowNames = False


    #Strings 2 / Columns
    #Check if the file has named columns
    if pointerToColumnNamesOffsetTable != 0:
        storeTable (pointerToColumnNamesOffsetTable, columnCount, columnNamesOffsetTable) 
        iteratePlainTextTable (columnNames, columnNamesOffsetTable)
        hasColumnNames = True

    else: #If there are no named columns, a dummy will be placed instead
        for column in range(0, columnCount):
            columnNames.append(str(column))
        hasColumnNames = False




    #Columns
    storageMode = readFromPosition(pointerToMainTable + 0x23, 1, "<B") #How data is stored. This only affects v2 armps. 0 = per column, 1 = per row
    columnContentOffsetTable = []
    if (columnCount > 0):
        if storageMode == 1:
            storeTable (pointerToColumnContentOffsetTable, rowCount, columnContentOffsetTable)
        else:
            storeTable (pointerToColumnContentOffsetTable, columnCount, columnContentOffsetTable)
        offsetTable = []
        for offset in columnContentOffsetTable:
            offsetTable.append(swapEndian(offset, "<I"))
        columnContentOffsetTable = offsetTable
        

    #Text
    if (textCount > 0):
        storeTable (pointerToTextOffsetTable, textCount, textOffsetTable) 
        iteratePlainTextTable (textTable, textOffsetTable)


    #ValidityBool
    if (pointerToValidityBool != 0 and pointerToValidityBool != -1): 
        validityBoolTable = iterateValidityBoolTable(pointerToValidityBool, rowCount) 
    else:
        validityBoolTable = None


    #Row validity
    if (pointerToRowValidity != -1) and (pointerToRowValidity != 0):
        row_validity = iterateBitmaskTable (pointerToRowValidity, rowCount)
        hasRowValidity = True
    else:
        row_validity = None
        hasRowValidity = False
        

    #Column validity
    if (pointerToColumnValidity != -1) and (pointerToColumnValidity != 0):
        column_validity = iterateBitmaskTable (pointerToColumnValidity, rowCount)
        hasColumnValidity = True
    else:
        column_validity = None
        hasColumnValidity = False


    #Row Index number
    if (pointerToRowIndices != -1) and (pointerToRowIndices != 0):
        rowIndices = iterateValueTable(pointerToRowIndices, rowCount, "<i", 4)
        hasRowIndices = True
    else:
        hasRowIndices = False


    #Column Indices
    if (pointerToColumnIndices != -1) and (pointerToColumnIndices != 0):
        columnIndices = iterateValueTable(pointerToColumnIndices, columnCount, "<i", 4)


    #Unknown Bitmask
    if (pointerToBitmaskOffsetTable != -1) and (pointerToBitmaskOffsetTable != 0):
        unknownOffsetTable = iterateValueTable(pointerToBitmaskOffsetTable, columnCount, "<i", 4)
        for offset in unknownOffsetTable:
            if offset != 0 and offset != -1:
                bitmask = iterateBitmaskTable (offset, rowCount)
                unknownBitmask.append(bitmask)
            else:
                dummy = []
                unknownBitmask.append(dummy)
        hasUnknownBitmask = True
    else:
        hasUnknownBitmask = False


    # Fill the dictionary
    if version == 2:
        exportDict["STORAGE_MODE"] = storageMode
    exportDict["ROW_COUNT"] = rowCount
    exportDict["COLUMN_COUNT"] = columnCount
    exportDict["TEXT_COUNT"] = textCount
    exportDict["HAS_ROW_NAMES"] = hasRowNames
    exportDict["HAS_COLUMN_NAMES"] = hasColumnNames
    exportDict["HAS_ROW_VALIDITY"] = hasRowValidity
    exportDict["HAS_COLUMN_VALIDITY"] = hasColumnValidity
    exportDict["HAS_UNKNOWN_BITMASK"] = hasUnknownBitmask
    exportDict["HAS_ROW_INDICES"] = hasRowIndices
    exportDict.update ( getColumnInfo(pointerToColumnDataTypes, pointerToColumnDataTypesAux, pointerToColumnValidity, columnCount, columnNames) )
    if (len(columnIndices) != 0):
        exportDict["COLUMN_INDICES"] = columnIndices

    #Store Column values

    #FOTNS, 6 and K2
    if version == 1: 
        columnTypes = exportDict["columnTypes2"]
        unused = -1
        uint8 = 0
        uint16 = 1
        uint32 = 2
        uint64 = 3
        int8 = 4
        int16 = 5
        int32 = 6
        int64 = 7
        float32 = 9
        boolean = 11
        string = 12
        table = 13


        columnValues = {}
        for column in columnNames:
            column_index = columnNames.index(column)

            if (columnTypes[str(column)] == unused): #Skip unused columns
                emptyList = []
                columnValues[column] = emptyList
                continue

            if (columnTypes[str(column)] == uint8): #Int8 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<B", 1)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == uint16): #Int16 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<H", 2)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == uint32): #Int32 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<I", 4)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == uint64): #Int64 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<Q", 8)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == int8): #Int8 signed
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<b", 1)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == int16): #Int16 signed
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<h", 2)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == int32): #Int32 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<i", 4)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == int64): #Int64 unsigned
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<q", 8)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == float32): #float32
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<f", 4)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == boolean): #boolean
                valueTable = iterateBitmaskTable (columnContentOffsetTable[column_index], rowCount)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == table): #Table
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<q", 8)
                columnValues[column] = valueTable
                continue



        row_index = 0
        for row in rowNamesTable: #Element per row
            columnDict = OrderedDict() #Column contents
            columnDict[row] = {}


            for column in columnNames: #Iterate through each column
                column_index = columnNames.index(column)

                if (columnTypes[str(column)] == unused): #Skip unused columns
                    continue

                if len(unknownBitmask) > 0 and len(unknownBitmask[column_index]) > 0: #Unknown Bitmask
                    columnData = {str(column)+"_unknownBool" : unknownBitmask[column_index][row_index]}
                    columnDict[row].update(columnData)

                if (columnTypes[str(column)] != string) and (columnTypes[str(column)] != table) and (len(columnValues[column]) > 0) :
                    columnData = {str(column) : columnValues[column][row_index]}
                    columnDict[row].update(columnData)
                    continue

                if (columnTypes[str(column)] == string): #String
                    index = getColumnValueTextTableIndex (columnContentOffsetTable[column_index], rowCount, row_index)
                    if (index == -1):
                        continue
                    columnData = {str(column) : textTable[index]}
                    columnDict[row].update(columnData)
                    continue

                if (columnTypes[str(column)] == table): #Table
                    pointer = columnValues[column][row_index]
                    if pointer != 0 and pointer != -1:
                        columnData = {str(column) : exportTable(pointer)}
                        columnDict[row].update(columnData)



            #Add the validityBool if present
            if (validityBoolTable is not None): 
                columnData = {'reARMP_validityBool' : validityBoolTable[row_index]}
                columnDict[row].update(columnData)

            #Row Validity
            if (hasRowValidity is not False):
                columnData = {'reARMP_isValid' : row_validity[row_index]}
                columnDict[row].update(columnData)

            #Row Index
            if (len(rowIndices) != 0):
                columnData = {'reARMP_rowIndex' : rowIndices[row_index]}
                columnDict[row].update(columnData)


            exportDict[row_index] = columnDict
            print ("Entry "+str(row_index+1) + " / "+str(rowCount))
            row_index +=1


        #subTable
        if pointerToSubTable != 0 and pointerToSubTable != -1:
            subTable = exportTable(pointerToSubTable)
            exportDict['subTable'] = subTable

        return exportDict


############################################################################################################ TODO Storage mode 0 code needs cleanup. v2 arrays need to be implemented
    #Judgment
    if version == 2: 
        columnTypes = exportDict["columnTypes"]
        unused = -1
        uint8 = 2
        uint16 = 1
        uint32 = 0
        uint64 = 8
        int8 = 5
        int16 = 4
        int32 = 3
        int64 = 10
        float32 = 7
        float64 = 11
        boolean = 6
        string = 13
        table = 9




        #columnDict = OrderedDict() #Column contents

        if storageMode == 0:

            columnValues = {}
            for column in columnNames:
                column_index = columnNames.index(column)

                if (columnTypes[str(column)] == unused): #Skip unused columns
                    emptyList = []
                    columnValues[column] = emptyList
                    continue

                if (columnTypes[str(column)] == uint8): #Int8 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<B", 1)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == uint16): #Int16 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<H", 2)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == uint32): #Int32 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<I", 4)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == uint64): #Int64 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<Q", 8)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == int8): #Int8 signed
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<b", 1)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == int16): #Int16 signed
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<h", 2)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == int32): #Int32 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<i", 4)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == int64): #Int64 unsigned
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<q", 8)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == float32): #float32
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<f", 4)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == float64): #float64
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<d", 8)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == boolean): #boolean
                    valueTable = iterateBitmaskTable (columnContentOffsetTable[column_index], rowCount)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == table): #Table
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<q", 8)
                    columnValues[column] = valueTable
                    continue



            row_index = 0
            for row in rowNamesTable: #Element per row
                columnDict = OrderedDict() #Column contents
                columnDict[row] = {}


                for column in columnNames: #Iterate through each column
                    column_index = columnNames.index(column)

                    if (columnTypes[str(column)] == unused): #Skip unused columns
                        continue

                    if len(unknownBitmask) > 0 and len(unknownBitmask[column_index]) > 0: #Unknown Bitmask
                        columnData = {str(column)+"_unknownBool" : unknownBitmask[column_index][row_index]}
                        columnDict[row].update(columnData)

                    if (columnTypes[str(column)] != string) and (columnTypes[str(column)] != table) and (len(columnValues[column]) > 0) :
                        columnData = {str(column) : columnValues[column][row_index]}
                        columnDict[row].update(columnData)
                        continue

                    if (columnTypes[str(column)] == string): #String
                        index = getColumnValueTextTableIndex (columnContentOffsetTable[column_index], rowCount, row_index)
                        if (index == -1):
                            continue
                        columnData = {str(column) : textTable[index]}
                        columnDict[row].update(columnData)
                        continue

                    if (columnTypes[str(column)] == table): #Table
                        pointer = columnValues[column][row_index]
                        if pointer != 0 and pointer != -1:
                            columnData = {str(column) : exportTable(pointer)}
                            columnDict[row].update(columnData)



                #Add the validityBool if present
                if (validityBoolTable is not None): 
                    columnData = {'reARMP_validityBool' : validityBoolTable[row_index]}
                    columnDict[row].update(columnData)

                #Row Validity
                if (hasRowValidity is not False):
                    columnData = {'reARMP_isValid' : row_validity[row_index]}
                    columnDict[row].update(columnData)

                #Row Index
                if (len(rowIndices) != 0):
                    columnData = {'reARMP_rowIndex' : rowIndices[row_index]}
                    columnDict[row].update(columnData)


                exportDict[row_index] = columnDict
                print ("Entry "+str(row_index+1) + " / "+str(rowCount))
                row_index +=1


            #subTable
            if pointerToSubTable != 0 and pointerToSubTable != -1:
                subTable = exportTable(pointerToSubTable)
                exportDict['subTable'] = subTable

            return exportDict




        if storageMode == 1:

            valueSizes = {
                0 : 0x4, #uint32
                1 : 0x2, #uint16
                2 : 0x1, #int8
                3 : 0x4, #int32
                4 : 0x2, #int16
                5 : 0x1, #int8
                7 : 0x4, #float32
                6 : 0x1, #bool
                8 : 0x8, #uint64
                9 : 0x8, #table
                10 : 0x8, #int64
                11 : 0x8, #float64
                13 : 0x4 #String
            }

            types = {
                0 : "I", #u32
                1 : "H", #u16
                2 : "B", #u8
                3 : "i", #32
                4 : "h", #16
                5 : "b", #8
                6 : "b", #bool
                7 : "f", #float32
                8 : "Q", #u64
                11 : "d", #float64
                10 : "q" #64
            }

            columnDict = OrderedDict() #Column contents
            columnInfo = getColumnInfoTable (pointerToColumnDataTypesAux, columnCount)
            row_index = 0
            for row in rowNamesTable:
                
                columnDict[row] = {}

                offset = columnContentOffsetTable[row_index]
                for column in columnNames:
                    column_index = columnNames.index(column)

                    if columnTypes[column] != -1:
                        if columnTypes[column] in [0,1,2,3,4,5,6,7,8,10,11]:
                            value = readFromPosition(offset + columnInfo[column_index][1], valueSizes[columnTypes[column]], "<"+types[columnTypes[column]])

                            columnData = {column : value}
                            columnDict[row].update(columnData)

                        if columnTypes[column] == string: #String
                            index = readFromPosition(offset + columnInfo[column_index][1], 4, "<i")
                            if (index == 0):
                                continue
                            columnData = {str(column) : textTable[index]}
                            columnDict[row].update(columnData)

                        if columnTypes[column] == table: #Table
                            pointer = readFromPosition(offset + columnInfo[column_index][1], 4, "<I")
                            if pointer != 0 and pointer != -1:
                                columnData = {str(column) : exportTable(pointer)}
                                columnDict[row].update(columnData)

                    else:
                        continue

                #Add the validityBool if present
                if (validityBoolTable is not None): 
                    columnData = {'reARMP_validityBool' : validityBoolTable[row_index]}
                    columnDict[row].update(columnData)

                if (hasRowValidity is not False):
                    columnData = {'reARMP_isValid' : row_validity[row_index]}
                    columnDict[row].update(columnData)

                #Row Index
                if (len(rowIndices) != 0):
                    columnData = {'reARMP_rowIndex' : rowIndices[row_index]}
                    columnDict[row].update(columnData)
                
                rowExport = {}
                rowExport[str(row)] = columnDict[row]
                exportDict[row_index] = rowExport
                print ("Entry "+str(row_index+1) + " / "+str(rowCount))
                row_index += 1

            #subTable
            if pointerToSubTable != 0 and pointerToSubTable != -1:
                subTable = exportTable(pointerToSubTable)
                exportDict['subTable'] = subTable

            return exportDict



def exportFile ():
    with open(file_path, "rb") as f:
        file=f.read()
    global hexFile
    hexFile=(binascii.hexlify(file))
    global fileSize
    fileSize =                      len(hexFile)
    global version
    version =                       readFromPosition (0xA, 0x2, "<H")
    global revision
    revision =                      readFromPosition (0x8, 0x2, "<H")
    pointerToMainTable =            readFromPosition (0x10, 0x4, "<I")

    exportDict = OrderedDict()
    exportDict["VERSION"] = version
    exportDict["REVISION"] = revision
    exportDict.update(exportTable (pointerToMainTable))


    with open(file_name +'.json', 'w', encoding='utf8') as file:
        json.dump(exportDict, file, indent=2, ensure_ascii=False)



def storeJSONInfo (data):
    row_count = data['ROW_COUNT']
    column_count = data['COLUMN_COUNT']
    text_count = data['TEXT_COUNT']
    has_row_names = data['HAS_ROW_NAMES']
    has_column_names = data['HAS_COLUMN_NAMES']
    has_row_validity = data['HAS_ROW_VALIDITY']
    has_column_validity = data['HAS_COLUMN_VALIDITY']
    has_row_indices = data['HAS_ROW_INDICES']
    has_unknown_bitmask = data['HAS_UNKNOWN_BITMASK']
    if 'COLUMN_INDICES' in data:
        column_indices = data['COLUMN_INDICES']
    else:
        column_indices = None
    
    rowNames = []
    if has_row_names == True:
        for entry in range(0, row_count): #Store row names
            rowNames.append( list(data[str(entry)])[0] )
    else:
        rowNames = [''] * row_count


    columnNames = list(data['columnTypes'].keys()) #Store column names

    rowContent = []
    for entry in range(0, row_count):
        rowContent.append( data[str(entry)][rowNames[entry]] )


    text = []
    if text_count > 0: #Store Text
        for entry in range(0, row_count):
            for column in columnNames:
                if data['columnTypes2'][column] == 12:
                    if column in data[str(entry)][rowNames[entry]]:
                        string = data[str(entry)][rowNames[entry]][str(column)]
                        if string not in text:
                            text.append(string)
    text_count = len(text)

    if row_count > 0:
        if 'reARMP_validityBool' in rowContent[0]:
            has_validitybool = True
        else:
            has_validitybool = False
    else:
        has_validitybool = False
    
    jsonInfo = {'ROW_COUNT' : row_count, 'COLUMN_COUNT' : column_count, 'TEXT_COUNT' : text_count, 'HAS_ROW_NAMES' : has_row_names, 'HAS_COLUMN_NAMES' : has_column_names, 'HAS_ROW_VALIDITY' : has_row_validity,
    'HAS_COLUMN_VALIDITY' : has_column_validity, 'HAS_ROW_INDICES' : has_row_indices, 'COLUMN_INDICES' : column_indices, 'ROW_NAMES' : rowNames, 'COLUMN_NAMES' : columnNames, 'TEXT' : text, 'ROW_CONTENT' : rowContent,
     'HAS_VALIDITYBOOL' : has_validitybool, 'HAS_UNKNOWN_BITMASK' : has_unknown_bitmask}
    return jsonInfo


    
def rebuildFile ():
    with open(file_path, 'r', encoding='utf8') as file:
        data = json.load(file)
        global rebuildFileTemp
        
        initializeRebuildFile (data['VERSION'], data['REVISION'])
        importTable (data)


        with open(file_name +'.bin', 'wb') as file:
            file.write(rebuildFileTemp)



def initializeRebuildFile (ver, revision):
    global rebuildFileTemp
    global version
    version = ver
    rebuildFileTemp += b'\x61\x72\x6D\x70' #Add magic
    rebuildFileTemp += b'\x00\x00\x00\x00'
    rebuildFileTemp += revision.to_bytes(2, 'little')
    rebuildFileTemp += version.to_bytes(2, 'little')
    rebuildFileTemp += b'\x00\x00\x00\x00'
    rebuildFileTemp += b'\x20\x00\x00\x00' #Pointer to main table (will always be the same)
    rebuildFileTemp += b'\x00\x00\x00\x00'*3 #Fill padding



def importTable (data):
    jsonInfo = storeJSONInfo(data)
    print ("Rebuilding...")
    global rebuildFileTemp

    pointerToMainTable = len(rebuildFileTemp)
    #Initialize empty main table
    rebuildFileTemp += b'\x00\x00\x00\x00'*3
    rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
    rebuildFileTemp += b'\x00\x00\x00\x00'
    rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
    rebuildFileTemp += b'\x00\x00\x00\x00'*5
    rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
    rebuildFileTemp += b'\x00\x00\x00\x00'*2
    rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
    rebuildFileTemp += b'\x00\x00\x00\x00'*5

    #Row Validity
    if jsonInfo['HAS_ROW_VALIDITY'] == True:
        pointerToRowValidity = len(rebuildFileTemp)
        binary = ''
        for row in range(0, jsonInfo['ROW_COUNT']):
            bit = jsonInfo['ROW_CONTENT'][row]['reARMP_isValid']
            if len(binary) < 8:
                binary += bit
            if len(binary) == 8:
                binary = binary[::-1]
                binary = int(binary, 2).to_bytes(1, 'little')
                rebuildFileTemp += binary
                binary = ''
            if row == jsonInfo['ROW_COUNT']-1:
                binary = binary.ljust(8, '0')
                binary = binary[::-1]
                binary = int(binary, 2).to_bytes(1, 'little')
                rebuildFileTemp += binary

        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x14, 0x4, int(pointerToRowValidity).to_bytes(4, 'little') )
        rebuildFileTemp += b'\x00\x00\x00\x00' + b'\x00'*calculateSeparator(len(rebuildFileTemp)) #Padding


    #Column Validity
    if jsonInfo['HAS_COLUMN_VALIDITY'] == True:
        pointerToBitArray2 = len(rebuildFileTemp)
        binary = ''
        for column in range(0, jsonInfo['COLUMN_COUNT']):
            bit = data['columnValidity'][jsonInfo['COLUMN_NAMES'][column]]
            if len(binary) < 8:
                binary += bit
            if len(binary) == 8:
                binary = binary[::-1]
                binary = int(binary, 2).to_bytes(1, 'little')
                rebuildFileTemp += binary
                binary = ''
            if column == jsonInfo['COLUMN_COUNT']-1:
                binary = binary.ljust(8, '0')
                binary = binary[::-1]
                binary = int(binary, 2).to_bytes(1, 'little')
                rebuildFileTemp += binary
        
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x38, 0x4, int(pointerToBitArray2).to_bytes(4, 'little') )
        rebuildFileTemp += b'\x00'*calculateSeparator(len(rebuildFileTemp)) #Padding


    #Row Entries
    if jsonInfo['HAS_ROW_NAMES'] == True:
        rowNamesOffsetTableTemp = []
        for x in range(jsonInfo["ROW_COUNT"]): #Write row String table and store offsets for the String offset table
            rowNamesOffsetTableTemp.append(len(rebuildFileTemp))
            rebuildFileTemp += jsonInfo["ROW_NAMES"][x].encode()
            rebuildFileTemp += b'\x00' #Null byte
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp)) #Add null bytes at the end of the String table

        #Row Entries Offset Table
        rowNamesOffsetTableOffset = len(rebuildFileTemp)
        for x in range(jsonInfo["ROW_COUNT"]): #Write String Offset table
            rebuildFileTemp += int(rowNamesOffsetTableTemp[x]).to_bytes(4, 'little')    

    #Row Entries and Row Entries Offset table pointers in Main Table
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x10, 0x4, int(rowNamesOffsetTableOffset).to_bytes(4, 'little') ) #Add the pointer to the String Offset table to the main table
    rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x0, 0x4, jsonInfo["ROW_COUNT"].to_bytes(4, 'little') ) #Add the number of rows to the main table

    
    #Column Names
    if jsonInfo['COLUMN_COUNT'] > 0:
        if jsonInfo['HAS_COLUMN_NAMES'] == True:
            columnNamesOffsetTableTemp = []
            for x in range(jsonInfo["COLUMN_COUNT"]): #Write Column String table and store offsets for the String offset table 2
                columnNamesOffsetTableTemp.append(len(rebuildFileTemp))
                rebuildFileTemp += jsonInfo["COLUMN_NAMES"][x].encode()
                rebuildFileTemp += b'\x00' #Null byte
            rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp)) #Add null bytes at the end of the String table 2

            #Column Names Offset Table
            columnNamesOffsetTableOffset = len(rebuildFileTemp)
            for x in range(jsonInfo["COLUMN_COUNT"]): #Write String Offset table 2
                rebuildFileTemp += int(columnNamesOffsetTableTemp[x]).to_bytes(4, 'little') 

        #Column Names and Column Names Offset table pointers in Main Table
            rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x28, 0x4, int(columnNamesOffsetTableOffset).to_bytes(4, 'little') ) #Add the pointer to the String Offset table 2 to the main table
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x4, 0x4, jsonInfo["COLUMN_COUNT"].to_bytes(4, 'little') ) #Add the number of columns to the main table


    #Text
    if jsonInfo['TEXT_COUNT'] > 0:
        textOffsetTableTemp = []
        for text in jsonInfo["TEXT"]: #Write Text table and store offsets for the Text offset table
            textOffsetTableTemp.append(len(rebuildFileTemp))
            rebuildFileTemp += text.encode()
            rebuildFileTemp += b'\x00' #Null byte
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp)) #Add null bytes at the end of the String table 2

        #Text Offset Table
        textOffsetTableOffset = len(rebuildFileTemp)
        for x in range(jsonInfo["TEXT_COUNT"]): #Write String Offset table 2
            rebuildFileTemp += int(textOffsetTableTemp[x]).to_bytes(4, 'little')

        #Text and Text Offset table pointers in Main Table
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x8, 0x4, jsonInfo["TEXT_COUNT"].to_bytes(4, 'little') ) #Add the number of text entries to the main table
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x24, 0x4, int(textOffsetTableOffset).to_bytes(4, 'little') ) #Add the pointer to the Text Offset table to the main table


    #ColumnTypes2
    if version == 1:
        columnTypes2Offset = len(rebuildFileTemp)
        for column in jsonInfo['COLUMN_NAMES']:
            rebuildFileTemp += data['columnTypes'][column].to_bytes(1, 'little', signed = True)
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x18, 0x4, int(columnTypes2Offset).to_bytes(4, 'little') ) #Add pointer to the main table


    #ColumnTypes
    if version == 1:
        columnTypesOffset = len(rebuildFileTemp)
        for column in jsonInfo['COLUMN_NAMES']:
            rebuildFileTemp +=  data['columnTypes2'][column].to_bytes(1, 'little', signed = True) 
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x48, 0x4, int(columnTypesOffset).to_bytes(4, 'little') ) #Add pointer to the main table


    #Column Values
    if version == 1:
        columnValueOffsets = []
        tableOffsets = [] #Table pointers
        tables = [] #Tables
        for column in jsonInfo['COLUMN_NAMES']:
            if jsonInfo['HAS_COLUMN_VALIDITY'] == True and data['columnValidity'][column] != "1":
                columnValueOffsets.append(0)
            else:
                columnValueOffsets.append(int(len(rebuildFileTemp)))

                bool_bitmask = '' #Initialize the bool bitmask in case there are boolean columns
                for row in range(0, jsonInfo['ROW_COUNT']):
                    if column not in jsonInfo['ROW_CONTENT'][row]:
                        if data['columnTypes2'][str(column)] == 13:
                            rebuildFileTemp += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        else:
                            rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
                    else:

                        if data['columnTypes2'][column] == 0: #Int8 unsigned
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(1, 'little', signed = False)

                        elif data['columnTypes2'][column] == 1: #Int16 unsigned
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(2, 'little', signed = False)

                        elif data['columnTypes2'][column] == 2: #Int32 unsigned
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(4, 'little', signed = False)

                        elif data['columnTypes2'][column] == 3: #Int64 unsigned
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(8, 'little', signed = False)

                        elif data['columnTypes2'][column] == 4: #Int8 signed
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(1, 'little', signed = True)

                        elif data['columnTypes2'][column] == 5: #Int16 signed
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(2, 'little', signed = True)

                        elif data['columnTypes2'][column] == 6: #Int32 signed
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(4, 'little', signed = True)

                        elif data['columnTypes2'][column] == 7: #Int64 signed
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(8, 'little', signed = True)
                        
                        elif data['columnTypes2'][column] == 9: #float32
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            value = bytes(bytearray(struct.pack("<f", value)))
                            rebuildFileTemp += value

                        elif data['columnTypes2'][column] == 12: #String
                            index = jsonInfo['TEXT'].index(jsonInfo['ROW_CONTENT'][row][column])
                            rebuildFileTemp += index.to_bytes(4, 'little')

                        elif data['columnTypes2'][column] == 11: #Boolean
                            bit = jsonInfo['ROW_CONTENT'][row][column]
                            if len(bool_bitmask) < 8:
                                bool_bitmask += bit
                            if len(bool_bitmask) == 8:
                                bool_bitmask = bool_bitmask[::-1]
                                bool_bitmask = int(bool_bitmask, 2).to_bytes(1, 'little', signed=False)
                                rebuildFileTemp += bool_bitmask
                                bool_bitmask = ''
                            if row == jsonInfo['ROW_COUNT']-1:
                                bool_bitmask = bool_bitmask.ljust(8, '0')
                                bool_bitmask = bool_bitmask[::-1]
                                bool_bitmask = int(bool_bitmask, 2).to_bytes(1, 'little', signed=False)
                                rebuildFileTemp += bool_bitmask

                        elif data['columnTypes2'][column] == 13: #Table
                            #Generate a dummy offset list and store the pointers. Write the subtables and update the dummy list with the right pointers
                                offset = len(rebuildFileTemp)
                                tableOffsets.append(offset)
                                dummy = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                                rebuildFileTemp += dummy
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                tables.append(value)


                rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))

        
        columnValueOffsetsOffset = len(rebuildFileTemp)
        for offset in columnValueOffsets:
            rebuildFileTemp += offset.to_bytes(4, 'little')
        
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x1C, 0x4, int(columnValueOffsetsOffset).to_bytes(4, 'little') ) #Add column content offset table pointer to the main table


    #Table value type
    for x in range(len(tables)):
        offset = int(len(rebuildFileTemp))
        importTable (tables[x])
        rebuildFileTemp = writeToPosition(rebuildFileTemp, tableOffsets[x], 0x8, offset.to_bytes(8, 'little') )


    #Row Index
    if jsonInfo['HAS_ROW_INDICES'] == True:
        rowIndexOffset = int(len(rebuildFileTemp))
        for row in range(jsonInfo['ROW_COUNT']):
            rebuildFileTemp += jsonInfo['ROW_CONTENT'][row]['reARMP_rowIndex'].to_bytes(4, 'little', signed=True)
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x30, 0x4, int(rowIndexOffset).to_bytes(4, 'little') ) #Add pointer to the main table


    #Column Index
    if jsonInfo['COLUMN_INDICES'] != None:
        columnIndexOffset = int(len(rebuildFileTemp))
        for index in jsonInfo['COLUMN_INDICES']:
            rebuildFileTemp += index.to_bytes(4, 'little', signed=True)
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x34, 0x4, int(columnIndexOffset).to_bytes(4, 'little') ) #Add pointer to the main table


    #Unknown Bitmask TODO
    if jsonInfo['HAS_UNKNOWN_BITMASK'] == True:
        bitmaskOffsetTable = []
        for column in range(0, jsonInfo['COLUMN_COUNT']):
            column_name = jsonInfo['COLUMN_NAMES'][column]
            if str(column_name+"_unknownBool") in jsonInfo['ROW_CONTENT'][0]: #Check entry 0 to look for bitmasks
                binary = ''
                pointerToColumnBitmask = len(rebuildFileTemp)
                for row in range(jsonInfo['ROW_COUNT']):
                    bit = jsonInfo['ROW_CONTENT'][row][column_name+"_unknownBool"]
                    if len(binary) < 8:
                        binary += bit
                    if len(binary) == 8:
                        binary = binary[::-1]
                        binary = int(binary, 2).to_bytes(1, 'little')
                        rebuildFileTemp += binary
                        binary = ''
                    if row == jsonInfo['ROW_COUNT']-1:
                        binary = binary.ljust(8, '0')
                        binary = binary[::-1]
                        binary = int(binary, 2).to_bytes(1, 'little')
                        rebuildFileTemp += binary
                bitmaskOffsetTable.append(pointerToColumnBitmask)
            else:
                bitmaskOffsetTable.append(0)

        rebuildFileTemp += b'\x00'*calculateSeparator(len(rebuildFileTemp)) #Padding
        pointerToBitmaskOffsetTable = len(rebuildFileTemp) 
        for offset in bitmaskOffsetTable:
            rebuildFileTemp += offset.to_bytes(4, 'little')

        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x44, 0x4, int(pointerToBitmaskOffsetTable).to_bytes(4, 'little') )
        rebuildFileTemp += b'\x00'*calculateSeparator(len(rebuildFileTemp)) #Padding


    #ValidityBool        
    if jsonInfo['HAS_VALIDITYBOOL'] == True:
        validityBoolOffset = len(rebuildFileTemp)
        for row in range(0, jsonInfo['ROW_COUNT']):
            binary = jsonInfo['ROW_CONTENT'][row]['reARMP_validityBool']
            binary = int(binary, 2).to_bytes(1, 'little')
            rebuildFileTemp += binary
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x4C, 0x4, int(validityBoolOffset).to_bytes(4, 'little') ) #Add pointer to the main table


    #subTable
    if "subTable" in data:
        offset = len(rebuildFileTemp)
        importTable (data['subTable'])
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x3C, 0x4, int(offset).to_bytes(4, 'little') ) #Add pointer to the main table




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

# -*- coding: utf-8 -*-
import binascii
import sys
import json
import math
import struct
import functools
from collections import OrderedDict

reARMP_version = "v0.11.1"
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



def getColumnValueTextTable (pointerToTable, numberOfEntries):
    table = hexFile[(pointerToTable*2):(pointerToTable + numberOfEntries*4)*2]
    table = [table[i:i+(4*2)] for i in range(0, len(table), (4*2))]
    return table



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



def getSpecialFieldIndices (pointerToTable):
    pointerToStart = readFromPosition(pointerToTable+4, 4, "<i")
    table = hexFile[(pointerToStart*2) : (pointerToTable*2)]
    tableLength = len([table[i:i+8] for i in range(0, len(table), 8)])
    returnList = iterateValueTable(pointerToStart, tableLength, "<i", 4)
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
    rowIndices = []
    columnIndices = []
    unknownOffsetTable = []
    unknownBitmask = []

    rowCount =                          readFromPosition (pointerToMainTable + 0x0, 0x4, "<i")
    columnCount =                       readFromPosition (pointerToMainTable + 0x4, 0x4, "<i")
    textCount =                         readFromPosition (pointerToMainTable + 0x8, 0x4, "<i")
    rowValidator =                      readFromPosition (pointerToMainTable + 0xC, 0x4, "<i")
    pointerToRowNamesOffsetTable =      readFromPosition (pointerToMainTable + 0x10, 0x4, "<i")
    pointerToRowValidity =              readFromPosition (pointerToMainTable + 0x14, 0x4, "<i")
    pointerToColumnDataTypes =          readFromPosition (pointerToMainTable + 0x18, 0x4, "<i")
    pointerToColumnContentOffsetTable = readFromPosition (pointerToMainTable + 0x1C, 0x4, "<i")
    tableID =                           readFromPosition (pointerToMainTable + 0x20, 0x2, "<h")
    pointerToTextOffsetTable =          readFromPosition (pointerToMainTable + 0x24, 0x4, "<i")
    pointerToColumnNamesOffsetTable =   readFromPosition (pointerToMainTable + 0x28, 0x4, "<i")
    columnValidator =                   readFromPosition (pointerToMainTable + 0x2C, 0x4, "<i")
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
    print ("Pointer to is_empty Bitmask Pointer Table: " + str(pointerToBitmaskOffsetTable))
    print ("Pointer to Auxiliary Column Data Types: " + str(pointerToColumnDataTypesAux))
    print ("Pointer to ValidityBool Array/Special Field Indices: " + str(pointerToValidityBool))
    print ("Row Validator: " + str(rowValidator))
    print ("Column Validator: " + str(columnValidator))
    print ("Table ID: " + str(tableID))


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


    #ValidityBool/Special Field Indices
    if (pointerToValidityBool != 0 and pointerToValidityBool != -1):
        if version == 1:
            validityBoolTable = iterateValidityBoolTable(pointerToValidityBool, rowCount)
        if version == 2:
            specialFieldIndices = getSpecialFieldIndices(pointerToValidityBool)
    else:
        if version == 1:
            validityBoolTable = None
        if version == 2:
            specialFieldIndices = None


    #Row validity
    if (pointerToRowValidity != -1) and (pointerToRowValidity != 0):
        row_validity = iterateBitmaskTable (pointerToRowValidity, rowCount)
        hasRowValidity = True
    else:
        row_validity = None
        hasRowValidity = False
        

    #Column validity
    if (pointerToColumnValidity != -1) and (pointerToColumnValidity != 0):
        hasColumnValidity = True
    else:
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
    exportDict["ROW_COUNT"] = rowCount
    exportDict["COLUMN_COUNT"] = columnCount
    exportDict["TEXT_COUNT"] = textCount
    exportDict["ROW_VALIDATOR"] = rowValidator
    exportDict["COLUMN_VALIDATOR"] = columnValidator
    exportDict["HAS_ROW_NAMES"] = hasRowNames
    exportDict["HAS_COLUMN_NAMES"] = hasColumnNames
    exportDict["HAS_ROW_VALIDITY"] = hasRowValidity
    exportDict["HAS_COLUMN_VALIDITY"] = hasColumnValidity
    exportDict["HAS_UNKNOWN_BITMASK"] = hasUnknownBitmask
    exportDict["HAS_ROW_INDICES"] = hasRowIndices
    exportDict["TABLE_ID"] = tableID
    if version == 2:
        exportDict["STORAGE_MODE"] = storageMode
        if specialFieldIndices is not None:
            exportDict["SPECIAL_FIELD_INDICES"] = specialFieldIndices
    exportDict.update ( getColumnInfo(pointerToColumnDataTypes, pointerToColumnDataTypesAux, pointerToColumnValidity, columnCount, columnNames) )
    if (len(columnIndices) > 0):
        exportDict["COLUMN_INDICES"] = columnIndices


    #Store Column values
    #FOTNS, 6 and K2
    if version == 1: 
        columnTypes = exportDict["columnTypes2"]

        valueSizes = {
            0 : 0x1, #uint8
            1 : 0x2, #uint16
            2 : 0x4, #uint32
            3 : 0x8, #uint64
            4 : 0x1, #int8
            5 : 0x2, #int16
            6 : 0x4, #int32
            7 : 0x8, #int64
            9 : 0x4, #float32
            13 : 0x8 #table
        }

        types = {
            0 : "B", #uint8
            1 : "H", #uint16
            2 : "I", #uint32
            3 : "Q", #uint64
            4 : "b", #int8
            5 : "h", #int16
            6 : "i", #int32
            7 : "q", #int64
            9 : "f", #float32
            13 : "q" #table
        }

        columnValues = {}
        for column in columnNames:
            column_index = columnNames.index(column)

            if (columnTypes[str(column)] == -1): #Skip unused columns
                emptyList = []
                columnValues[column] = emptyList
                continue

            if (columnTypes[str(column)] in [0,1,2,3,4,5,6,7,9,13]): #ints, floats and tables
                valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<" + types[columnTypes[str(column)]], valueSizes[columnTypes[str(column)]])
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == 11): #boolean
                valueTable = iterateBitmaskTable (columnContentOffsetTable[column_index], rowCount)
                columnValues[column] = valueTable
                continue

            if (columnTypes[str(column)] == 12): #String
                valueTable = getColumnValueTextTable (columnContentOffsetTable[column_index], rowCount)
                columnValues[column] = valueTable


        row_index = 0
        for row in rowNamesTable: #Element per row
            columnDict = OrderedDict() #Column contents
            columnDict[row] = {}


            for column in columnNames: #Iterate through each column
                column_index = columnNames.index(column)

                if (columnTypes[str(column)] == -1): #Skip unused columns
                    continue

                if len(unknownBitmask) > 0 and len(unknownBitmask[column_index]) > 0: #Unknown Bitmask
                    columnData = {str(column)+"_unknownBool" : unknownBitmask[column_index][row_index]}
                    columnDict[row].update(columnData)

                if (columnTypes[str(column)] != 12) and (columnTypes[str(column)] != 13) and (len(columnValues[column]) > 0) :
                    columnData = {str(column) : columnValues[column][row_index]}
                    columnDict[row].update(columnData)
                    continue

                if (columnTypes[str(column)] == 12): #String
                    index = columnValues[column][row_index]
                    if index == b'ffffffff':
                        index = -1
                    else:
                        index = swapEndian(index, "<I")

                    if (index == -1):
                        continue
                    columnData = {str(column) : textTable[index]}
                    columnDict[row].update(columnData)
                    continue

                if (columnTypes[str(column)] == 13): #Table
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



    #Judgment, Like a Dragon
    if version == 2: 
        columnTypes = exportDict["columnTypes"]
        arrays = [
            14, #uint8
            15, #uint16
            16, #uint32
            17, #uint64
            18, #int8
            19, #int16
            20, #int32
            21, #int64
            22, #string
            23, #table
            25, #float32
            26, #float64
            27, #vf128
            29 #bool
        ]

        if storageMode == 0: #TODO implement arrays

            valueSizes = {
                0 : 0x4, #uint32
                1 : 0x2, #uint16
                2 : 0x1, #uint8
                3 : 0x4, #int32
                4 : 0x2, #int16
                5 : 0x1, #int8
                7 : 0x4, #float32
                8 : 0x8, #uint64
                9 : 0x8, #table
                10 : 0x8, #int64
                11 : 0x8 #float64
            }

            types = {
                0 : "I", #uint32
                1 : "H", #uint16
                2 : "B", #uint8
                3 : "i", #int32
                4 : "h", #int16
                5 : "b", #int8
                7 : "f", #float32
                8 : "Q", #uint64
                9 : "q", #table
                10 : "q", #int64
                11 : "d" #float64
            }

            columnValues = {}
            for column in columnNames:
                column_index = columnNames.index(column)

                if (columnTypes[str(column)] == -1 or columnContentOffsetTable[column_index] == 0): #Skip unused columns
                    emptyList = []
                    columnValues[column] = emptyList
                    continue

                if (columnTypes[str(column)] in [0,1,2,3,4,5,7,8,9,10,11]): #ints, floats and tables
                    valueTable = iterateValueTable (columnContentOffsetTable[column_index], rowCount, "<" + types[columnTypes[str(column)]], valueSizes[columnTypes[str(column)]])
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == 6): #boolean
                    valueTable = iterateBitmaskTable (columnContentOffsetTable[column_index], rowCount)
                    columnValues[column] = valueTable
                    continue

                if (columnTypes[str(column)] == 13): #String
                    valueTable = getColumnValueTextTable (columnContentOffsetTable[column_index], rowCount)
                    columnValues[column] = valueTable


            row_index = 0
            for row in rowNamesTable: #Element per row
                columnDict = OrderedDict() #Column contents
                columnDict[row] = {}

                for column in columnNames: #Iterate through each column
                    column_index = columnNames.index(column)

                    if (columnTypes[str(column)] == -1): #Skip unused columns
                        continue

                    if len(unknownBitmask) > 0 and len(unknownBitmask[column_index]) > 0: #Unknown Bitmask
                        columnData = {str(column)+"_unknownBool" : unknownBitmask[column_index][row_index]}
                        columnDict[row].update(columnData)

                    if (columnTypes[str(column)] != 13) and (columnTypes[str(column)] != 9) and (len(columnValues[column]) > 0) :
                        columnData = {str(column) : columnValues[column][row_index]}
                        columnDict[row].update(columnData)
                        continue

                    if (columnTypes[str(column)] == 13): #String
                        index = columnValues[column][row_index]
                        index = swapEndian(index, "<I")

                        if (index == -1):
                            continue
                        columnData = {str(column) : textTable[index]}
                        columnDict[row].update(columnData)
                        continue

                    if (columnTypes[str(column)] == 9): #Table
                        pointer = columnValues[column][row_index]
                        if pointer != 0 and pointer != -1:
                            columnData = {str(column) : exportTable(pointer)}
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
                6 : 0x1, #bool
                7 : 0x4, #float32
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
                10 : "q", #64
                11 : "d" #float64
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

                        if columnTypes[column] == 13: #String
                            index = readFromPosition(offset + columnInfo[column_index][1], 4, "<i")
                            if (index == 0):
                                continue
                            columnData = {str(column) : textTable[index]}
                            columnDict[row].update(columnData)

                        if columnTypes[column] == 9: #Table
                            pointer = readFromPosition(offset + columnInfo[column_index][1], 4, "<I")
                            if pointer != 0 and pointer != -1:
                                columnData = {str(column) : exportTable(pointer)}
                                columnDict[row].update(columnData)

                        if columnTypes[column] in arrays: #Arrays
                            arrayLength = columnInfo[column_index][2]
                            columnData = {column : arrayLength}
                            columnDict[row].update(columnData)

                    else:
                        continue


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
    if 'SPECIAL_FIELD_INDICES' in data:
        special_field_indices = data['SPECIAL_FIELD_INDICES']
    else:
        special_field_indices = None
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
                if (version == 1 and data['columnTypes2'][column] == 12) or (version == 2 and data['columnTypes'][column] == 13):
                    if column in data[str(entry)][rowNames[entry]]:
                        string = data[str(entry)][rowNames[entry]][str(column)]
                        if string not in text:
                            text.append(string)
        if version == 2 and data['STORAGE_MODE'] == 1:
            text.insert(0, '')
    text_count = len(text)

    if row_count > 0:
        if 'reARMP_validityBool' in rowContent[0]:
            has_validitybool = True
        else:
            has_validitybool = False
    else:
        has_validitybool = False
    
    jsonInfo = {'ROW_COUNT' : row_count, 'COLUMN_COUNT' : column_count, 'TEXT_COUNT' : text_count, 'HAS_ROW_NAMES' : has_row_names, 'HAS_COLUMN_NAMES' : has_column_names, 'HAS_ROW_VALIDITY' : has_row_validity,
    'HAS_COLUMN_VALIDITY' : has_column_validity, 'HAS_ROW_INDICES' : has_row_indices, 'SPECIAL_FIELD_INDICES' : special_field_indices, 'COLUMN_INDICES' : column_indices, 'ROW_NAMES' : rowNames, 'COLUMN_NAMES' : columnNames, 'TEXT' : text, 'ROW_CONTENT' : rowContent,
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



def generateColumnDataTypesAuxTable (columnTypes, sizes, arraySizes):
    dataTypesAuxTable = b''
    distanceFromStart = 0

    auxTypes = {
        #Column types value : Aux table value
        0 : 2,
        1 : 3,
        2 : 4,
        3 : 6,
        4 : 7,
        5 : 8,
        6 : 4,
        7 : 10,
        8 : 1,
        9 : 13,
        10 : 5,
        11 : 9,
        13 : 12,
        14 : 14,
        15 : 15,
        16 : 16,
        17 : 17,
        18 : 18,
        19 : 19,
        20 : 20,
        21 : 21,
        22 : 25,
        23 : 26,
        25 : 23,
        26 : 24,
        27 : 27,
        29 : 29
    }

    for columnName, columnType in columnTypes.items():
        if columnType != -1:
            dataTypesAuxTable += auxTypes[columnType].to_bytes(4, 'little', signed=True) #Type
            dataTypesAuxTable += distanceFromStart.to_bytes(4, 'little', signed=True) #Distance from start
            distanceFromStart += sizes[columnType]
            if columnName in arraySizes: #Array Size
                dataTypesAuxTable += arraySizes[columnName].to_bytes(4, 'little', signed=True)
            else:
                dataTypesAuxTable += b'\x00\x00\x00\x00'
            dataTypesAuxTable += b'\x00\x00\x00\x00' #Unknown/Placeholder

        else:
            dataTypesAuxTable += b'\x00\x00\x00\x00'
            dataTypesAuxTable += b'\xFF\xFF\xFF\xFF'
            dataTypesAuxTable += b'\x00\x00\x00\x00'*2

    return dataTypesAuxTable



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
    rebuildFileTemp += b'\x00\x00\x00\x00'*20

    if version==2: #Different storage modes are only present in v2, STORAGE_MODE does not exist as a key on v1 because it is always 0
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x23, 0x1, int(data["STORAGE_MODE"]).to_bytes(1, 'little', signed=True) )
    rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0xC, 0x4, int(data["ROW_VALIDATOR"]).to_bytes(4, 'little', signed=True) )
    rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x2C, 0x4, int(data["COLUMN_VALIDATOR"]).to_bytes(4, 'little', signed=True) )
    rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x20, 0x2, int(data["TABLE_ID"]).to_bytes(2, 'little', signed=True) )

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
    else:
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x14, 0x4, b'\xFF\xFF\xFF\xFF' )


    #Column Validity
    if jsonInfo['HAS_COLUMN_VALIDITY'] == True:
        pointerToColumnValidity = len(rebuildFileTemp)
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
        
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x38, 0x4, int(pointerToColumnValidity).to_bytes(4, 'little') )
        rebuildFileTemp += b'\x00'*calculateSeparator(len(rebuildFileTemp)) #Padding
    else:
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x38, 0x4, b'\xFF\xFF\xFF\xFF' )


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


    #ColumnTypes
    columnTypes2Offset = len(rebuildFileTemp)
    for column in jsonInfo['COLUMN_NAMES']:
        rebuildFileTemp += data['columnTypes'][column].to_bytes(1, 'little', signed = True)
    rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
    rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x18, 0x4, int(columnTypes2Offset).to_bytes(4, 'little') ) #Add pointer to the main table


    #ColumnTypesAux
    if version == 1: #Only used in v1, for v2 we will create the Auxiliary table once values have been written
        columnTypesOffset = len(rebuildFileTemp)
        for column in jsonInfo['COLUMN_NAMES']:
            rebuildFileTemp +=  data['columnTypes2'][column].to_bytes(1, 'little', signed = True)
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x48, 0x4, int(columnTypesOffset).to_bytes(4, 'little') ) #Add pointer to the main table


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
    else:
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x24, 0x4, int(columnTypes2Offset).to_bytes(4, 'little'))


    #Column Values
    if version == 1:
        columnValueOffsets = []
        tableOffsets = [] #Table pointers
        tables = [] #Tables
        unusedColumns = {} #Used to check if a column goes unused even though being marked as valid

        sizes = {
            # "Type in table 2" : size
            0 : 0x1, #uint8
            1 : 0x2, #uint16
            2 : 0x4, #uint32
            3 : 0x8, #uint64
            4 : 0x1, #int8
            5 : 0x2, #int16
            6 : 0x4, #int32
            7 : 0x8, #int64
            9 : 0x4, #float32
            12 : 0x4, #string
            13 : 0x8, #table
        }

        signeds = {
            0 : False,
            1 : False,
            2 : False,
            3 : False,
            4 : True,
            5 : True,
            6 : True,
            7 : True
        }

        for column in jsonInfo['COLUMN_NAMES']:
            unusedColumns[column] = 0 #Set the unused counter to 0 to increase and compare later
            if jsonInfo['HAS_COLUMN_VALIDITY'] == True and data['columnValidity'][column] != "1":
                columnValueOffsets.append(0)
            else:
                columnValueOffsets.append(int(len(rebuildFileTemp)))

                bool_bitmask = '' #Initialize the bool bitmask in case there are boolean columns
                for row in range(0, jsonInfo['ROW_COUNT']):
                    if column not in jsonInfo['ROW_CONTENT'][row]: #This will generate trash in some cases (booleans marked as valid that go unused)
                        unusedColumns[column] += 1
                        if data['columnTypes2'][str(column)] == 13: 
                            rebuildFileTemp += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        else:
                            rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
                    else:
                        if data['columnTypes2'][column] in [0,1,2,3,4,5,6,7]: #No specials or floats
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            rebuildFileTemp += value.to_bytes(sizes[data['columnTypes2'][column]], 'little', signed = signeds[data['columnTypes2'][column]])
                     
                        elif data['columnTypes2'][column] == 9: #float32
                            value = jsonInfo['ROW_CONTENT'][row][column]
                            value = bytes(bytearray(struct.pack("<f", value)))
                            rebuildFileTemp += value

                        elif data['columnTypes2'][column] == 12: #String
                            index = jsonInfo['TEXT'].index(jsonInfo['ROW_CONTENT'][row][column])
                            rebuildFileTemp += index.to_bytes(sizes[data['columnTypes2'][column]], 'little')

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
                                dummy = b'\x00' * sizes[data['columnTypes2'][column]]
                                rebuildFileTemp += dummy
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                tables.append(value)


                rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))

        
        for column in unusedColumns:
            if unusedColumns[column] == jsonInfo['ROW_COUNT'] and data['columnTypes2'][column] == 11: #This only applies to booleans (?)
                columnValueOffsets[jsonInfo['COLUMN_NAMES'].index(column)] = -1

        columnValueOffsetsOffset = len(rebuildFileTemp)
        for offset in columnValueOffsets:
            rebuildFileTemp += offset.to_bytes(4, 'little', signed=True)
        
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x1C, 0x4, int(columnValueOffsetsOffset).to_bytes(4, 'little') ) #Add column content offset table pointer to the main table



    if version == 2:
        columnValueOffsets = []
        tableOffsets = [] #Table pointers
        tables = [] #Tables
        bool_bitmask = '' #Initialize the bool bitmask in case there are boolean columns
        
        arrays = [
            14, #uint8
            15, #uint16
            16, #uint32
            17, #uint64
            18, #int8
            19, #int16
            20, #int32
            21, #int64
            22, #string
            23, #table
            25, #float32
            26, #float64
            27, #vf128
            29 #bool
        ]

        sizes = {
            # "Type in table 1" : size
            0 : 0x4, #uint32
            1 : 0x2, #uint16
            2 : 0x1, #uint8
            3 : 0x4, #int32
            4 : 0x2, #int16
            5 : 0x1, #int8
            6 : 0x1, #bool
            7 : 0x4, #float32
            8 : 0x8, #uint64
            9 : 0x8, #table pointer
            10 : 0x8, #int64
            11 : 0x8, #float64
            13 : 0x8, #string pointer
            14 : 0x0, #uint8 array 
            15 : 0x0, #uint16 array 
            16 : 0x0, #uint32 array 
            17 : 0x0, #uint64 array 
            18 : 0x0, #uint8 array 
            19 : 0x0, #uint16 array 
            20 : 0x0, #uint32 array 
            21 : 0x0, #uint64 array 
            22 : 0x0, #string array 
            23 : 0x0, #table array 
            25 : 0x0, #float32 array 
            26 : 0x0, #float64 array 
            27 : 0x0, #vf128 
            29 : 0x0 #bool array 
        }

        signeds = {
            0 : False,
            1 : False,
            2 : False,
            3 : True,
            4 : True,
            5 : True,
            6 : False,
            8 : False,
            10 : True
        }

        arraySizes = {} #Column name : size (value)

        if data['STORAGE_MODE'] == 0:
            unusedColumns = {} #Used to check if a column goes unused even though being marked as valid
            for column in jsonInfo['COLUMN_NAMES']:
                unusedColumns[column] = 0 #Set the unused counter to 0 to increase and compare later
                if jsonInfo['HAS_COLUMN_VALIDITY'] == True and data['columnValidity'][column] != "1":
                    columnValueOffsets.append(0)
                else:
                    columnValueOffsets.append(int(len(rebuildFileTemp)))

                    bool_bitmask = '' #Initialize the bool bitmask in case there are boolean columns
                    for row in range(0, jsonInfo['ROW_COUNT']):
                        if column not in jsonInfo['ROW_CONTENT'][row]: #This will generate trash in some cases (booleans marked as valid that go unused)
                            unusedColumns[column] += 1
                            if data['columnTypes'][str(column)] == 9:
                                rebuildFileTemp += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                            else:
                                rebuildFileTemp += b'\xFF\xFF\xFF\xFF'
                        else:
                            if data['columnTypes'][column] in [0,1,2,3,4,5,8,10]: #No specials or floats
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                rebuildFileTemp += value.to_bytes(sizes[data['columnTypes'][column]], 'little', signed = signeds[data['columnTypes'][column]])

                            elif data['columnTypes'][column] == 7: #float32
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                value = bytes(bytearray(struct.pack("<f", value)))
                                rebuildFileTemp += value

                            elif data['columnTypes'][column] == 11: #float64
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                value = bytes(bytearray(struct.pack("<d", value)))
                                rebuildFileTemp += value

                            elif data['columnTypes'][column] == 13: #String
                                index = jsonInfo['TEXT'].index(jsonInfo['ROW_CONTENT'][row][column])
                                rebuildFileTemp += index.to_bytes(4, 'little')

                            elif data['columnTypes'][column] == 6: #Boolean
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

                            elif data['columnTypes'][column] == 9: #Table
                                #Generate a dummy offset list and store the pointers. Write the subtables and update the dummy list with the right pointers
                                    offset = len(rebuildFileTemp)
                                    tableOffsets.append(offset)
                                    dummy = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                                    rebuildFileTemp += dummy
                                    value = jsonInfo['ROW_CONTENT'][row][column]
                                    tables.append(value)


                    rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))

            
            for column in unusedColumns:
                if unusedColumns[column] == jsonInfo['ROW_COUNT'] and data['columnTypes'][column] == 6: #This only applies to booleans (?)
                    columnValueOffsets[jsonInfo['COLUMN_NAMES'].index(column)] = 0

            columnValueOffsetsOffset = len(rebuildFileTemp)
            for offset in columnValueOffsets:
                rebuildFileTemp += offset.to_bytes(4, 'little', signed=True)
            
            rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x1C, 0x4, int(columnValueOffsetsOffset).to_bytes(4, 'little') ) #Add column content offset table pointer to the main table


        if data['STORAGE_MODE'] == 1:
            for row in range(jsonInfo['ROW_COUNT']):
                rebuildFileTemp += b'\x00' * (16 - (len(rebuildFileTemp)%16)) #Pad to 16 bytes
                columnValueOffsets.append(int(len(rebuildFileTemp)))

                for column in jsonInfo['COLUMN_NAMES']:
                    if column not in jsonInfo['ROW_CONTENT'][row]:
                        if data['columnTypes'][str(column)] == 13: 
                            rebuildFileTemp += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        if data['columnTypes'][str(column)] == 9: 
                            rebuildFileTemp += b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    else:
                        if jsonInfo['HAS_COLUMN_VALIDITY'] == True and data['columnValidity'][column] != "1":
                            continue
                        else:
                            if data['columnTypes'][column] in [0,1,2,3,4,5,6,8,10]: #No specials or floats
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                rebuildFileTemp += value.to_bytes(sizes[data['columnTypes'][column]], 'little', signed = signeds[data['columnTypes'][column]])

                            elif data['columnTypes'][column] == 7: #float32
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                value = bytes(bytearray(struct.pack("<f", value)))
                                rebuildFileTemp += value

                            elif data['columnTypes'][column] == 11: #float64
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                value = bytes(bytearray(struct.pack("<d", value)))
                                rebuildFileTemp += value

                            elif data['columnTypes'][column] == 13: #String
                                index = jsonInfo['TEXT'].index(jsonInfo['ROW_CONTENT'][row][column])
                                rebuildFileTemp += index.to_bytes(8, 'little', signed=True)

                            elif data['columnTypes'][column] == 9: #Table
                            #Generate a dummy offset list and store the pointers. Write the subtables and update the dummy list with the right pointers
                                offset = len(rebuildFileTemp)
                                tableOffsets.append(offset)
                                dummy = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                                rebuildFileTemp += dummy
                                value = jsonInfo['ROW_CONTENT'][row][column]
                                tables.append(value)

                            elif data['columnTypes'][column] in arrays:
                                arraySize = jsonInfo['ROW_CONTENT'][row][column]
                                arraySizes[str(column)] = arraySize
                    

            dataTypesAuxTable = generateColumnDataTypesAuxTable(data['columnTypes'], sizes, arraySizes)


            rebuildFileTemp += b'\x00'*calculateSeparator(len(rebuildFileTemp))
            columnValueOffsetsOffset = len(rebuildFileTemp)
            for offset in columnValueOffsets:
                rebuildFileTemp += offset.to_bytes(4, 'little', signed=True)

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
    if version == 1 and jsonInfo['HAS_VALIDITYBOOL'] == True:
        validityBoolOffset = len(rebuildFileTemp)
        for row in range(0, jsonInfo['ROW_COUNT']):
            binary = jsonInfo['ROW_CONTENT'][row]['reARMP_validityBool']
            binary = int(binary, 2).to_bytes(1, 'little')
            rebuildFileTemp += binary
        rebuildFileTemp += b'\x00' * calculateSeparator(len(rebuildFileTemp))
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x4C, 0x4, int(validityBoolOffset).to_bytes(4, 'little') ) #Add pointer to the main table


    #V2 Column Types Aux Table
    if version == 2 and 'dataTypesAuxTable' in locals():
        rebuildFileTemp += b'\x00' * (16 - (len(rebuildFileTemp)%16)) #Pad to 16 bytes
        pointer = int(len(rebuildFileTemp))
        rebuildFileTemp += dataTypesAuxTable
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x48, 0x4, int(pointer).to_bytes(4, 'little') ) #Add pointer to the main table


    #Special Field Indices
    if version == 2 and jsonInfo['SPECIAL_FIELD_INDICES'] != None:
        sizeList = []
        specialIndexList = jsonInfo['SPECIAL_FIELD_INDICES']

        for column in jsonInfo['COLUMN_NAMES']:
            if data['columnTypes'][column] in [14,15,16,17,18,19,20,21,22,23,25,26,27,29]:
                sizeList.append(data['0'][''][str(column)])
            else:
                sizeList.append(0)

        nextPointer = int(len(rebuildFileTemp))
        for index in specialIndexList:
            rebuildFileTemp += index.to_bytes(4, 'little')
        rebuildFileTemp += b'\x00' * (16 - (len(rebuildFileTemp)%16)) #Pad to 16 bytes
        pointer = int(len(rebuildFileTemp))

        for index in range(jsonInfo['COLUMN_COUNT']):
            rebuildFileTemp += sizeList[index].to_bytes(4, 'little')
            rebuildFileTemp += nextPointer.to_bytes(4, 'little')
            rebuildFileTemp += b'\x00\x00\x00\x00'*6 #Unknown/Padding?
            if sizeList[index] > 0:
                nextPointer = nextPointer + 4*sizeList[index]

        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x4C, 0x4, int(pointer).to_bytes(4, 'little') ) #Add pointer to the main table


    #subTable
    if "subTable" in data:
        pointer = int(len(rebuildFileTemp))
        importTable (data['subTable'])
        rebuildFileTemp = writeToPosition(rebuildFileTemp, pointerToMainTable + 0x3C, 0x4, int(pointer).to_bytes(4, 'little') ) #Add pointer to the main table



def showBanner():
    print(r'''
                       _____   __  __  _____  
                /\    |  __ \ |  \/  ||  __ \ 
  _ __  ___    /  \   | |__) || \  / || |__) |
 | '__|/ _ \  / /\ \  |  _  / | |\/| ||  ___/ 
 | |  |  __/ / ____ \ | | \ \ | |  | || |     
 |_|   \___|/_/    \_\|_|  \_\|_|  |_||_|     ''' + reARMP_version + '\n\n')

showBanner()
if (len(sys.argv) <= 1):
    print ("Usage: reARMP <file>")
    print ("You can also drag & drop!\n")
    input("Press ENTER to exit... ")
    sys.exit
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

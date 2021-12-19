import time
import threading

#levels
LOGL_DEBUG = 0
LOGL_VERBOSE = 1
LOGL_NORMAL = 2
LOGL_INF = 99

#parameters
loglevel = LOGL_DEBUG

class Segment:
    def __init__(self,address):
        self.address = address
        self.data = b""

    def append(self, data):
        self.data += data

    def truncate(self):
        data = self.data[0]
        self.data = self.data[1:]
        self.address +=1
        return data

    def getlength(self):
        return len(self.data)

    def getsegmentend(self):
        return self.address +len(self.data)-1

    def prepend(self,data):
        self.data[:0] = data

    def newsegment(self,address):
        return self.getsegmentend()+1 != address

class Memory:
    def __init__(self):
        self.segments=[]
        self.currentseg= None

    def adddata(self, data, address):
        if self.currentseg == None or self.currentseg.newsegment(address):
            # try to find a segment to continue
            self.currentseg = None
            for segment in self.segments:
                if segment.getsegmentend()+1 == address:
                    self.currentseg = segment

            # if no segment has been found to continue
            if self.currentseg == None:
                self.currentseg = Segment(address)
                self.segments.append(self.currentseg)

        self.currentseg.append(data)
    def gettotalbytes(self):
        total = 0
        for s in self.segments:
            total +=len(s.data)
        return total


    # this function realigns segments and their length on the 2 byte boundary
    # even though depending on the page size, these can be cut again, generally only words can be written into D-Flash
    def align(self):
        self.sortsegments()
        previous = None
        length = len(self.segments)
        for idx in range(length):
            segment = self.segments[idx]
            if segment.address%2!= 0:
                segment.address -=1
                segment.prepend(b"\xFF")

            if segment.getsegmentend()%2 == 0:
                if (idx+1)<length:
                    nextsegment = self.segments[idx+1]
                    if nextsegment.address  == segment.getsegmentend()+1:
                        segment.append([nextsegment.truncate()])
                    else:
                        segment.append(b"\xFF")
                else:
                    segment.append(b"\xFF")
            previous = segment

    def splitsegment(self,idx,endaddress):
        segment = self.segments[idx]
        restofdata = segment.data[endaddress-segment.address:]
        segment.data = segment.data[:endaddress-segment.address]

        newsegment = Segment(endaddress+1)
        newsegment.data = restofdata

    def sortsegments(self):
        def sortcondition(elem):
            return elem.address
        self.segments.sort(key=sortcondition)

    def printmemory(self):
        for s in self.segments:
            segment = [s.address,s.data]
            log(segment,conv="mem",level=LOGL_DEBUG)

    def printsegments(self):
        for segment in self.segments:
            log("Address:%010X-%010X Bytes:%d"%(segment.address, segment.getsegmentend(),len(segment.data)))

    def alignmemory(self):
        log("Loaded Image: %d Bytes %d Segments"%(self.gettotalbytes(),len(self.segments)),level=LOGL_VERBOSE)
        self.align()
        log("Aligned Image: %d Bytes %d Segments"%(self.gettotalbytes(),len(self.segments)),level=LOGL_VERBOSE)


def comparepagetosegments(segmentlist,pagememory,startaddress,endaddress,errorQueue):
    previousstart = 0

    try:
        for segment in segmentlist:
            start = segment.address-startaddress
            end = start+segment.getlength()

            # Check ff's
            while previousstart != start:
                if pagememory[previousstart:previousstart+2] != b"\xff\xff":
                    errorQueue.put((previousstart,  b"\xff\xff",pagememory[previousstart:previousstart+2]))
                previousstart +=2;

            # Check data
            while previousstart != end:
                if pagememory[previousstart:previousstart+2] != segment.data[previousstart-start:previousstart-start+2]:
                    errorQueue.put((segment.address+previousstart, segment.data[previousstart-start:previousstart-start+2],pagememory[previousstart:previousstart+2]))
                previousstart +=2;



        # Check ff's
        end = len(pagememory)
        while previousstart < end:
            if pagememory[previousstart:previousstart+2] != b"\xff\xff":
                errorQueue.put((previousstart,  b"\xff\xff",pagememory[previousstart:previousstart+2]))
            previousstart +=2;
        ''''''
    except Exception as e:
        log(e)


def comparememorytosegment(segment, pagememory, errorQueue):
    checked = 0
    end = segment.getlength()
    while checked != end:
        if pagememory[checked:checked+2] != segment.data[checked:checked+2]:
            errorQueue.put((segment.address+checked, segment.data[checked:checked+2],pagememory[checked:checked+2]))
        checked +=2;

# logger
def log(data, level=0, debugline="",conv="",tag=""):
    if loglevel<=level:
        if conv == "hex":
            if type(data) is int:
                print("log(%d):%s#%s%s"%(level, tag, debugline, hex(data)))
            else:
                print("log(%d):%s#%s%s"%(level, tag, debugline, ''.join('{:02x}'.format(x) for x in data)))

        elif conv == "mem":
            address = data[0]
            memory = data[1]
            length = len(memory)
            tidx = 0
            while tidx != length:
                idx = 0
                print("log(%d):%s#%s%08X\t  "%(level,tag, debugline, address),end="")
                while idx <16 and  idx + tidx < length:
                    if type(memory[idx+tidx]) is int:
                        print("%02X "%(memory[idx+tidx]),end="")
                    else:
                        print("%02X "%(int.from_bytes(memory[idx+tidx],byteorder="big")),end="")
                    idx = idx + 1
                print("")
                address = address + idx
                tidx = tidx + idx

        else:
            print("log(%d):%s#%s%s"%(level, tag,debugline,str(data)))

def setlogginglevel(level):
    global loglevel
    loglevel = level

def gets19data(record, realchecksum):
    checksum = 0
    idx = 0
    length = len(record)
    data = b""
    while idx<length:
        bval = int(record[idx:idx+2],16)&0x000000FF
        checksum += bval
        data += bval.to_bytes(1,"big")
        idx +=  2

    checksum = ((~checksum) &0x000000FF)
    if checksum != realchecksum:
        raise ValueError("Error: S19 wrong checksum")
    return data[1:]

def loadprogramfile(fname):
    memory = None
    format = fname.split(".")
    format = format[len(format)-1]

    # https://en.wikipedia.org/wiki/SREC_(file_format)
    if format == "s19":
        flagstart = 0
        with open(fname, "rb") as fin:
            lines = fin.readlines()
            memory = Memory()
            for line in lines:
                line = line.strip()
                recordfield = line[0:2]
                recordlength= int(line[2:4],16) &0x00000000FF
                readlength = int((len(line)-4)/2)

                if(readlength!= recordlength or recordlength <4):
                    raise ValueError("Error: S19 wrong record length")

                record = line[2:len(line)-2]
                checksum = line[len(line)-2:]
                datarecord = gets19data(record,int(checksum,16) &0x0000FFFF)

                # Header
                if recordfield == b"S0":
                    flagstart = 1
                    log("S19 starting record: %s" %record, level=LOGL_VERBOSE)
                elif flagstart == 1:
                    # 16-bit address data
                    if recordfield == b"S1":
                        memory.adddata(datarecord[2:], int.from_bytes(datarecord[0:2],byteorder="big", signed=False))
                    # 24-bit address data
                    elif recordfield == b"S2":
                        memory.adddata(datarecord[3:], int.from_bytes(datarecord[0:3], byteorder="big",signed=False))
                    # 32-bit address data
                    elif recordfield == b"S3":
                        memory.adddata(datarecord[4:], int.from_bytes(datarecord[0:4],byteorder="big", signed=False))
                    # reserved
                    elif recordfield == b"S4":
                        pass
                    # 16-bit count
                    elif recordfield == b"S5":
                        pass
                    # 24-bit count
                    elif recordfield == b"S6":
                        pass
                    # 32-bit address termination
                    elif recordfield == b"S7":
                        pass
                    # 24-bit address termination
                    elif recordfield == b"S8":
                        pass
                    # 16-bit address termination
                    elif recordfield == b"S9":
                        pass
                    else:
                        raise ValueError('Error: S19 bad format')
            memory.printmemory()
            memory.alignmemory()
            memory.printsegments()

    elif format == "hex":
         raise ValueError('Error: hex not implemented')
    elif format == "bin":
         raise ValueError('Error: bin not implemented')     # can only split into correct segments, when the page size is known
    return memory

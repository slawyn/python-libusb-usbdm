from helpers import *

# Routines here are used by all chip types
# Override the routines to specify behavior
class ChipInterface():
    NAME = "STUB"
    def __init__(self,usbdm, target, pages, idlocation,ids):
        self.usbdm = usbdm                  # usbdm handle
        self.target = target                # HCS12 = 0x00 HCS08 = 0x01
        self.ChipPages = pages              # memory pages of the chip flash
        self.ChipAddressId = idlocation     # id address
        self.ChipIds = ids                  # ids for identification of the chip
        self.memory = []                    # file contents
        self.memorypages = {}               # page assignemts

        # Open Target
        self.usbdm.setBdmTarget(self.target)
        log("Opening %s for target %s ..."%(self.usbdm.NAME, self.NAME),level=LOGL_NORMAL,tag = self.NAME)
        if not self.usbdm.openBdm():
            log("Opened %s device"%(self.usbdm.NAME),level=LOGL_NORMAL,tag =  self.NAME)
        else:
            log("Couldn't open %s device"%self.usbdm.NAME, level=LOGL_NORMAL,tag =  self.NAME)

    # Reattaching doesn't really work, idea is to use it to reclaim a lost interface
    def reattach(self):
        log("Reattaching usbcore",level=LOGL_NORMAL)
        return self.usbdm.reattach()

    def halt(self):
        log("Halting processor",level=LOGL_VERBOSE,tag = self.NAME)
        return self.usbdm.haltTarget()

    def disconnect(self):
        log("Disconnecting target",level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.closeBdm()

    def connect(self):
        status = 0
        self.reset()
        if not self.usbdm.connect():
            log("Connected to %s"%(self.NAME),level=LOGL_NORMAL,tag = self.NAME)
            self.setup()
        else:
            log("Couldn't connect to %s"%(self.NAME),level=LOGL_NORMAL,tag = self.NAME)
            status = 1

    def program(self):
        log("STUB-program",level=LOGL_INF)

    def setup(self):
        log("STUB-setup",level=LOGL_INF)

    def unsecure(self):
        log("STUB-unsecure",level=LOGL_INF)

    def verify(self):
        log("STUB-verify",level=LOGL_INF)

    def reset(self):
        log("Resetting device", level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.resetTarget()

    def writememory(self, address, data):
        size = len(data)
        log("Writing Memory %8X %d"%(address,size),level=LOGL_VERBOSE, tag = self.NAME)
        off = 0
        while(size>0):
            if size > 0x88:
                result = self.usbdm.writeBdmBlock(address,data[off:off+0x88])
            else:
                result = self.usbdm.writeBdmBlock(address,data[off:off+size])

            off = off + 0x88
            size = size - 0x88
            address = address + 0x88

    def readmemory(self, address, size):
        log("Reading Memory",level=LOGL_VERBOSE, tag = self.NAME)
        memory = []
        while(size>0):
            if size > 0x90:
                result = self.usbdm.readBdmBlock(address,0x90)
            else:
                result = self.usbdm.readBdmBlock(address,size)

            if not result[0]:
                log((address,result[1:]),level=LOGL_VERBOSE, conv="mem", tag = self.NAME)
            else:
                 raise ValueError("Error while reading memory")

            memory.extend(result[1:])
            size = size - 0x90
            address = address + 0x90
        return bytes(memory)

    def close(self):
        log("Closing target...",level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.closeBdm()

    # This routine loads memory and assigns the segments to the corresponding pages
    def load(self, fname):
        log("Loading file %s"%fname,level=LOGL_NORMAL,tag = self.NAME)
        self.memory = loadprogramfile(fname)
        self.memorypages = {}
        for pgaddr in self.ChipPages:
            self.memorypages[pgaddr] = []

        splitneeded = False
        # check which segments need to be written to
        for pgaddr in self.ChipPages:
            pagestart = self.ChipPages[pgaddr][0]
            pageend = self.ChipPages[pgaddr][1]
            contains = 0

            length = len(self.memory.segments)
            idx = 0
            while idx<length:
                segment = self.memory.segments[idx]
                if pagestart<=segment.address and segment.address<=pageend:
                    if segment.getsegmentend()<=pageend:
                        self.memorypages[pgaddr].append(segment)
                    else:
                        splitneeded = True
                        self.memorypages[pgaddr].append(self.memory.splitsegment(idx,pageend))
                        length = len(self.memory.segments)
                        break
                idx +=1
        if splitneeded:
            log("Segments after split",level=LOGL_VERBOSE, tag = self.NAME)
            self.memory.printsegments()


        assignedsegments = 0
        for pgaddr in self.memorypages:
            assignedsegments +=len(self.memorypages[pgaddr])
            log("Page %x contains %d segments"%(pgaddr, len(self.memorypages[pgaddr])),level=LOGL_NORMAL, tag = self.NAME)

        if assignedsegments != len(self.memory.segments):
            raise ValueError("Error: some of the segments were not assigned")
        else:
            log("All Segments were assigned",level=LOGL_VERBOSE, tag = self.NAME)


    def identify(self):
        found = ""
        result = self.readmemory(self.ChipAddressId,2)
        if len(result)>0:
            if int.from_bytes(result[0:],"big") in self.ChipIds:
                found = self.NAME
        else:
            log("Failed to read memory %s"%self.NAME,level=LOGL_NORMAL, tag = self.NAME)

        return found

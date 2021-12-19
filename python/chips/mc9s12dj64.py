from helpers import *
from usbdm import*
from chips.chipinterface import ChipInterface
import threading
from queue import Queue

# Note: DJ64-Flash can only write word-length
# Chip standard clock is 8 Mhz
class MC9S12DJ64(ChipInterface):
    NAME = "MC9S12DJ64"
    ADDRESS_MAPPED_PAGE = 0x8000
    ADDRESS_SECURITY = 0xFF0E

    RAM_START = 0x4000
    RAM_END   = 0x5000
    PAGE_LENGTH = 0x4000
    VALUE_SECURITY_UNSECURE = 0xFFFE
    VALUE_SECURITY_SECURE = 0xFFFF

    REG_PAGE_MAP= 0x00000030
    REG_FCLKDIV = 0x00000100
    REG_FSEC    = 0x00000101
    REG_FCNFG   = 0x00000103
    REG_FPROT   = 0x00000104
    REG_FSTAT   = 0x00000105
    REG_FCMD    = 0x00000106

    REG_MODE    = 0x0000000B
    REG_INITRM  = 0x00000010
    REG_INITRG  = 0x00000011
    REG_INITEE  = 0x00000012

    REG_ECLKDIV = 0x00000110
    REG_ECNFG   = 0x00000113
    REG_EPROT   = 0x00000114
    REG_ESTAT   = 0x00000115
    REG_ECMD    = 0x00000116

    BITS_FSTAT_ACCER = 0x10
    BITS_FSTAT_CCIF  = 0x40
    BITS_FSTAT_CBEIF = 0x80
    BITS_FSTAT_RESET = 0xFF
    BITS_FSTAT_BLANK = 0x04

    BITS_ESTAT_ACCER = BITS_FSTAT_ACCER
    BITS_ESTAT_CCIF  = BITS_FSTAT_CCIF
    BITS_ESTAT_CBEIF = BITS_FSTAT_CBEIF
    BITS_ESTAT_RESET = BITS_FSTAT_RESET
    BITS_ESTAT_BLANK = BITS_FSTAT_BLANK

    CMD_BLANK          = 0x05
    CMD_PROGRAM        = 0x20
    CMD_ERASE_SECTOR   = 0x40
    CMD_ERASE_PAGE     = 0x41

    def __init__(self,usbdm):
        ChipInterface.__init__(self, usbdm, 0x00, {0x3E:[0x4000,0x7FFF], 0x3F:[0xC000,0xFFFF], 0x3C:[0x3C8000,0x3CBFFF], 0x3D:[0x3D8000,0x3DBFFF]}, 0x1A, [0x0200, 0x0201, 0x0202, 0x0203, 0x0204])

        # Note: postbytes X=0x00 Y=0x40 SP= 0x80
        # D = counter X = source Y = destination S = value16
        # VAR16_DESTINATION          #-6 dest
        # VAR16_TO_FLASH             #-4 size
        # VAR16_FLASHED              #-2 flashed
        # \xce\x40\x60\              #+3 ldx # load source 4060
        # \xfd\x40\x00\              #+6 ldy # load destination
        # \xcc\x00\x00               #+9 ldd 0
        # \xef\x00                   #+11 lds D, X
        # \x6f\x40                   #+13 sts D, Y
        # \x18\x0b\x20\x01\x06       #+18 movb #20, $0x106
        # \x18\x0b\x80\x01\x05       #+23 movb #80, $0x105
        # \1f\x01\x05\x40\xfb        #+28 loop if CBIF clear in %105
        # \xc3\x00\x02               #+31 addd 2
        # \x08\x08\x02\x02           #+35 inx 2 iny 2
        # \xbc\x40\x02               #+38 cmp D $4002
        # \x26\xe1                   #+40 bne to start
        # \x7c\x40\x04               #+43 std $4002
        # \x2a\xfe"                  #+45 loop
        self.bootloader =  [b"\xce\x40\x60",\
                            b"\xfd\x40\x00",\
                            b"\xcc\x00\x00",\
                            b"\xef\x00",\
                            b"\x6f\x40",\
                            b"\x18\x0b\x20\x01\x06",\
                            b"\x18\x0b\x80\x01\x05",\
                            b"\x1f\x01\x05\x40\xfb",\
                            b"\xc3\x00\x02",\
                            b"\x08\x08\x02\x02",\
                            b"\xbc\x40\x02",\
                            b"\x26\xe1",\
                            b"\x7c\x40\x04",\
                            b"\x2a\xfe"]

        self.usebootloader = True

    def unsecure(self):
        log("Unsecuring chip by mass erase",level=LOGL_NORMAL,tag = self.NAME)
        self.setup()

        log("Erasing EEPROM",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmWord(0x118,0x7ff0) #EADDR HI
        self.usbdm.writeBdmWord(0x11a,0xffff) #EDATA HI
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_ECMD, MC9S12DJ64.CMD_ERASE_PAGE)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_ESTAT, MC9S12DJ64.BITS_ESTAT_CBEIF)
        self.waitForEEPROM()
        # write 115 30
        # write 115 02
        # write 118 7ff0
        # write 11a ffff
        # write 116 41
        # write 115 80
        #

        log("Erasing Flash",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmWord(0x108,0x7ff0) #EADDR HI
        self.usbdm.writeBdmWord(0x10a,0xffff) #EDATA HI
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCMD, MC9S12DJ64.CMD_ERASE_PAGE)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FSTAT, MC9S12DJ64.BITS_FSTAT_CBEIF)
        self.waitForFlash()
        # write 105 30
        # write 102 00
        # write 105 02
        # write 102 10
        # write 108 7ff0
        # write 10a ffff
        # write 106 41
        # write 105 80
        #self.reset()

    def setup(self):
        log("Setting up registers and flash access",level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_MODE, 0xe0)      # Single mode
        self.usbdm.writeBdmByte(0x3C, 0x40)                     # Stop watchdog
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_INITRM, 0x40)    # map the ram at 0x4000
        #self.usbdm.writeBdmByte(MC9S12DJ64.REG_INITRG, 0x18)   # Map registers to 0x1800 - 0x1FFF ?

        self.usbdm.writeBdmByte(0x13, 0x03)                     #Misc
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCNFG, 0x00)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FPROT, 0xFF)

        '''
        # This can be used to check if the external clock is working properly
        log("Setting up PLL",level=LOGL_VERBOSE,tag = self.NAME)

        ## Configure PLL to 24 Mhz -> 12 Mhz Bus Clock, External Crystal(8 Mhz) as Source
        self.usbdm.writeBdmByte(0x034, 0x02)
        self.usbdm.writeBdmByte(0x035, 0x01)
        self.usbdm.writeBdmByte(0x039, 0x00)
        self.usbdm.writeBdmByte(0x03A, 0xD1)

        ## Read status  till PLL ready
        timeout = time.time()*1000  + 5000 # 5 seconds
        while self.usbdm.readBdmByte(0x37)[1] & 0x08 == 0x00:
            if time.time()*1000>timeout:
                raise ValueError("Error:Could not setup PLL")

        ## Switch clock Source
        self.usbdm.writeBdmByte(0x039, 0x80)

        log("Setting up Flash",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCLKDIV, 0x44)  # FCLK DIV. 12Mhz /(0x44 + 1) for approx. 175 Khz, normally without pll 0x2a would work
        '''
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCLKDIV, 0x29)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FSTAT, 0xFF)    # Reset FSTAT

        log("Setting up EEPROM",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_ECLKDIV, 0x29)  # ECLK
        #self.usbdm.writeBdmByte(MC9S12DJ64.REG_ECLKDIV, 0x44)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_ESTAT,   0xff)  # EPROT
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_INITEE,  0x01)  # Enable EEPROM

    # Need to connect to program
    def program(self):
        start = time.time()
        if self.memory.gettotalbytes()>0:
            # if can't connect, then we need to unsecure the flash by erasing it's contents
            retries = 0
            while retries <=3:
                if retries >= 3:
                    raise ValueError("Error: Could not prepare flash for programming")
                elif self.connect():
                    self.unsecure()
                    self.erase()
                    retries +=1
                elif self.blankcheck():
                    self.unsecure()
                    self.erase()
                    retries +=1
                else:
                    self.flash()
                    self.verify()
                    break

        log("time: %s s"%str(time.time()-start), level=LOGL_NORMAL,tag = self.NAME)

    # Flash
    def flash(self):
        if self.usebootloader:
            log("Loading bootloader into RAM",level=LOGL_VERBOSE,tag = self.NAME)
            self.halt()
            self.writememory(MC9S12DJ64.RAM_START+6, b"".join(self.bootloader))

            pagenumbers = list(self.ChipPages.keys())  # are the keys
            for pageaddress in pagenumbers:
                if len(self.memorypages[pageaddress]) == 0:
                    log("Skipping Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
                else:
                    log("Flashing Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
                    pagestart = self.ChipPages[pageaddress][0]
                    pageend = self.ChipPages[pageaddress][1]
                    self.usbdm.writeBdmByte(MC9S12DJ64.REG_PAGE_MAP, pageaddress)

                    # Flash segments for current page
                    for segment in self.memorypages[pageaddress]:
                        written = 0
                        dataleft = segment.getlength()
                        memorystart = segment.address-pagestart
                        maxspace = MC9S12DJ64.RAM_END - (MC9S12DJ64.RAM_START+0x60) # minus the size of the bootloader + some bytes
                        offset = segment

                        # Write in small batches, because ram is only 1k
                        while dataleft > 0:
                            sztowrite = 0
                            if dataleft>maxspace:
                                sztowrite = maxspace
                            else:
                                sztowrite = dataleft

                            log("Flashing %d Bytes, Address: %x "%(sztowrite,MC9S12DJ64.ADDRESS_MAPPED_PAGE + memorystart + written), level=LOGL_VERBOSE,tag = self.NAME)
                            self.writememory(MC9S12DJ64.RAM_START+0x60,segment.data[written:written+sztowrite])

                            fcondition = sztowrite.to_bytes(2,"big")
                            self.usbdm.writeBdmWord(MC9S12DJ64.RAM_START, MC9S12DJ64.ADDRESS_MAPPED_PAGE + memorystart + written)
                            self.usbdm.writeBdmWord(MC9S12DJ64.RAM_START+2, fcondition)
                            self.usbdm.writeBdmWord(MC9S12DJ64.RAM_START+4, 0)


                            log("Executing bootloader ", level=LOGL_VERBOSE,tag = self.NAME)
                            self.usbdm.writeRegister(0x03, MC9S12DJ64.RAM_START+6)   # set PC Counter
                            self.usbdm.runTarget()               # execute boot loader
                            timeout = time.time() * 1000  + 5000
                            while True:
                                if time.time()*1000<timeout:
                                    mem = self.usbdm.readBdmBlock(MC9S12DJ64.RAM_START+4,2)
                                    #self.readmemory(0x4000, 50)
                                    if bytes(mem[1:]) == fcondition:
                                        break
                                else:
                                    raise ValueError("Error: flashing timed out")

                            log("Halting bootloader ", level=LOGL_VERBOSE,tag = self.NAME)
                            self.usbdm.haltTarget()
                            written = written + sztowrite
                            dataleft = dataleft - sztowrite

        else:
            # Note: writing 2 bytes over usb and then waiting for FSTAT
            # pages take more than 200 seconds-> too slow. Try to use bootloader!
            log("Programming over USB", level=LOGL_VERBOSE,tag = self.NAME)
            for pageaddress in list(self.ChipPages.keys()):
                log("Flashing Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
                self.usbdm.writeBdmByte(MC9S12DJ64.REG_PAGE_MAP, pageaddress)
                pagestart = self.ChipPages[pageaddress][0]
                pageend = self.ChipPages[pageaddress][1]
                for segment in self.memorypages[pageaddress]:
                    written = 0
                    writelength = segment.getlength()
                    memorystart = segment.address-pagestart
                    log("Segment %10X-%10X"%(segment.address,segment.getsegmentend()), level=LOGL_NORMAL,tag = self.NAME)
                    while written<writelength:
                        self.usbdm.writeBdmWord(MC9S12DJ64.ADDRESS_MAPPED_PAGE+memorystart+written, segment.data[written:written+2])
                        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCMD, MC9S12DJ64.CMD_PROGRAM)
                        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FSTAT, MC9S12DJ64.BITS_FSTAT_CBEIF)
                        self.waitForFlash()
                        written = written + 2

    def erase(self):
        for pageaddress in self.ChipPages:
            log("Erasing Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
            self.usbdm.writeBdmByte(MC9S12DJ64.REG_PAGE_MAP, pageaddress)
            self.usbdm.writeBdmWord(MC9S12DJ64.ADDRESS_MAPPED_PAGE, 0xFFFF) #
            self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCMD, MC9S12DJ64.CMD_ERASE_PAGE)
            self.usbdm.writeBdmByte(MC9S12DJ64.REG_FSTAT, MC9S12DJ64.BITS_FSTAT_CBEIF)
            self.waitForFlash()


    def blankcheck(self):
        status = 0
        log("Blank check ",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmWord(MC9S12DJ64.ADDRESS_MAPPED_PAGE, 0xFFFF) #
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FCMD, MC9S12DJ64.CMD_BLANK)
        self.usbdm.writeBdmByte(MC9S12DJ64.REG_FSTAT, MC9S12DJ64.BITS_FSTAT_CBEIF)

        readstatus = self.waitForFlash()
        if readstatus & MC9S12DJ64.BITS_FSTAT_BLANK == MC9S12DJ64.BITS_FSTAT_BLANK:
            log("Device is blank",level=LOGL_NORMAL,tag = self.NAME)
        else:
            status = 1
            log("Device is not blank",level=LOGL_NORMAL,tag = self.NAME)
        return status

    def verify(self):
       threads = []
       errorQueue = Queue()

       #compare whole pages
       for pagenumber in list(self.ChipPages.keys()):
           log("Verifying Page %X"%(pagenumber), level=LOGL_NORMAL,tag = self.NAME)
           self.usbdm.writeBdmByte(MC9S12DJ64.REG_PAGE_MAP, pagenumber)

           flashmemory = self.readmemory(MC9S12DJ64.ADDRESS_MAPPED_PAGE, MC9S12DJ64.PAGE_LENGTH)

           # compare memory
           thread = threading.Thread(target=comparepagetosegments, args=(self.memorypages[pagenumber],flashmemory,self.ChipPages[pagenumber][0],self.ChipPages[pagenumber][1],errorQueue,))
           threads.append(thread)
           thread.start()

       for t in threads:
           t.join()

       if not errorQueue.empty():
           while not errorQueue.empty():
               result = errorQueue.get()
               log("Memory did not match at %10X expected: %2s read: %2s"%(result[0], ''.join('{:02x}'.format(x) for x in result[1]), ''.join('{:02x}'.format(x) for x in result[2])),level=LOGL_VERBOSE,tag = self.NAME)

           raise ValueError("Error: Contents don't match the file")
       else:
           log("Verified. Contents are good",level=LOGL_NORMAL,tag = self.NAME)

    def waitForEEPROM(self):
        timeout = time.time()*1000  + 5000 # 5 seconds
        readstatus = 0x00
        while True:
            if time.time()*1000<timeout:
                readstatus = self.usbdm.readBdmByte(MC9S12DJ64.REG_ESTAT)[1]
                if readstatus & MC9S12DJ64.BITS_ESTAT_ACCER == MC9S12DJ64.BITS_ESTAT_ACCER:
                    raise ValueError("Error: couldn't access EEPROM")
                elif readstatus & MC9S12DJ64.BITS_ESTAT_CCIF == MC9S12DJ64.BITS_ESTAT_CCIF:
                   break
            else:
                raise ValueError("Error: command timed out")
        return readstatus


    def waitForFlash(self):
        timeout = time.time()*1000  + 5000 # 5 seconds
        readstatus = 0x00
        while True:
            if time.time()*1000<timeout:
                readstatus = self.usbdm.readBdmByte(MC9S12DJ64.REG_FSTAT)[1]
                if readstatus & MC9S12DJ64.BITS_FSTAT_ACCER == MC9S12DJ64.BITS_FSTAT_ACCER:
                    raise ValueError("Error: couldn't access flash")
                elif readstatus & MC9S12DJ64.BITS_FSTAT_CCIF == MC9S12DJ64.BITS_FSTAT_CCIF:
                   break
            else:
                raise ValueError("Error: command timed out")
        return readstatus

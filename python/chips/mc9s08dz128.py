from helpers import *
from usbdm import*
from chips.chipinterface import ChipInterface
import threading
from queue import Queue

# Note: D64-Flash can only write word-length
# Chip Clock is 40 Mhz, Bus Clock is 20 Mhz
# Clock defaults to either 32 or 16 Mhzrb 0x
# This chip has linear address access capabilities, so it is not required to use page window
class MC9S08DZ128(ChipInterface):
    NAME = "MC9S08DZ128"
    ADDRESS_MAPPED_PAGE = 0x8000
    ADDRESS_SECURITY = 0xFFBF

    VALUE_SECURITY_UNSECURE = 0xFFFE
    VALUE_SECURITY_SECURE = 0xFFFF

    RAM_START =   0x00000080
    RAM_END   =   0x00001800

    RAM2_START =  0x00001900
    RAM2_END   =  0x00002180

    EEPROM_START = 0x00003C00
    EEPROM_END =   0x00004000

    REG_PAGE_MAP= 0x00000078
    REG_MCGC1   = 0x00000048
    REG_MCGC2   = 0x00000049
    REG_MGCB    = 0x0000004B
    REG_MCGC3   = 0x0000004C
    REG_MCGT    = 0x0000004D

    REG_SOPT1   = 0x00001802
    REG_FCLKDIV = 0x00001820
    REG_FOPT    = 0x00001821
    REG_FCNFG   = 0x00001823
    REG_FPROT   = 0x00001824
    REG_FSTAT   = 0x00001825
    REG_FCMD    = 0x00001826


    BITS_FSTAT_ACCER = 0x10
    BITS_FSTAT_PVIOL = 0x20 # protection violation
    BITS_FSTAT_CCIF  = 0x40
    BITS_FSTAT_CBEIF = 0x80
    BITS_FSTAT_RESET = 0xFF
    BITS_FSTAT_BLANK = 0x04

    CMD_BLANK          = 0x05
    CMD_PROGRAM_BYTE   = 0x20
    CMD_PROGRAM_BURST  = 0x25
    CMD_ERASE_SECTOR   = 0x40
    CMD_ERASE_MASS     = 0x41

    def __init__(self,usbdm):
        # Note: linear access addresses differ from addresses used in .hex or .s19 files
        ChipInterface.__init__(self, usbdm, 0x01, {0:[0x2180,0x217F], 1:[0x4000,0x7FFF], 2:[0x8000,0xBFFF], 3:[0xC000,0xFFFF],4:[0x48000,0x4BFFF],5:[0x58000,0x5BFFF],6:[0x68000,0x6BFFF],7:[0x78000,0x7BFFF]}, 0x1806, [0x0119,0x2019])

        # Because bootloader is loaded in RAM area which can be
        # addressed with one byte the locations of variables are addressed as such
        # Register: A 8-bit
        #           HX 16-bit
        #           SP 16-bit
        #           PC 16-bit

        # bootloader for flashing
        # Ram starts at 0x80
        #80+2  VAR16_DESTINATION     # flash destination
        #82+2  VAR16_TO_FLASH        # bytes end
        #84+2  VAR16_FLASHED         # bytes flashed
        #86+1  VAR8_DONE            # flag set when the flashing is done
        #87+2  \xa6\x80              # [lda #04] load 0x80 into A
        #89+3  \xc4\x18\x25         # [anda opr16a] check if CBEIF bit is set
        #8C+2  \x27\xf9\             # [beq rel] branch until CBEIF is set
        #8E+2  \x55\x84              # [ldhx opr8a] load source address in H:X
        #90+1  \xf6                  # [lda A,$X] load source byte into A
        #91+2  \x55\x80              # [ldhx opr8a] load destination address in H:X
        #93+1  \xf7                  # [sta A, $X] store A at destination address
        #94+2  \xa6\x25              # [lda 0x25] load "burst cmd" into A
        #96+3  \xc7\x18\x26          # [sta opr16a] store A in fcmd
        #99+2  \xa6\x80              # [lda 0x25] load 0x80 into A
        #9B+3  \xc7\x18\x25          # [sta opr16a] store A in fstat
        #9E+2  \x55\x80              # [ldhx opr8a] load destination
        #A0+2  \xaf\x01             # [aix 0x01] increment destination
        #A2+2  \x35\x80              # [sthx opr8a] store 16-bit in destination
        #A4+2  \x55\x84              # [ldhx opr8a] load flashed
        #A6+2  \xaf\x01             # [aix 0x01] increment flashed
        #A8+2  \x35\x84              # [sthx opr8a] store 16-bit in flashed
        #AA+2  \x75\x82              # [cphx opr8a] compare flashed to end
        #AC+2  \x26\xd9              # [bne goto 86] branch if flashed != end
        #AE+2  \xa6\x40              # [lda #04] load 0x40 into A
        #B0+3  \xc4\x18\x25         # [anda opr16a] check if CBCCF bit is set
        #B3+2  \x27\xf9\             # [beq rel] branch until CBCCF is set
        #B5+2  \x3c\x86             # [inc $0x86] set "flashing done flag"
        #B7+2  \x20\xfe              # loop


        self.bootloader =  [b"\xa6\x80",\
                            b"\xc4\x18\x25",\
                            b"\x27\xf9",\
                            b"\x55\x84",\
                            b"\xf6",\
                            b"\x55\x80",\
                            b"\xf7",\
                            b"\xa6\x25",\
                            b"\xc7\x18\x26",\
                            b"\xa6\x80",\
                            b"\xc7\x18\x25",\
                            b"\x55\x80",\
                            b"\xaf\x01",\
                            b"\x35\x80",\
                            b"\x55\x84",\
                            b"\xaf\x01",\
                            b"\x35\x84",\
                            b"\x75\x82",\
                            b"\x26\xd9",\
                            b"\xa6\x40",\
                            b"\xc4\x18\x25",\
                            b"\x27\xf9",\
                            b"\x3c\x86",\
                            b"\x20\xfe",\
                            ]


    def unsecure(self):
        protection = self.usbdm.readBdmByte(MC9S08DZ128.REG_FPROT)[1]

        # halt target when necessary
        # write 1802 20(watchdog)
        # erase
        # read fopt -> e3

        # check if protection is in place
        if  protection & 0x01 == 0x00 or (protection>1)&0x1F != 0x1F:
            self.usbdm.writeBdmByte(MC9S08DZ128.REG_FPROT, 0xFF)
            self.erase()
            self.blankcheck()


    def setup(self):
        # After Reset the MCGOUT defaults to 16 Mhz(wrong): using Internal Clock + FLL
        # if Clock Defaults to 32 - 40 Mhz so need to clear the DRS bit
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_SOPT1, 0x20)        # stop mode watchdog
        if not self.usbdm.readBdmByte(MC9S08DZ128.REG_MCGC1)[1] & 0xC0 == 0x00:
            raise ValueError("Error: FLL not set")

        if not self.usbdm.readBdmByte(MC9S08DZ128.REG_MCGC2)[1] & 0xC0 == 0x40:
            raise ValueError("Error: Bus Clock Divider is not 2")

        self.usbdm.writeBdmByte(MC9S08DZ128.REG_MCGT, 0x00)

        # Wait for bit to clear to get DCOOUT into the 16 -20 Mhz range
        timeout = time.time()*1000 + 5000
        while self.usbdm.readBdmByte(MC9S08DZ128.REG_MCGT)[1] !=0x00:
            if time.time()*1000>timeout:
                raise ValueError("Error: Couldn't change Clock range to 16 Mhz -")



        # Set Flash CLock to <~200 Khz for 8 Mhz bus
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FCLKDIV, 0x2e) # 2e?

        # Setup flash registers
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FCNFG, 0x00)
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FPROT, 0xFF)
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FSTAT, 0xFF)    # Reset FSTAT

        # TODO add FLL and PLL examples here to check if clock is working
        # Required Clock Generator Mode PBE: PLL bypassex external Page.189
        # CLKS 10
        # IREFS 0
        # PLLS 1
        # RDIV to divide down to 2 8Mhz
        # LP 0
        # Set FLL config to 0
        # Needed MCGOUT: BusFreq = MCGOUT/2
        #self.usbdm.writeBdmByte(MC9S08DZ128.REG_MCGC2, 0x00)

        # Setsystem clock to external 10 Mhz, clock stays enabled during stop
        #self.usbdm.writeBdmByte(MC9S08DZ128.REG_MCGC1, 0x85)

        #Set Bus Frequency Clock to 10 Mhz: Mhz Range, High Gain, Disable FLL in Bypass mode
        #self.usbdm.writeBdmByte(MC9S08DZ128.REG_MCGC2, 0x38)

    # Need to connect to program
    def program(self):
        # During Burst Programming the sequential flash accesses are faster than singular
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

    def flash(self):
        log("Loading bootloader into RAM",level=LOGL_VERBOSE,tag = self.NAME)
        self.halt()

        jbootloader = b"".join(self.bootloader)
        dataoffset = len(jbootloader)+7
        self.writememory(MC9S08DZ128.RAM_START+7, jbootloader)

        pagenumbers = list(self.ChipPages.keys())  # are the keys

        for pageaddress in pagenumbers:
            if len(self.memorypages[pageaddress]) == 0:
                log("Skipping Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
            else:
                log("Flashing Page %X"%(pageaddress), level=LOGL_NORMAL,tag = self.NAME)
                pagestart = self.ChipPages[pageaddress][0]
                pageend = self.ChipPages[pageaddress][1]

                self.usbdm.writeBdmByte(MC9S08DZ128.REG_PAGE_MAP, pageaddress)

                # Flash segments for current page
                for segment in self.memorypages[pageaddress]:
                    written = 0
                    dataleft = segment.getlength()
                    memorystart = segment.address-pagestart
                    maxspace = MC9S08DZ128.RAM_END - (MC9S08DZ128.RAM_START+dataoffset) # minus the size of the bootloader + some bytes
                    offset = segment

                    # Write in small batches, because ram is only 1k
                    while dataleft > 0:
                        sztowrite = 0
                        if dataleft>maxspace:
                            sztowrite = maxspace
                        else:
                            sztowrite = dataleft

                        log("Flashing %d Bytes, Address: %x "%(sztowrite,MC9S08DZ128.ADDRESS_MAPPED_PAGE + memorystart + written), level=LOGL_VERBOSE,tag = self.NAME)
                        self.writememory(MC9S08DZ128.RAM_START+dataoffset,segment.data[written:written+sztowrite])

                        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FSTAT, 0xFF)    # Reset FSTAT
                        self.usbdm.writeBdmWord(MC9S08DZ128.RAM_START, MC9S08DZ128.ADDRESS_MAPPED_PAGE + memorystart + written)
                        self.usbdm.writeBdmWord(MC9S08DZ128.RAM_START+2, (MC9S08DZ128.RAM_START+sztowrite+dataoffset).to_bytes(2,"big"))
                        self.usbdm.writeBdmWord(MC9S08DZ128.RAM_START+4, (MC9S08DZ128.RAM_START+dataoffset).to_bytes(2,"big"))
                        self.usbdm.writeBdmByte(MC9S08DZ128.RAM_START+6, 0x00)

                        log("Executing bootloader ", level=LOGL_VERBOSE,tag = self.NAME)
                        self.usbdm.writeRegister(0x0B, MC9S08DZ128.RAM_START+7)   # set PC Counter
                        self.usbdm.runTarget()               # execute boot loader
                        timeout = time.time() * 1000  + 5000
                        while True:
                            if time.time()*1000<timeout:
                                flashingdone = self.usbdm.readBdmByte(MC9S08DZ128.RAM_START+6)
                                #self.readmemory(0x4000, 50)
                                if flashingdone[1] == 0x01:
                                    break
                            else:
                                raise ValueError("Error: flashing timed out")

                        log("Halting bootloader ", level=LOGL_VERBOSE,tag = self.NAME)
                        self.usbdm.haltTarget()
                        written = written + sztowrite
                        dataleft = dataleft - sztowrite

    def erase(self):
        log("Mass Erasing flash" , level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.writeBdmByte(0x3bf0, 0xFF) #
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FCMD, MC9S08DZ128.CMD_ERASE_MASS)
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FSTAT, MC9S08DZ128.BITS_FSTAT_CBEIF)
        self.waitForFlash()

    def blankcheck(self):
        status = 0
        log("Blank check ",level=LOGL_VERBOSE,tag = self.NAME)
        self.usbdm.writeBdmByte(0x3bf0, 0xFF) #
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FCMD, MC9S08DZ128.CMD_BLANK)
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FSTAT, MC9S08DZ128.BITS_FSTAT_CBEIF)

        readstatus = self.waitForFlash()
        if readstatus & MC9S08DZ128.BITS_FSTAT_BLANK == MC9S08DZ128.BITS_FSTAT_BLANK:
            log("Device is blank",level=LOGL_NORMAL,tag = self.NAME)
        else:
            status = 1
            log("Device is not blank",level=LOGL_NORMAL,tag = self.NAME)
        self.usbdm.writeBdmByte(MC9S08DZ128.REG_FSTAT, 0x30)    # Reset FSTAT
        return status

    def verify(self):
       threads = []
       errorQueue = Queue()

       # compare segment addresses
       for segment in self.memory.segments:
           segaddress = segment.address

           found = False
           for pagenumber in self.ChipPages:
               pagestart = self.ChipPages[pagenumber][0]
               pageend = self.ChipPages[pagenumber][1]
               if segaddress>= pagestart and segaddress<=pageend:
                    log("Verifying Segment %X"%(segaddress), level=LOGL_NORMAL,tag = self.NAME)
                    self.usbdm.writeBdmByte(MC9S08DZ128.REG_PAGE_MAP, pagenumber)
                    flashmemory = self.readmemory(MC9S08DZ128.ADDRESS_MAPPED_PAGE+(segaddress-pagestart), segment.getlength())
                    thread = threading.Thread(target=comparememorytosegment, args=(segment, flashmemory, errorQueue,))
                    threads.append(thread)
                    thread.start()
                    found = True
           if not found:
               raise ValueError("Error: segment address not assigned to pages")

       for t in threads:
           t.join()

       if not errorQueue.empty():
           while not errorQueue.empty():
               result = errorQueue.get()
               log("Memory did not match at %10X expected: %2s read: %2s"%(result[0], result[1], result[2]),level=LOGL_VERBOSE,tag = self.NAME)

           raise ValueError("Error: Contents don't match the file")
       else:
           log("Verified. Contents are good",level=LOGL_NORMAL,tag = self.NAME)


    def waitForFlash(self):
        timeout = time.time()*1000  + 5000 # 5 seconds
        readstatus = 0x00
        while True:
            if time.time()*1000<timeout:
                time.sleep(0.010)
                readstatus = self.usbdm.readBdmByte(MC9S08DZ128.REG_FSTAT)[1]
                if readstatus & MC9S08DZ128.BITS_FSTAT_ACCER == MC9S08DZ128.BITS_FSTAT_ACCER:
                    raise ValueError("Error: couldn't access flash")
                elif readstatus & MC9S08DZ128.BITS_FSTAT_PVIOL == MC9S08DZ128.BITS_FSTAT_PVIOL:
                    raise ValueError("Error: protection violation flash")
                elif readstatus & MC9S08DZ128.BITS_FSTAT_CCIF == MC9S08DZ128.BITS_FSTAT_CCIF:
                   break
            else:
                raise ValueError("Error: command timed out")
        return readstatus

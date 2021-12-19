# author: am
# date: 04.12.2020
# description: Example of communication with USBDM and DJ64 chip using libusb + "libusb driver"
# ver: 1.00

import usb.core
import usb.util
import struct
import time
from helpers import *



# General interface for usbdm
# each Command is at least 2 Bytes long
# tx-command is <length><command><data>
# rx-command is <status>
#               <length><data>
# First one is a placedholder and is reused as status
class Usbdm():
    NAME= "USBDM"
    USBDM_SPEED     = 0x077f   # approx. 4 Mhz, not used
    def __init__(self):
        self.inEndpoint = None
        self.outEndpoint = None
        self.dev = None
        self.find()
        self.reinit()

        # specific .dll
        # backend = usb.backend.libusb1.get_backend(find_library=lambda x: "/usr/lib/libusb-1.0.so")
        # dev     = usb.core.find(..., backend=backend)

    def find(self):
        #Unknown Phenomenon, Device registers with another VID and PID and does not have an OUT Endpoint
        #Could this be failsafe configuration?
        #usb.core.find(idVendor=0x15A2, idProduct=0x0038)#
        self.dev  = usb.core.find(idVendor=0x16D0, idProduct=0x06A5)
        if self.dev is None:
            raise ValueError('Error: Device not found')
        else:
            log(self.dev.manufacturer, debugline="Manufacturer:", level=LOGL_NORMAL, tag=Usbdm.NAME)

    # set the active configuration. With no arguments, the first
    # configuration will be the active one
    def reinit(self):
        self.dev.set_configuration()
        self.cfg = self.dev.get_active_configuration()

        if self.cfg is None:
            raise ValueError('Error: No active usb configuration')

        log(self.cfg,level=LOGL_DEBUG)
        intf = self.cfg[(0,0)]

        # match the first endpoints: For BDM these are 0x01(OUT) and 0x82(IN)
        self.outEndpoint = usb.util.find_descriptor(intf, custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.inEndpoint = usb.util.find_descriptor(intf, custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        if self.outEndpoint is None or self.inEndpoint is None:
            raise ValueError('Error: Endpoints not found for the interface')

        readback = self.dev.ctrl_transfer(0xC0, 0x0C, 0x100, 0, 10)   # URB control transfer,  to get the HW and SW versions
        log(readback, level=LOGL_DEBUG ,conv="hex",tag="Hw and Sw")

        if readback[0]:
            raise ValueError('Error: Control Endpoint failed')


    # Some of those set the target, don't know which ones yet
    def openBdm(self):
        # Get String Descriptor Index 2
        string = usb.util.get_string(self.dev, 2)           # Device String 1
        log(string, debugline = "Device String1:", level=LOGL_DEBUG, tag=Usbdm.NAME)

        # Get String Descriptor Index 3
        string = usb.util.get_string(self.dev, 3)           # Device String 2
        log(string, debugline = "Device String2:", level=LOGL_DEBUG,tag=Usbdm.NAME)

        readback = self.dev.ctrl_transfer(0xC0, 0x0C, 0x101, 0, 10)   # URB control transfer, to get the HW and SW versions
        log(readback,conv = "hex", debugline = "URB Control Transfer:", level=LOGL_DEBUG,tag=Usbdm.NAME)

        self.outEndpoint.write("\x02\x05")                  # GET CAPABILITIES
        readback = self.inEndpoint.read(8)

        log(readback,conv = "hex", debugline = "Get Capabilities:", level=LOGL_DEBUG, tag=Usbdm.NAME)

        # Write something and read status
        # HCS08 uses 08 06 00 00 ff 02 30 01
        # HCS08 uses 08 06 00 00 ff 02 18 01
        #self.outEndpoint.write(b"\x08\x06\x00\x00\xff\x02\x18\x01") # SET OPTIONS(SBDFRaddr,autoReconnect,altbdmclock,[cyclevddonreset,cycleonconnect,leavepowered,guessspeedd,useresetsignal])

        self.outEndpoint.write(b"\x06\x06\x18\x00\xff\x02") # SET OPTIONS(SBDFRaddr,autoReconnect,altbdmclock,[cyclevddonreset,cycleonconnect,leavepowered,guessspeedd,useresetsignal])
        # alternative with autoreconnect
        #elf.outEndpoint.write(b"\x06\x06\x18\x01\xff\x02")

        readback = self.inEndpoint.read(1)
        log(readback,conv = "hex", debugline = "Set Options:", level=LOGL_DEBUG,tag=Usbdm.NAME)

        # Write some more
        self.outEndpoint.write(b"\x02\x04")                 # GET BDM STATUS
        status = self.inEndpoint.read(3)
        log(readback, conv = "hex", debugline = "Bdm Status:",level=LOGL_DEBUG, tag=Usbdm.NAME)

        readback = self.dev.ctrl_transfer(0xC0, 0x0C, 0x144, 0, 10)   # URB control transfer, what for ?
        log(readback,level=LOGL_DEBUG,debugline = "URB Control Transfer:",conv="hex", tag=Usbdm.NAME)
        return status[0]

    # try to reclaim the interface
    def reattach(self):
        reattach = False
        if self.dev.is_kernel_driver_active(0):
            reattach = True
            self.dev.detach_kernel_driver(0)

        usb.util.dispose_resources(self.dev)

        # It may raise USBError if there's e.g. no kernel driver loaded at all
        if reattach:
            self.dev.attach_kernel_driver(0)

    def closeBdm(self):
        self.outEndpoint.write(b"\x03\x01\xff")     # SET TARGET 0xFF
        status = self.inEndpoint.read(1)
        log(status, debugline = "Unset Target:", level=LOGL_DEBUG, conv="hex",tag=Usbdm.NAME)

        self.outEndpoint.write(b"\x04\x02\x00\x00") # SET VDD 0
        status = self.inEndpoint.read(1)
        log(status, debugline = "Unset Vdd:", level=LOGL_DEBUG, conv="hex", tag=Usbdm.NAME)

        return status[0]

    def connect(self):
        self.outEndpoint.write(b"\x02\x11") # GET SPEED
        readback = self.inEndpoint.read(3)  # 0x0 0x7 0x7f  or 0x0 0x7 0x7d or 03 31
        log(readback, debugline = "Speed:",level=LOGL_DEBUG, conv="hex", tag=Usbdm.NAME)

        # set speed here
        if readback[1] == 0x00 or readback[2] == 0x00:
            pass
            #self.outEndpoint.write(b"\x04\x10\x07\x7f") # SET SPEED
            #readback = self.inEndpoint.read(1)    # status(00), returns 12 if target is secured. Can't connect
            #log(readback, debugline = "Setting Speed:", level=LOGL_DEBUG, conv="hex", tag=Usbdm.NAME)

        self.outEndpoint.write(b"\x02\x0f") # CONNECT
        readback = self.inEndpoint.read(1)    # status(00), returns 12 if target is secured. Can't connect
        log(readback, debugline = "Connect:", level=LOGL_DEBUG, conv="hex", tag=Usbdm.NAME)

        self.outEndpoint.write(b"\x02\x04") # GET BDM STATUS
        readback = self.inEndpoint.read(3)  # 0x0 0x0 0x5d
        log(readback, debugline = "Bdm Status:",level=LOGL_DEBUG, conv="hex", tag=Usbdm.NAME)

        return readback[0]

    def getBdmStatus(self):
        self.outEndpoint.write(b"\x02\x14") # READ BDM STATUS REG
        readback = self.inEndpoint.read(5)  # 0x0 0x0 0x0 0x0 0xc0
        log(readback, debugline = "Bdm Status Reg:", level=LOGL_DEBUG, conv="hex",tag=Usbdm.NAME)

        self.outEndpoint.write(b"\x02\x04") # GET BDM STATUS
        bdmstatus = self.inEndpoint.read(3)  # 0x0 0x0 0x4d
        log(bdmstatus, debugline = "Bdm Status:", level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME)

        return bdmstatus

    def setBdmTarget(self, target):
        # Write something and read status
        self.outEndpoint.write(b"\x03\x01"+target.to_bytes(1,"big")) # SET TARGET 0x00: HCS12
        status = self.inEndpoint.read(1)
        log(status,level=LOGL_DEBUG, conv="hex",tag =Usbdm.NAME, debugline="Set Target:")
        return status[0]


   # Control reset pin
    def resetTarget(self):
        self.outEndpoint.write(b"\x04\x08\x00\x0a")          # Set reset pin high
        readback = self.inEndpoint.read(3)  # 0x0 0x0 0x08
        log(readback,level=LOGL_DEBUG, conv="hex",tag =Usbdm.NAME, debugline="Control pins 0:")
        self.outEndpoint.write(b"\x04\x08\x00\x04")          # Set reset pin tri state
        readback = self.inEndpoint.read(3)  # 0x0 0x0 0x0c
        log(readback,level=LOGL_DEBUG, conv="hex",tag =Usbdm.NAME, debugline="Control pins 1:")
        time.sleep(1)
        self.outEndpoint.write(b"\x04\x08\xff\xff")          # RELEASE
        readback = self.inEndpoint.read(3)  # 0x0 0x0 0x0c
        log(readback,level=LOGL_DEBUG, conv="hex",tag =Usbdm.NAME, debugline="Control pins 2:")
        time.sleep(1)
                           # Let the device reset: Can't connect without waiting
        return readback[0]

    # this doesn't seem to work properly
    def resetTargetInternal(self):
        self.outEndpoint.write(b"\x03\x16\x08") # RESET TARGET
        time.sleep(0.5)
        #readback = self.inEndpoint.read(4)    # 0x3 0x1 0x2 0x3     is what you read when the device is busy
        readback = self.inEndpoint.read(1)    # 0x01
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Reset Target:")
        time.sleep(1)               # Let the device reset
        return readback[0]

    # 02 19 sent after connect by hcs08
    def haltTarget(self):
        self.outEndpoint.write(b"\x02\x19")
        status = self.inEndpoint.read(1)    # 0x00
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Halt target:")
        return status[0]

    def runTarget(self):
        #self.outEndpoint.write(b"\x08\x21\x01\x04\x00\x00"+pc.to_bytes(2,"big")) # Read opcodes to be executed, 4 bytes
        #status = self.inEndpoint.read(1)    # 0x00
        #log(status,level=LOGL_DEBUG, conv="hex", tag="Read Next Opcodes#")

        self.outEndpoint.write(b"\x02\x18")
        status = self.inEndpoint.read(1)    # 0x00
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Run target:")
        return status[0]

    def writeRegister(self, register, pc):
        self.outEndpoint.write(b"\x08\x1a\x00"+register.to_bytes(1,"big")+b"\x00\x00"+pc.to_bytes(2,"big"))
        status = self.inEndpoint.read(1)    # 0x00
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Pc Register:")
        return status[0]


    def writeCoreRegister(self):
        self.outEndpoint.write(b"\x04\x1b\x00\x03")     # What is being set exactly??? In the response is the PC Counter
        status = self.inEndpoint.read(5)    # 0x00 0x00 0x00 0x(Program) 0x(Counter)
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Core Register:")
        return status[0]

    def writeControlRegister(self):
        self.outEndpoint.write(b"\x06\x15\x00\x00\x00\xc4") # WRITE CONTROL REGISTER c4
        status = self.inEndpoint.read(1)    # 0x00
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Control Register:")
        return status[0]

    def writeControlRegister2(self):
        self.outEndpoint.write(b"\x06\x15\x00\x00\x00\x04") # WRITE CONTROL REGISTER 4
        status = self.inEndpoint.read(1)    # 0x00
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Control Register:")
        return status[0]


    def writeBdmBlock(self, address, data):
        size = len(data)
        if size>0x88:
            return 0xff
        # max 62 bytes per 1# frame
        # max ? 2# frame,
        # max 0x90 total amount
        # max 0x88 payload
        if size > 62-8:
            self.outEndpoint.write((size+8).to_bytes(1,"big")+b"\x20\x01"+size.to_bytes(1,"big") + address.to_bytes(4,"big") + data[:62-8])          # WRITE MEM
            self.outEndpoint.write(b"\x00"+ data[62-8:])                   # WRITE MEM
        else:
            self.outEndpoint.write((size+8).to_bytes(1,"big")+b"\x20\x01"+size.to_bytes(1,"big") + address.to_bytes(4,"big") + data)          # WRITE MEM

        status = self.inEndpoint.read(1)    # could be 0x11
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Byte:")
        return status[0]

    def readBdmBlock(self, address, size):
        if size>0x90:
            return 0xff
        # max size is 0x90 ->  144 bytes
        self.outEndpoint.write(b"\x08\x21\x01"+size.to_bytes(1,"big") + address.to_bytes(4,"big"))
        readback = self.inEndpoint.read(size+1)  # 0x0(status) <bytes>
        log(readback,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Read Block:")
        return readback

    def writeBdmByte(self, address, byte):
        self.outEndpoint.write(b"\x09\x20\x01\x01" + address.to_bytes(4,"big") + byte.to_bytes(1,"big"))          # WRITE MEM
        #readback = self.inEndpoint.read(4)  # 0x3 0x1 0x2 0x3
        status = self.inEndpoint.read(1)    # could be 0x11
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline ="Write Byte")
        return status[0]

    def writeBdmWord(self, address, word ):
        if isinstance(word, int):
            self.outEndpoint.write(b"\x0a\x20\x01\x02" + address.to_bytes(4,"big") + word.to_bytes(2,"big"))           # WRITE INTEGER MEM
        elif len(word) == 2:
            self.outEndpoint.write(b"\x0a\x20\x01\x02" + address.to_bytes(4,"big") + word)                             # WRITE BYTES MEM
        else:
            raise ValueError("Error: Data is not integer or wrong byte length")

        #readback = self.inEndpoint.read(4)  # 0x3 0x1 0x2 0x3 is what you read when the device is busy
        status = self.inEndpoint.read(1)    # could be 0x11
        log(status,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Write Word:")
        return status[0]

    def readBdmByte(self, address):
        self.outEndpoint.write(b"\x08\x21\x01\x01" + address.to_bytes(4,"big"))      # READ MEM
        readback = self.inEndpoint.read(2)  # 0x3 0x1 0x2 0x3
        log(readback,level=LOGL_DEBUG, conv="hex", tag =Usbdm.NAME, debugline="Read Byte:")
        return readback

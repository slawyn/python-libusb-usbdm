# author: am
# date: 20.11.2020
# description: libusb based python interface to usbdm for programm Motorola chips
# rev: 1.00

from chips.mc9s12dg128 import MC9S12DG128
from chips.mc9s12dj64 import MC9S12DJ64
from chips.mc9s08dz128 import MC9S08DZ128
from usbdm import Usbdm
from helpers import *
import sys

# Supported Chips
chips = {MC9S12DJ64.NAME:MC9S12DJ64,MC9S12DG128.NAME:MC9S12DG128,MC9S08DZ128.NAME:MC9S08DZ128}


'''
 Start execution here
'''
if __name__ == "__main__":
    if len(sys.argv)>1:
        chipHandle = None
        usbdmHandle = None
        filename = ""
        chipname = ""
        loglevel = LOGL_NORMAL
        idx = 1

        try:
            while idx<len(sys.argv):
                if sys.argv[idx] == "-file":
                    idx +=1
                    filename = sys.argv[idx]
                elif sys.argv[idx] == "-chip":
                    idx +=1
                    chipname = sys.argv[idx]
                elif sys.argv[idx] == "-log":
                    idx +=1
                    loglevel = int(sys.argv[idx])
                idx +=1

            setlogginglevel(loglevel)
            usbdmHandle = Usbdm()
            if chipname in chips.keys():
                chipHandle = chips[chipname](usbdmHandle)
                chipHandle.load(filename)
                chipHandle.program()
            else:
                raise ValueError("Error: Chip not found")
        except Exception as e:
            log(e, level=LOGL_NORMAL)
            sys.exit(1)

    else:
        print("Arguments:")
        print("%-30s :%s"%("\t-file <>","load file to program .bin|.s19|.hex"))
        print("%-30s :%s"%("\t-chip <chipname>","select chip to program"))
        print("%-30s :%s"%("\t-log <loglevel>","change logging level DEBUG(0) VERBOSE(1) NORMAL(2)"))
        print("Commands:")
        print("%-30s :%s"%("\tlog <loglevel>","change logging level DEBUG(0) VERBOSE(1) NORMAL(2)"))
        print("%-30s :%s"%("\tload <file>","load file to program .bin|.s19|.hex"))
        print("%-30s :%s"%("\topen <chip name>","open specific chip"))
        print("%-30s :%s"%("\thalt","halt processor"))
        print("%-30s :%s"%("\tauto","auto identification of the connected chip"))
        print("%-30s :%s"%("\treattach","reattach usbdriver <TODO>"))
        print("%-30s :%s"%("\treset","reset chip"))
        print("%-30s :%s"%("\tconnect","connect to chip"))
        print("%-30s :%s"%("\tdisconnect","disconnect from chip"))
        print("%-30s :%s"%("\tprogram","program chip with loaded binary"))
        print("%-30s :%s"%("\tsetup","setup PLL and registers"))
        print("%-30s :%s"%("\tverify","compare programmed flash against the loaded binary"))
        print("%-30s :%s"%("\tread <address> <size>","read memory at address"))
        print("%-30s :%s"%("\twrite <address> <data>","write memory at address"))
        print("%-30s :%s"%("\tblankcheck","check if the device is blank"))
        chipHandle = None
        usbdmHandle = None

        try:
            usbdmHandle = Usbdm()
        except Exception as e:
            log(e, level=LOGL_NORMAL)

        #chiphandle = chips[0](usbdmHandle)
        #chiphandle.load("flash-bins/hcs12dj64-thimm.s19")
        #chiphandle.program()

        while usbdmHandle != None:
            try:
                ins = input()
                cmds = ins.split(" ")
                if cmds[0] == "log":
                    setlogginglevel(int(cmds[1]))
                elif cmds[0] == "open" and len(cmds) == 2:
                    if chipHandle != None:
                        chipHandle.close()

                    chipname = cmds[1].strip()
                    if chipname in chips.keys():
                        chipHandle = chips[chipname](usbdmHandle)

                elif cmds[0] == "auto":
                    log("Identifying..",level=LOGL_NORMAL)
                    found = ""
                    chipkeys = chips.keys()
                    for chipkey in chipkeys:
                        try:
                            chipHandle = chips[chipkey](usbdmHandle)
                            found = chipHandle.identify()
                            chipHandle.close()
                        except Exception as e:
                            log(e)

                        if found != "":
                            log("Found following chip: %s"%found,level=LOGL_NORMAL)
                            break
                    chipHandle = None

                elif chipHandle != None:
                    if cmds[0] == "close":
                        chipHandle.close()
                        chipHandle = None
                    elif cmds[0] == "disconnect":
                        chipHandle.disconnect()
                    elif cmds[0] == "connect":
                        chipHandle.connect()
                    elif cmds[0] == "unsecure":
                        chipHandle.unsecure()
                    elif cmds[0] == "load":
                        if len(cmds)>1:
                            chipHandle.load(cmds[1])
                        else:
                            log("Error: no file specified",level=LOGL_NORMAL)

                    elif cmds[0] == "program":
                        chipHandle.program()
                    elif cmds[0] == "setup":
                        chipHandle.setup()
                    elif cmds[0] == "erase":
                        chipHandle.erase()
                    # Note can only verify if the chip is not secured
                    elif cmds[0] == "verify":
                        chipHandle.verify()
                    elif cmds[0] == "reset":
                        chipHandle.reset()
                    elif cmds[0] == "reattach":
                        chipHandle.reattach()
                    elif cmds[0] == "halt":
                        chipHandle.halt()
                    elif cmds[0] == "blankcheck":
                        chipHandle.blankcheck()
                    elif cmds[0] == "read":
                        size = 0
                        if len(cmds)>2:
                            size = int(cmds[2])
                        if size == 0:
                           size = 1
                        address = int(cmds[1],16)
                        result = chipHandle.readmemory(address,size)
                        log((address,result),level=LOGL_NORMAL, conv="mem")

                    elif cmds[0] == "write":
                        chipHandle.writememory(int(cmds[1],16), bytes.fromhex(cmds[2]))

            except Exception as e:
                log(e, level=LOGL_NORMAL)

import sys
import time
import struct


def writeData(fd, pageaddress, offsetstart, offsetend):
	idx = 0
	startword = offsetstart
	while (startword) < offsetend:
		#print(hex(startword))
		bint = struct.unpack(">H",bindata[startword:startword+2])[0]
		line = "ww 0x%08X 0x%04X\n"%(pageaddress+idx,bint)
		#print(line)
		fout.write(line)
		fout.write("wb 0x00000106 0x20\n")
		fout.write("wb 0x00000105 0x80\n")
		idx = idx +2
		startword = offsetstart + idx


if __name__ == "__main__":
	DEBUG = False
	PAGE_ADDRESS= 0x8000


	fin = open("tr.bin","rb")
	bindata = fin.read()
	fin.close()
	
	try:
		if len(bindata):
			with open("hcs12dj.tcl","w") as fout:
				fout.write("settarget HCS12\n")
				fout.write("openbdm\n")
				fout.write("reset\n")
				fout.write("connect\n")
				fout.write("regs\n")
				fout.write("wb 0x0000000B 0x00\n")  	# Single mode 
				fout.write("wb 0x0000000B 0x00\n")
				fout.write("wb 0x0000003C 0x40\n")      # Stop Watchdog
				fout.write("wb 0x00000010 0x40\n")		#map the ram in
				fout.write("wb 0x00000012 0x00\n")
				fout.write("wb 0x00000013 0x03\n")
				fout.write("wb 0x00000103 0x00\n")
				fout.write("wb 0x00000104 0xFF\n")
				
				fout.write("wb 0x034 0x02\n")				# Configure PLL to 24 Mhz -> 12 Mhz Bus Clock, External Crystal(8 Mhz) as Source
				fout.write("wb 0x035  0x01\n")
				fout.write("wb 0x039 0x00\n")
				fout.write("wb 0x03A 0xD1\n")
				fout.write("wb 0x39 0x80\n")
				
				fout.write("wb 0x00000100 0x44\n")		# FCLK DIV. 12Mhz /(0x44 + 1) for approx. 175 Khz
					
				fout.write("wb 0x00000105 0xFF\n")       # Reset FSTAT
				
				fout.write("wb 0x00000030 0x3C\n")		# Erase Block/Page #3C : TCL won't wait here, but we need to wait 3 -4 Seconds/ test 0x105 for Completion flag
				fout.write("ww 0x0008000 0xFFFF\n")
				fout.write("wb 0x0000106 0x41\n")
				fout.write("wb 0x0000105 0x80\n")
				
				fout.write("wb 0x00000030 0x3D\n")		# Erase Block/Page #3D : TCL won't wait here, but we need to wait 3 -4 Seconds/ test 0x105 for Completion flag
				fout.write("ww 0x0008000 0xFFFF\n")
				fout.write("wb 0x0000106 0x41\n")
				fout.write("wb 0x0000105 0x80\n")
				
				fout.write("wb 0x00000030 0x3E\n")		# Erase Block/Page #3E : TCL won't wait here, but we need to wait 3 -4 Seconds/ test 0x105 for Completion flag
				fout.write("ww 0x0008000 0xFFFF\n")
				fout.write("wb 0x0000106 0x41\n")
				fout.write("wb 0x0000105 0x80\n")
				
				
				fout.write("wb 0x00000030 0x3F\n")		# Erase Block/Page #3F : TCL won't wait here, but we need to wait 3 -4 Seconds/ test 0x105 for Completion flag: 
				fout.write("ww 0x0008000 0xFFFF\n")
				fout.write("wb 0x0000106 0x41\n")
				fout.write("wb 0x0000105 0x80\n")
				
				if DEBUG:
					fout.write("rblock 0x4000 0x1F\n")		# read some memory: for debugging only
					fout.write("rblock 0x5000 0x1F\n")
					fout.write("rblock 0x8000 0x1F\n")
					fout.write("rblock 0xC000 0x1F\n")

					fout.write("wb 0x00000030 0x3C\n")
					writeData(fout,PAGE_ADDRESS, 0x3C8000, 0x3CBFFF)		# Program 3C Page
				
					fout.write("wb 0x00000030 0x3D\n")
					writeData(fout,PAGE_ADDRESS, 0x3D8000, 0x3DBFFF)		# Program 3D Page
	
			
					fout.write("wb 0x00000030 0x3E\n")
					writeData(fout,PAGE_ADDRESS, 0x4000, 0x8000)				# Program 3E Page
				
					fout.write("wb 0x00000030 0x3F\n")
					
					writeData(fout,PAGE_ADDRESS, 0xC000, 0xFF0E)				# Program 3F Page
					
					fout.write("ww 0xFF0E 0xFFFE\n")		# unsecure flash 0xFF0F(s12d64): for debugging only! Note, can only program word-length not bytes. Firmware won't work if there checksum test of this region
					fout.write("wb 0x106 0x20\n")
					fout.write("wb 0x105 0x80\n")	
				
					writeData(fout,PAGE_ADDRESS+(0xFF10-0xC000), 0xFF10, 0xFFFF)		# Program Second Page Part 2 , without the security bytes
				else:
					fout.write("wb 0x00000030 0x3C\n")
					writeData(fout,PAGE_ADDRESS, 0x3C8000, 0x3CBFFF)		# Program 3C Page
				
					fout.write("wb 0x00000030 0x3D\n")
					writeData(fout,PAGE_ADDRESS, 0x3D8000, 0x3DBFFF)		# Program 3D Page
					
					fout.write("wb 0x00000030 0x3E\n")
					writeData(fout,PAGE_ADDRESS, 0x4000, 0x8000)				# Program 3E Page
					
					fout.write("wb 0x00000030 0x3F\n")
					writeData(fout,PAGE_ADDRESS, 0xC000, 0xFFFF)				# Program 3F Page

				fout.close

			fout.close()

	except Exception as e:
		print(e)









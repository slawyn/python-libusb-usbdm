
# --- without target ---
filter: !(usb.data_len == 0 )&& usb.device_address == 3
[openbdm] sets target HCS12, openbdm	

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[writebdm] setstarget HCS12, openbdm, wb 0x4fff 0xaa, ww 0x4fff 0xaaaa rb 0x4fffe and closebdm	


# --- with target ----
filter: usb.device_address == 2 && !(usb.data_len == 0)	
[connect] settarget HCS12, openbdm, reset, connect, closebdm

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[getstatus] gs,gs,gs,gs,gs

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[reset] reset, reset, reset hardware normal, reset

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[rblock] rblock 0x8000 0xFF, rblock 0x8000 0x1FF

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[erase] mass erase from the Flash Programmer. A lot of data here l.115

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[wlong] writing a long

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[wblock] writing a block of data 200 bytes

filter: usb.device_address == 2 && !(usb.data_len == 0)	
[writereggohalt] writing PC(reg3), go, halt
#!/bin/bash

create() { # do not call or start this - it's just doc / a reminder
    sudo modprobe nbd max_part=4

    # testdrive.qc2 anlegen, MBR, 3 partitionen: ext4, fat und btrfs
    qemu-img create -f qcow2 testdrive.qc2 200M
    sudo qemu-nbd --connect=/dev/nbd0 testdrive.qc2
    sudo gparted /dev/nbd0
    
    # backupdrive, GPT, 1 partition, NTFS
    qemu-img create -f qcow2 backupdrive.qc2 210M
    sudo qemu-nbd --connect=/dev/nbd1 backupdrive.qc2
    sudo gparted /dev/nbd1

    
    # mount testdrive(s)
    mkdir bp1 bp2 bp3
    
    sudo mount /dev/nbd0p1 bp1
    sudo mount /dev/nbd0p2 bp2
    sudo mount /dev/nbd0p3 bp3
    
    # copy stuff
    #...
    
    sudo umount /dev/nbd0p[123]
    
    sync
    sudo qemu-nbd --disconnect /dev/nbd0
    sudo qemu-nbd --disconnect /dev/nbd1
    sudo modprobe -r nbd
    
    # done!
    rmdir bp[123]
}

qemu-system-x86_64 -enable-kvm -m 1024 -display gtk \
    -kernel BUILD/vmlinuz64 \
    -initrd BUILD/aubacore_x86_64.gz \
    -append "loglevel=0 noswap norestore multivt kmap=qwertz/de-latin1 base vga=791" \
    -drive file="testdrive.qc2",media=disk,index=0,if=ide \
    -drive file="backupdrive.qc2",media=disk,index=1,if=ide

#qemu-system-x86_64 -enable-kvm -m 1024 -display gtk \
#    -kernel BUILD/vmlinuz \
#    -initrd BUILD/aubacore_x86.gz \
#    -append "loglevel=0 noswap norestore multivt kmap=qwertz/de-latin1 base vga=791" \
#    -drive file="testdrive.qc2",media=disk,index=0,if=ide \
#    -drive file="backupdrive.qc2",media=disk,index=1,if=ide
#

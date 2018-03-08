#!/bin/sh

echo "mount truecryptvolume as label tc with password tc."

qemu-system-x86_64 -enable-kvm -m 1024 \
    -kernel BUILD/vmlinuz \
    -initrd BUILD/aubacore.gz \
    -append "loglevel=0 noswap norestore multivt kmap=qwertz/de-latin1 vga=791 base" \
    -hdc /home/iks/Downloads/qemu-dummy-drive 
    #-hdc /dev/sdc


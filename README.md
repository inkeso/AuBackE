# AuBackE - Autarkic Backup External

A small bootable backup-tool based on rsync

## Ingredients

**See [build.sh](build.sh)**

*Base:* [TinyCore Linux](http://www.tinycorelinux.net)

build.sh includes option for 32 or 64 bit.

*Additional TCZ-Packages (placed in tcz-dir):*

- kmaps        (for supporting other then US-keyboards)
- rsync, popt  (actual backup is done using this)
- python       (for AuBackE frontend)
- parted       (detecting partitiontypes and -labels)
- filesystems  (for additional filesystem support like xfs, reiserfs, jfs etc.)
- ntfs-3g      (for supporting NTFS-partitions)
- setfont      (if you don't want the default terminal font.)
- [terminus-font](http://terminus-font.sourceforge.net), or any other font. Place it in external-dir.
- readline, ncurses, ncurses-common, ncurses-terminfo
                   (readline-support in AuBackE for a better input-experience)
- you can also include any other TCZ you want... dependencies are resolved by build-skript

*Actual sources are:*

- ~/.ashrc (invoking AuBackE on first login, created in build.sh)
- aubacke.py (the program itself)

*For building initial ramdisk you need:*

- cpio (for extracting the TC-ramdisk)
- 7z (for a tighter recompression, optional)

For using veracrypt, place matching cli-binary in external/$ARCH.
(Well, that was working with truecrypt, but veracrypt doesn't execute in TC. 
I don't know why. So... no veracrypt at the moment.)


# Building

## Create ramdisk

For building the modified tinycore-image, edit & execute `build.sh`

A BUILD-dir containing all needed files is created:

- aubacore_$ARCH.gz (ramdisk)
- vmlinuz (kernel)

## Prepare external drive

You can copy them to a partition on you external drive and install a
bootloader. For example sys-/extlinux or grub.

In the examples below, the framebuffer is set to 1024x768 which is fine
for the default-font. Something lower like 800x600 will also work (I 
tried to limit the output to about 100 columns). But if you don't intend
to use this script on computers with very, very old low-res screen, I 
recomment using at least 1024x768 and/or a smaller font (see build.sh)
as you want as much output as possible visible on the screen.

### For extlinux

- Install the MBR to the external drive:
  `./extlinux -i /mnt/ext3partition`
  `./syslinux -d . -i /dev/sdc1`
- Set the partition to active / bootable
- create extlinux.conf:
```
    DEFAULT aubacke
    LABEL aubacke
      KERNEL /aubacke/vmlinuz
      APPEND initrd=/aubacke/aubacore.gz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791
```
### For GRUB

- `grub-install --root-directory=/mnt/usb/stick /dev/sdc`
- you probably have to copy some grub-files and edit the device.map
- Set the partition to active / bootable
- create menu.lst:
```
    hiddenmenu
    timeout   0
    default   0
    title AuBackE
    root (hd0,1)
    kernel /boot/vmlinuz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791
    initrd /boot/aubacore.gz
```
### For UEFI

- create GPT partition table, 2 Partitions: ~50MB VFAT and the rest as whatever 
  you like. Don't need ESP. install grub:
```
    mount /dev/sdh1 /mnt
    mkdir /mnt/boot
    mkdir /mnt/efi
    grub-install --target x86_64-efi --efi-directory /mnt/efi/ --removable --boot-directory=/mnt/boot
    cp -t /mnt/boot aubacore.gz vmlinuz
```
- Edit `/boot/grub/grub.cfg`:
```
    linux /boot/vmlinuz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791
    initrd /boot/aubacore.gz
```

### TinyCore Sheetcodes

Of course, you should modify the kernel-options to your liking, see
[TC-FAQ](http://www.tinycorelinux.net/faq.html#bootcodes)


# Bugs

If no storage-devices are present the script behaves quite bitchy, but 
it also is completely useless without any storage-device. So I won't
fix it.

At the moment, it is not possible to change from one ProfileStore to
another. The one you select at startup remains the active one forever.

Veracrypt doesn't work. (Binary won't execute in TC. Why?)

Btrfs should be work in tinycore, but doesn't mount in current version (11.x)

# ToDo

 - Internationalization 
 - Possibility to change ProfileStore on runtime
 - possibility to dump raw partition (for encrypted or unsupported partitions)
 

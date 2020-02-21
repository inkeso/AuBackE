====================================
 AuBackE - Autarkic Backup External
====================================

Ingredients
===========

*See build.sh* 

*Base:* `TinyCore Linux <http://www.tinycorelinux.net>`

build.sh includes option for 32 or 64 bit.

*Additional TCZ-Packages (placed in tcz-dir):*

- kmaps        (for supporting other then US-keyboards)
- rsync, popt  (actual backup is done using this)
- python       (for AuBackE frontend)
- parted       (detecting partitiontypes and -labels)
- filesystems      (for additional filesystem support like xfs, reiserfs, jfs etc.)
- ntfs-3g          (for supporting NTFS-partitions)
- setfont          (if you don't want the default terminal font.)
- `terminus-font <http://terminus-font.sourceforge.net>`_, or any other font. Place
  it in external-dir
- readline, ncurses, ncurses-common, ncurses-terminfo
                   (readline-support in AuBackE for a better input-experience)
- you can also include any other TCZ you want... dependencies are resolved by
  build-skript

*Actual sources are:*

- ~/.ashrc (invoking AuBackE on first login, created in build.sh)
- aubacke.py (the program itself)

*For building initial ramdisk you need:*

- cpio (for extracting the TC-ramdisk)
- 7z (for a tighter recompression, optional)

For using veracrypt, place matching cli-binary in external/$ARCH.
(Well, that was working with truecrypt, but veracrypt doesn't execute in TC. 
I don't know why. So... no veracrypt at the moment.


Building
========

Create ramdisk
--------------

For building the modified tinycore-image, edit & execute build.sh
If you have 7z you can `./build.sh release` which will recompress the
ramdisk, squeezing out a few bytes

A BUILD-dir containing all needed files is created:
- aubacore.gz (initial ramdisk)
- vmlinuz (kernel)

Prepare external drive
----------------------

You can copy them to a partition on you external drive and install a
bootloader. For example sys-/extlinux or grub.

In the examples below, the framebuffer is set to 1024x768 which is fine
for the default-font. Something lower like 800x600 will also work (I 
tried to limit the output to about 100 columns). But if you don't intend
to use this script on computers with very, very old low-res screen, I 
recomment using at least 1024x768 and/or a smaller font (see build.sh)
as you want as much output as possible visible on the screen.

For extlinux
''''''''''''

- Install the MBR to the external drive (in doku/boot/syslinux):
  ``./extlinux -i /mnt/ext3partition``
  ``./syslinux -d . -i /dev/sdc1``
- Set the partition to active / bootable
- create extlinux.conf::

    DEFAULT aubacke
    LABEL aubacke
      KERNEL /aubacke/vmlinuz
      APPEND initrd=/aubacke/aubacore.gz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791

For GRUB
''''''''

- ``grub-install --root-directory=/mnt/usb/stick /dev/sdc``
- you probably have to copy some grub-files and edit the device.map
- Set the partition to active / bootable
- create menu.lst::

    hiddenmenu
    timeout   0
    default   0
    title AuBackE
    root (hd0,1)
    kernel /boot/vmlinuz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791
    initrd /boot/aubacore.gz

For UEFI
''''''''

- create GPT partition table, 2 Partitions: ~50MB VFAT and the rest as whatever 
  you like. Don't need ESP. install grub::

    mount /dev/sdh1 /mnt
    mkdir /mnt/boot
    mkdir /mnt/efi
    grub-install --target x86_64-efi --efi-directory /mnt/efi/ --removable --boot-directory=/mnt/boot
    cp -t /mnt/boot aubacore.gz vmlinuz

- Edit /boot/grub/grub.cfg::

    linux /boot/vmlinuz loglevel=3 noswap norestore multivt kmap=qwertz/de-latin1 loop.max_loop=256 vga=791
    initrd /boot/aubacore.gz
    

TinyCore Sheetcodes
'''''''''''''''''''

Of course, you should modify the kernel-options to your liking. Here's
a sheetsheat, extracted from TinyCores bootloader::

 Color    640x480     800x600      1024x768     1280x1024
  8 bit     769         771           773          775
 15 bit     784         787           790          793
 16 bit     785         788        -> 791 <-       794
 24 bit     786         789           792          795
 
 tce={hda1|sda1}            Specify Restore TCE apps directory
 restore={hda1|sda1|floppy} Specify saved configuration location
 waitusb=X                  Wait X seconds for slow USB devices
 swapfile{=hda1}            Scan or Specify swapfile
 home={hda1|sda1}           Specify persistent home directory
 opt={hda1|sda1}            Specify persistent opt directory
 local={hda1|sda1}          Specify PPI directory or loopback file
 lst=yyy.lst                Load alternate static yyy.lst on boot
 base                       Skip TCE load only the base system
 norestore                  Turn off the automatic restore
 safebackup                 Saves a backup copy (mydatabk.tgz)
 showapps                   Display application names when booting
 vga=7xx                    7xx from table above
 xsetup                     Prompt user for Xvesa setup
 lang=en                    C only unless getlocale.tcz is installed
 kmap=us                    US only unless kmaps.tcz is installed
 text                       Textmode
 superuser                  Textmode as user root
 noicons                    Do not use icons
 noswap                     Do not use swap partition
 nodhcp                     Skip the dhcp request at boot
 noutc                      BIOS is using localtime
 pause                      Pause at completion of boot messages
 {cron|syslog}              Start various daemons at boot
 host=xxxx                  Set hostname to xxxx
 secure                     Set password
 protect                    Password Encrypted Backup
 noautologin                Skip automatic login
 tz=GMT+8                   Timezone tz=PST+8PDT,M3.2.0/2,M11.1.0/2
 settime                    Set UTC time at boot, internet required
 user=abc                   Specify alternate user
 desktop=yyy                Specify alternate window manager
 laptop                     Force load laptop related modules
 embed                      Stay on initramfs
 nozswap                    Skip compressed swap in ram
 xvesa=800x600x32           Set Xvesa default screen resolution
 bkg=image.{jpg|png|gif}    Set background from /opt/backgrounds
 blacklist=ssb              Blacklist a single module
 multivt                    Allows for multiple virtual terminals
 iso={hda1|sda1}            Specify device to search and boot an iso file


Bugs
====

If no storage-devices are present the script behaves quite bitchy, but 
it also is completely useless without any storage-device. So I won't
fix it.

At the moment, it is not possible to change from one ProfileStore to
another. The one you select at startup remains the active one forever.


ToDo
====

 - Internationalization 
 - Possibility to change ProfileStore on runtime

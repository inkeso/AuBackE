#!/bin/bash

# Build AuBackE RAM-disk (aubacore.gz)


# Argh, this needs a thorough rework. It is OLD.


# include and load terminus-font (smaller than default).
# You can use your favorite font here. just be shure to place it in the
# external-dir and the filename ends in .psf.gz
# you can also omit setfont completely and stick with the default font.

# NOTE: setfont isn't available for TC 5.x yet. So you have to manually
# download http://repo.tinycorelinux.net/4.x/x86/tcz/setfont.tcz

#FONT="ter-i12n.psf.gz"
#FONT="ter-i14n.psf.gz"
#FONT="ter-i14b.psf.gz"

# include filesystems-package for adding support for:
# cifs, hfsplus, jfs, minix, nfsd, reiserfs, udf. [0/1]
FILESYSTEMS=0

# include ntfs-3g for accessing NTFS-Partitions? [0/1]
NTFS=1

# include TrueCrypt? [0/1]
TRUECRYPT=1

# remove unused Libs/Modules from python-distribution? [0/1]
PYTHONSTRIP=1

# build in other dir (e.g. in a tmpfs-dir)
target="/tmp/AuBackE"

# bonus-packages. Readline, for example. It's nice but not needed.
BONUS="readline ncurses ncurses-terminfo"

# TinyCore version and matching kernel (currently 6.2 with Kernel 3.16.6)
KERNL=3.16.6
TCVER=6.x


# if you have 7z installed and want to recompress the final RAM-disc (so
# it will be a bit smaller in size) use "release" as a commandline
# parameter. This will take some time but it will reduce filesize by
# about 8% (see last 10 lines of this script)
#
# I always build 3 releases (repacked and stripped python-libs):
# mini - no extrafont, no extra filesystems, no truecrypt
# full - everything and ter-i14n font
# cust - ntfs and ter-i14n font
########################################################################

case "n$2" in
    nmini)
        NTFS=0
        TRUECRYPT=0
        BONUS=""
        ;;
    nfull)
        FILESYSTEMS=1
        FONT="ter-i14n.psf.gz"
        ;;
    ncust)
        TRUECRYPT=0
        FONT="ter-i14n.psf.gz"
        # A nice filemanager comes handy quite often
        BONUS="$BONUS mc slang glib2 libssh2 libgcrypt libgpg-error"
        # see below. ini-file is copied as well.
        ;;
    nultra)
        FILESYSTEMS=1
        FONT="ter-i14n.psf.gz"
        # Everything!
        BONUS="$BONUS mc slang glib2 libssh2 libgcrypt libgpg-error"
        ;;
esac



if [ `whoami` != "root" ] ; then
    echo "Run this as root"
    exit 1
fi

if [ ! -e external ] ; then
    echo "external-dir not found. creating."
    mkdir external
fi
if [ ! -e tcz ] ; then
    echo "tcz-dir not found. creating and downloading needed tczs"
    mkdir tcz
fi
if [ ! -e "external/$FONT" ] ; then
    echo "warning: Font $FONT does not exist, deactivating setfont!"
    FONT=
fi

# create tmp- and build-dirs
for l in BUILD tmp ; do
    mkdir -p "${target}/${l}"
    ln -s -t . "${target}/${l}" 2>/dev/null
done

for l in external tcz src ; do
    ln -s -r -t "${target}" "${l}" 2>/dev/null
done

cd tmp
[ $? -ne 0 ] && exit 1 # safety first.
# cleanup
rm -r *

# extract core-base.
echo "extracting core"
if [ ! -e ../external/core.gz ] ; then
    echo "core.gz not found: downloading"
    wget -nv "http://repo.tinycorelinux.net/$TCVER/x86/release/distribution_files/core.gz" -O"../external/core.gz"
fi
if [ ! -e ../external/vmlinuz ] ; then
    echo "vmlinuz not found: downloading"
    wget -nv "http://repo.tinycorelinux.net/$TCVER/x86/release/distribution_files/vmlinuz" -O"../external/vmlinuz"
fi

zcat ../external/core.gz | cpio -i -H newc -d

# extensions
intex() {
    if [ ! -e "../tcz/$1.tcz" ] ; then
        echo "Package $1 not found. Downloading..."
        wget -nv "http://repo.tinycorelinux.net/$TCVER/x86/tcz/$1.tcz" -O "../tcz/$1.tcz"
    fi
    echo "unsquashing $1"
    unsquashfs -n -f -d . "../tcz/$1.tcz" > /dev/null
}

# essential TCZ
for a in kmaps rsync popt python parted ; do
    intex $a
done

# Bonus TCZ
for a in $BONUS ; do
    intex $a
done

# optional
if [ -n "$FONT" ] ; then
    intex setfont
    # remove most of the setfont-package since we only use a single terminus-font
    rm -r usr/local/share/consolefonts/* usr/local/share/consoletrans/* usr/local/share/unimaps/*
    cp "../external/$FONT" usr/local/share/consolefonts/
    echo '
    FONT="$(basename "`ls /usr/local/share/consolefonts/`" .psf.gz)"
    setfont "$FONT"
    ' >> opt/bootsync.sh
fi

if [ $FILESYSTEMS -eq 1 ] ; then 
    # MTD is listed in the dependencies of filesystem. But it still works without(?)
    #intex mtd-$KERNL-tinycore 
    intex filesystems-$KERNL-tinycore
    echo '
    echo -en "\033[1;32mLoading additional filesystem-modules: \033[1;35m"
    for m in `find /usr/local/lib/modules/'$KERNL'-tinycore/kernel/fs -name *.ko.gz` ; do
        echo -n "`basename $m .ko.gz` "
        insmod $m 2>/dev/null
    done
    echo -e "\033[0m"
    ' >> opt/bootsync.sh
fi

if [ $NTFS -eq 1 ] ; then
    intex ntfs-3g
    echo '
    echo -en "\033[1;32mLoading \033[1;35mntfs-3g\033[0m"
    /usr/local/tce.installed/ntfs-3g
    echo -e " \033[1;32mDone\033[0m"
    ' >> opt/bootsync.sh
fi

if [ $TRUECRYPT -eq 1 ] ; then
    # truecrypt is available in TC-repos, but only with GUI. We use the console-only
    # static binary from truecrypt.org.
    
    ### TODO !!! This is no longer working...
    
    if [ ! -e ../external/truecrypt ] ; then
        echo "TrueCrypt not found. Downloading & extracting..."
        wget -nv 'http://www.truecrypt.org/download/truecrypt-7.1a-linux-console-x86.tar.gz' -O- | tar -xzf - -C "../external"
        tail -n+855 ../external/truecrypt-7.1a-setup-console-x86 | tar -xzf - -C "../external" usr/bin/truecrypt
        mv ../external/usr/bin/truecrypt ../external/truecrypt
        rm -r ../external/usr
        rm ../external/truecrypt-7.1a-setup-console-x86
    fi
    cp ../external/truecrypt usr/bin
    # but we still need fuse, lvm2 and device-mapper
    for a in fuse lvm2 liblvm2 libdevmapper udev-lib raid-dm-$KERNL-tinycore ; do
        intex $a
    done
    echo '
    echo -en "\033[1;32mLoading \033[1;35mLVM\033[0m"
    insmod /usr/local/lib/modules/'$KERNL'-tinycore/kernel/drivers/md/dm-mod.ko.gz
    /usr/local/tce.installed/lvm2
    echo -e " \033[1;32mDone\033[0m"
    ' >> opt/bootsync.sh
fi

# remove some unused python-modules. perhaps, we shouldn't do this... 
if [ $PYTHONSTRIP -eq 1 ] ; then
    echo "removing unused python-modules"
    cd usr/local/lib/python2.7
    # I don't know what this is, but it's huge and it seems like it isn't needed:
    rm config/libpython2.7.a
    # dirs & files:
    rm -r *[sS]erver* *[cC]ookie* *HTML* html* http* imap* Mime* json/tests
    rm -r __p* _p* a[sinru]* [Bb]as* bin* bs* c[aghuPst]* codeop.py code.py colo* com* Con* cont*
    rm -r di[frs]* d[beo]* dumb* em* f[ioprt]* get[pt]* glob* h[mo]* i[dhmn]* lib2* lib-t* lo* n[enu]* ntu*
    rm -r opt* p[^io]* picklet* p[io]p* rex* r[flou]* s[cegmnoqs]* sh[aeu]* statv* string[op]*
    rm -r sun* sym* ta* te[ls]* thi* ti* toa* trace.py tt* wav* web* w[hs]* [mquxz]*
    # dynlibs:
    cd lib-dynload
    rm _cod* _c[stu]* _[behjmt]* _ls* _s[oqs]* au* bz* fu* im* mm* os* res* te* c[mrP]* s[pty]* [dglnpu]*
    cd ..
    # encodings:
    cd encodings
    rm cp* iso* koi* mac* big* bz2* euc* gb* hp* hz* idna* mb* p* q* rot* shift* tis* uu* utf_16* utf_32* utf_7*
    cd ../../../../..
fi

echo "copy program files"

# always append this to boot-process
echo '
echo -e "\033[1;32mLoading python\033[0m"
/usr/local/tce.installed/python

# Set screen blank timeout & VESA powerdown to 1440 minutes (24h)
echo -en "\033[0m\033[9;1440]\033[14;1440]"

echo -e "\033[1;32mWaiting for devices...\033[0m"
sleep 5

' >> opt/bootsync.sh

# modify .ashrc to start main script upon first autologin:
echo '
if [ ! -e ~/.autostart_done ] ; then
    touch ~/.autostart_done
    cd /opt
    echo -e "import aubacke\naubacke.banner()" | python
    parted -l -m 2>&1 | tee /tmp/parted_output.txt
    sudo python /opt/aubacke.py   # Run backup
fi
' >> etc/skel/.ashrc

# copy the main program & pyon-lib
cp ../src/aubacke.py opt/

echo "Core Linux - login as user 'tc'" > etc/issue

# fix MC-function-keys, if mc.tcz is used
if [ -e "usr/local/share/mc/mc.lib" ] ; then
    cat <<EOF >> "usr/local/share/mc/mc.lib"
[terminal:linux]
f11=\\\\e[25~
f12=\\\\e[26~
f13=\\\\e[28~
f14=\\\\e[29~
f15=\\\\e[31~
f16=\\\\e[32~
f17=\\\\e[33~
f18=\\\\e[34~
EOF
fi

# update shared libs
sudo ldconfig -r .

# repack

echo "repack everything"
find | cpio -o -H newc | gzip -2 > ../BUILD/aubacore.gz
cd ..

cp external/vmlinuz BUILD

if [ "$1" == "release" ] ; then
    echo "recompressing tightly"
    cd BUILD
    gunzip aubacore.gz
    7z a -tgzip -mfb=256 -mpass=15 aubacore.gz aubacore
    rm aubacore
    cd ..
    if [ ! -e release ] ; then
        echo "release-dir not found. creating"
        mkdir release
    fi
    mv BUILD/aubacore.gz release/aubacore-$2.gz
    mv BUILD/vmlinuz release/vmlinuz

    echo "RELEASE BUILD: release/aubacore-$2.gz DONE (`wc -c <release/aubacore-$2.gz` bytes)"
else
    echo "BUILD DONE. (ramdisk size: `wc -c <BUILD/aubacore.gz` bytes)"
fi


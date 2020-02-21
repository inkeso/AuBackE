#!/bin/bash

# TODO:
# Automatic dependencies
# 64 AND 32 bit version
# Commit to Github
# test / remove veracrypt

# if you have 7z installed and want to recompress the final RAM-disc (so
# it will be a bit smaller in size) use "release" as a commandline
# parameter. This will take some time but it will reduce filesize by
# about 8% (see last 10 lines of this script)
########################################################################

# -----------------------------------------------------------------------------
# CONFIG

# include and load terminus-font (smaller than default).
# You can use your favorite font here. just be shure to place it in the
# external-dir and the filename ends in .psf.gz
# you can also omit setfont completely and stick with the default font.

#FONT="ter-i12n.psf.gz"
FONT="ter-i14n.psf.gz"
#FONT="ter-i14b.psf.gz"

ARCH="x86_64"
#ARCH="x86"

# build in other dir (e.g. in a tmpfs-dir)
target="/tmp/AuBackE"

# String "KERNEL" is beeing replaced by $KKERNL later on 
# (since there may be dependencies such as mtd-KERNEL fpr filesystems)
PACKAGES="kmaps rsync popt python parted setfont ntfs-3g filesystems-KERNEL mc"

AUBA="aubacore_$ARCH.gz"
case "$ARCH" in
    x86_64)
        CORE=corepure64.gz
        KERN=vmlinuz64
        ;;
    x86)
        CORE=core.gz
        KERN=vmlinuz
        ;;
    *)
        echo "ARCH Must be x86 or x86_64"
        exit 2
        ;;
esac

do_as_user() {
    # -------------------------------------------------------------------------
    # PRECHECK: create dirs etc.

    mkdir -p external/$ARCH
    mkdir -p tcz/$ARCH

    # create tmp- and build-dirs
    for l in BUILD tmp ; do
        mkdir -p "${target}/${l}"
        ln -s -t . "${target}/${l}" 2>/dev/null
    done

    for l in external tcz src ; do
        ln -s -r -t "${target}" "${l}" 2>/dev/null
    done

    # -------------------------------------------------------------------------
    # DOWNLOAD: TinyCore & Packages

    # get latest tinycore version
    NEWVER=$(wget -q -O - "http://www.tinycorelinux.net/" | grep "latest version" | sed "s/.*: //" | sed -re "s/<..?>|[[:space:]]//g")
    if (grep -q "[0-9]\\.[0-9]" <<<$NEWVER && [ ${#NEWVER} -gt 2 ]) ; then
        TCVER=$(sed -r "s/([0-9]+)\\../\1.x/" <<<$NEWVER)
    fi
    if [ -z "$TCVER" ] ; then
        echo -e "\e[91mError getting TinyCore Version\e[0m"
        exit 1
    fi

    echo -e "\e[96mUsing TinyCore $TCVER $ARCH\e[0m"

    TCBASE="http://repo.tinycorelinux.net/$TCVER/$ARCH/release/distribution_files"
    TCZPTH="http://repo.tinycorelinux.net/$TCVER/$ARCH/tcz"

    for ff in $CORE $KERN ; do
        if [ ! -e external/$ARCH/$ff ] ; then
            wget -nv "$TCBASE/$ff" -O"external/$ARCH/$ff"
        fi
    done

    cp external/$ARCH/$KERN BUILD

    # get kernel version
    KERNVER=$(file external/$ARCH/$KERN | sed -r 's/.*version ([^ ]+).*/\1/')

    echo -e "\e[96mDetected Kernel-version: $KERNVER\e[0m"

    newpacks=$(sed "s/ /.tcz /g" <<<$PACKAGES).tcz
    while [ $(wc -c <<<$newpacks) -gt 1 ] ; do
        echo -n >"$target/aubacke_build_dep"
        for pp in $newpacks ; do
            PKG="$(sed s/KERNEL/$KERNVER/ <<< $pp)"
            if [ ! -e tcz/$ARCH/$PKG ] ; then
                wget -nv "$TCZPTH/$PKG" -O"tcz/$ARCH/$PKG"
                wget -q "$TCZPTH/$PKG.dep" -O- | sed "s/KERNEL/$KERNVER/" >> $target/aubacke_build_dep
            fi
        done
        newpacks=$(sort $target/aubacke_build_dep | uniq)
    done
}


do_as_fakeroot() {

    # -------------------------------------------------------------------------
    # COMPILE: TinyCore & Packages - Everything in fakeroot

    echo "Extract base image $CORE ... "

    cd tmp
    [ $? -ne 0 ] && exit 1 # safety first.
    # cleanup
    rm -r *

    gzip -dc ../external/$ARCH/$CORE | cpio -i -H newc -d

    echo "Add packages ... "
    for pp in $(ls -1 ../tcz/$ARCH/$PKG) ; do
        unsquashfs -n -f -d . "../tcz/$ARCH/$pp" > /dev/null
    done

    # optional font
    if [ -n "$FONT" -a -e "../external/$FONT" ] ; then
        echo "Copy font $FONT"
        cp "../external/$FONT" usr/local/share/consolefonts/
        echo "setfont $(basename "$FONT" .psf.gz)" >> opt/bootsync.sh
    fi

    # veracrypt doesn't work at the moment, i don't know why (won't execute)
    if [ -e ../external/$ARCH/veracrypt ] ; then
        echo "Copy veracrypt (currently nonfunctional)"
        cp ../external/$ARCH/veracrypt usr/bin
    #else
    #     echo -e "\e[93mwarning: veracrypt-binary not found.\e[0m"
    #     echo "To use veracrypt, download the generic linux-installer from:"
    #     echo "https://www.veracrypt.fr/en/Downloads.html"
    #     echo "extract the CLI-binary from it and place in external/$ARCH"
    fi

    # insert tce.installed scripts
    echo '
for tce in $(ls -1 /usr/local/tce.installed) ; do
    echo -e "\033[1;32mLoading \033[1;35m$tce\033[0m"
    /usr/local/tce.installed/$tce
done

# old school - probably not needed
# echo -en "\033[1;32mLoading additional filesystem-modules: \033[1;35m"
# for m in `find /usr/local/lib/modules/*/kernel/fs -name *.ko.gz` ; do
#     echo -n "`basename $m .ko.gz` "
#     insmod $m 2>/dev/null
# done
# echo -e "\033[0m"

# Set screen blank timeout & VESA powerdown to 1440 minutes (24h)
echo -en "\033[0m\033[9;1440]\033[14;1440]"

echo -e "\033[1;32mWaiting for devices...\033[0m"
sleep 2

' >> opt/bootsync.sh

    # copy the main program
    echo "Copy program files"
    cp ../src/aubacke.py opt/

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
    ldconfig -r .

    # repack
    echo "repack everything"
    find | cpio -o -H newc | gzip -2 > ../BUILD/$AUBA
    echo -e "\e[92mCOMPILE DONE.\e[0m (ramdisk size: `wc -c <../BUILD/$AUBA` bytes)"
    cd ..
}

do_release() {
    echo "recompressing tightly"
    cd BUILD
    gunzip $AUBA
    unp=$(basename $AUBA .gz)
    7z a -tgzip -mfb=256 -mpass=15 $AUBA $unp
    rm $unp
    cd ..
    if [ ! -e release ] ; then
        echo "release-dir not found. creating"
        mkdir release
    fi
    mv BUILD/$AUBA release/$AUBA
    mv BUILD/$KERN release/$KERN
    echo "RELEASE BUILD: release/$AUBA DONE (`wc -c <release/$AUBA` bytes)"
}


if [ -z "$1" ] ; then
    do_as_user
    fakeroot $0 do_fakeroot
fi

if [ "$1" == "do_fakeroot" ] ; then
    do_as_fakeroot
fi

if [ "$1" == "release" ] ; then
    do_release
fi

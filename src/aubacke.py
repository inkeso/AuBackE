#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#  
#-----------------------------------------------------------------------
#  AuBackE - Autarkic Backup External
#-----------------------------------------------------------------------
#  
#  Copyright 2013 Vitius Ponti <errorpriester@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#-----------------------------------------------------------------------
#
# for testing in qemu (or different box) use pusher.py.

import sys, os, re
import json, gzip, time
import subprocess, threading, Queue, shlex


## GLOBAL FUNCTIONS ##

def cp(string, colorcode="0"):
    '''
    Simplest unbuffered color printer
    '''
    sys.stdout.write("\033["+colorcode+"m"+string+"\033[0m")
    sys.stdout.flush()

def heading(string, color="1"):
    '''
    format a delicious heading
    '''
    cp(" ┌"+(len(string)+2)*"─"+"┐\n", "1;30")
    cp(" │ ","1;30")
    cp(string, color)
    cp(" │\n","1;30")
    cp(" └"+(len(string)+2)*"─"+"┘\n\n", "1;30")

def banner():
    '''
    clear screen, show banner
    '''
    # Using 800x600 (mode 788) and default-font there are 100 columns available.
    # ─│┌┐└┘├ ┤ ┬ ┴ ┼ ═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬ ▀▄ █▌▐░▒▓■▬▲▶▼◀◆○
    cp("\033[H\033[2J") # clear screen
    cp("            │ "+           "                                          "+              " │          \n","1;30")
    cp("            │╔"+           "══════════════════════════════════════════"+              "╗│          \n","1;30")
    cp("            └╢","1;30");cp("                                          ","1;33;44");cp("╟┘          \n","1;30")
    cp("             ║","1;30");cp("       ┌──┐     ┌┐         ┬┌  ┌──        ","1;33;44");cp("║           \n","1;30")
    cp("             ║","1;30");cp("       ├──┤ ┬ ┬ ├┴┐ ┌─┐ ┌─ ├┴┐ ├─         ","1;33;44");cp("║           \n","1;30")
    cp("             ║","1;30");cp("       ┴  ┴ └─┘ └─┘ └─┴ └─ ┴ └ └──        ","1;33;44");cp("║           \n","1;30")
    cp("             ║","1;30");cp("       Autarkic   Backup   External       ","1;34;44");cp("║           \n","1;30")
    cp("             ║","1;30");cp("                                          ","1;33;44");cp("║           \n","1;30")
    cp("             ╚"+           "══════════════════════════════════════════"+              "╝           \n","1;30")
    cp("\n")

try: import readline # nice but not mandantory
except: cp("readline support disabled", "1;30")

def vinput(message, vlist, pcol="0"):
    '''
    Display a Message and raw_input a value.
    If the value isn't in vlist, show error and repeat.
    If vlist is None, no validation is done.
    Additionally, there's magic in here. Watch out!
    '''
    # create prompt
    prompt = "▶ "
    pre = ""
    # if all items in vlist start with the same substring, that part is
    # used as a string. Otherwise, we'll just use an arrow
    # This is a bit dirty, but very efficient
    i=0
    try:
        vlm = map(lambda x: [x[i] for i in range(len(x))], vlist)
        while True:
            if any(map(lambda x: x[i] != vlm[0][i], vlm)):
                raise Exception
            i += 1
    except:
        pass
    if i > 0: 
        pre = vlist[0][:i]
        prompt += pre
    
    # main input-loop
    valid = False
    while not valid:
        cp(message+"\n")
        inp = pre+raw_input("\033["+pcol+"m"+prompt+"\033[1;"+pcol+"m")
        cp("")
        if not vlist or inp in vlist:
            valid = True
        else:
            cp("Invalid value.\n","31")
            cp("(Try one of those: " + ", ".join(map(lambda x: x[i:], vlist)) + ")\n")
    return inp

def cmd(s):
    '''
    execude a shellcommand. return stdout/stderr
    '''
    if type(s) == str: s = shlex.split(s)
    if type(s) == tuple: s = list(s)
    try:
        return subprocess.check_output(s, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return "ERROR " + str(e.returncode) + ": " + str(e.output)


class Device():
    '''
    a simple class for partitions.
    '''
    def __init__(self, dev, label, uuid, fstype):
        '''
        fill all properties, mount partition, get free space.
        '''
        # everything is string
        self.dev    = dev    # device-node of partition
        self.uuid   = uuid   # uuid of partition (from blkid)
        self.fstype = fstype # type of filesystem according to blkid
        self.label  = label  # label or uuid.
        self.mount  = None   # mountpoint named by label or uuid
        self.free   = None   # set by getFreeSpace()
        self.used   = None   # set by getFreeSpace()
        self.size   = None   # set by getFreeSpace()
        
        # labels may not be unique, but the storage-class takes care of that
        if label:
            # sanitize label. (some weirdos use funky chars)
            self.label = re.sub("[^A-Za-z0-9_-]", "_", self.label)
            self.mount = "/mnt/" + self.label
        else:
            self.label = self.uuid
            self.mount = "/mnt/" + self.uuid
        
        self.doMount()
        self.getFreespace()
    
    def __del__(self):
        '''
        unmount on class-destruction (i.e. program ending)
        '''
        self.doUnmount()
    
    def isMounted(self):
        for l in cmd("mount").split("\n"):
            tok = l.split()
            # check by device (and set mountpoint if necessary)
            if len(tok) > 2 and self.dev == tok[0]: 
                self.mount = tok[2]
                return True
            # check by mountpoint (in case of veracrypt, device is a loopback)
            if len(tok) > 2 and self.mount == tok[2]: 
                return True
        return False
    
    def doMount(self):
        if not self.mount: 
            cp("$ " + self.dev + " has no mountpoint\n")
            return False
        if self.isMounted(): 
            cp("$ " + self.dev + " already mounted to " + self.mount + "\n")
            return True
        if not os.path.exists(self.mount): os.makedirs(self.mount)
        
        # In case of veracrypt, we don't use the normal mountcommand
        if self.fstype=="veracrypt":
            tca = vinput ("Additional veracrypt-arguments (like --filesystem=ntfs-3g for encrypted NTFS-partitions):",None)
            mc = "veracrypt -m=nokernelcrypto "+tca+" "+self.dev+" "+self.mount
            return os.system(mc) == 0
        
        mountcmd = ["mount"]
        # this is a fix for ntfs-3g. needed for TC, since busybox-mount
        # can't detect ntfs-3g on its own. And we DON'T use /etc/fstab
        if self.fstype=="ntfs": mountcmd += ["-t", "ntfs-3g"]
        
        # cp("$ mount " + self.dev + " to " + self.mount + "\n", "1;30")
        cp(self.dev.replace("/dev/","") + " ", "1;30")
        targ = cmd(mountcmd + [self.dev, self.mount])
        if len(targ.strip()) > 0:
            cp("\nMOUNT said: ", "1;33")
            cp(targ)
            return False
        else:
            return True
    
    def doUnmount(self):
        if self.isMounted():
            cp("$ unmount " + self.dev + "\n", "1;30")
            if self.fstype == "veracrypt":
                targ = cmd(["veracrypt", "-d", self.dev])
            else:
                targ = cmd(["umount", self.dev])
            if len(targ.strip()) > 0:
                cp("UNMOUNT said: ", "1;33")
                cp(targ+"\n\n")
                return False
            else:
                return not self.isMounted()
        else:
            return True
    
    def getFreespace(self):
        try:
            cmd("sync")
        except Exception:
            pass
        df = cmd("df -h " + self.mount).split("\n")[1].split()
        self.free = df[3]
        self.used = df[2]
        self.size = df[1]
    
    def ls(self):
        '''
        show file-count and directory-listing. (1. Level only)
        This is nice and all, but (currently) never used.
        '''
        dirs = []
        fils = []
        for l in os.listdir(self.mount):
            if os.path.isdir(l): 
                dirs.append(l)
            else:
                fils.append(l)
        dirs.sort()
        heading(self.dev)
        cp(self.mount, "32")
        cp(": "+len(fils)+" files and these directories:\n")
        cp("\n".join(dirs)+"\n")


class Storage():
    '''
    Contains Storage-devices (HDs) and partitions
    '''
    def __init__(self):
        '''
        structured representation of all available storage devices (disks and
        partitions) using:
        
        - "blkid" for dev, label/uuid and type 
        - "parted -l -m" for drive-model and size (drive and partitions)
        
        self.hd = { '/dev/sda': {
                        SIZE: "120GB", 
                        MODEL: "Intel SSD", 
                        PARTITIONS: [List of Device-instance (mounted partitions)]
                    },
                   '/dev/sdb': { ... }
        }
        
        also 2 simpler dicts of Device-instances are available:
        self.devs and self.uuids
        
        [[TODO]] partition-labels may not be unique. take care of that!
        '''
        
        self.hd    = {}     # a complete representation of all installed disks
        self.devs  = {}     # also, for convinience, there are dicts of devs and
        self.uuids = {}     # uuids (as keys) and Device-instances as values

        hdtmp = {}
        labels = []         # keep a temporary list of labels to avoid duplicates
        
        for l in cmd("blkid").split("\n"):
            if l.find(":") < 0: continue
            ddat = dict(re.findall("([A-Z]+?)=\"(.+?)\"", l))
            # ignore swap, CD and squashFS:
            if not "TYPE" in ddat.keys(): ddat['TYPE'] = "unknown"
            if ddat['TYPE'] in ("swap", "iso9660", "squashfs", "unknown"): continue
            # ignore if no label and no uuid:
            if "LABEL" not in ddat.keys() and "UUID" not in ddat.keys(): continue
            # use UUID as label when no label is present (this is also done in Device()
            # but we need it here as well, because checking for duplicates.
            if "LABEL" not in ddat.keys(): ddat['LABEL'] = ddat['UUID']
            
            if ddat['LABEL'] in labels:
                i = 1;
                while (ddat['LABEL'] + "_" + i) in labels: i+=1
                ddat['LABEL'] = ddat['LABEL'] + "_" + i
            
            dev = l.split(":")[0]
            newd = Device(dev, ddat['LABEL'], ddat['UUID'], ddat['TYPE'])
            if newd.isMounted(): # do not include if mounting fails
                self.devs[dev] = newd
                self.uuids[self.devs[dev].uuid] = newd
        
        ptv = [] # aggregate Possible veracrypt Volumes
        current = ""
        # sometimes parted needs interaction. so we execute it (in autostart) 
        # before launching this script and write the output to a file (and stdout)
        # see build.sh
        #for l in cmd("parted -l -m").split("\n"):
        parted_output = open("/tmp/parted_output.txt", "r")
        for l in parted_output:
            t = l.split(":")
            if (l.find("swap") > -1) or (len(t) < 5): 
                # omit swap-partitions and non-partition-lines (such as "BYT;")
                continue
            
            if t[0].startswith("/dev/"):
                current = t[0]
                hdtmp[current] = { "SIZE": t[1], "MODEL": t[6], "PARTITIONS": [] }
            else:
                if current + t[0] in self.devs.keys():
                    hdtmp[current]['PARTITIONS'].append(self.devs[current + t[0]])
                else:
                    # partitions without a known FS (not listed by blkid)
                    # may be veracrypt-volumes, but omit extended partition
                    if not "PTTYPE" in cmd("blkid -p -s PTTYPE "+current+t[0]):
                        ptv.append({'DEV': current+t[0], 'START': t[1], 'SIZE':t[3]})
        parted_output.close()
        # remove disks with no partitions
        for (k,v) in hdtmp.items(): 
            if len(v['PARTITIONS']) > 0: self.hd[k] = v

        # if veracrypt is available, ask for veracrypt-devices
        if os.path.exists("/usr/bin/veracrypt"):
            cp("\n")
            heading("veracrypt available. You may now mount your encrypted volumes.")
            self.show()
            # if there are unmounted & unknown partitions left, show them
            if ptv: cp("◆ Unknown (possibly veracrypt) partitions:\n","1;33")
            for d in ptv: 
                cp(d['DEV'],"36")
                cp(" starting at ")
                cp(d['START'], "1")
                cp(" and is ")
                cp(d['SIZE'], "1")
                cp(" long.\n")
            # ask for veracrypt mount
            while True:
                tcdev = vinput("\nMount veracrypt-device or -file (full path; Enter to cancel)", None)
                if tcdev == "": break
                tcmnt = vinput("Label or name", None)
                newd = Device(tcdev, tcmnt, "veracrypt-"+tcmnt, "veracrypt")
                if newd.isMounted():
                    self.devs[newd.dev] = newd
                    self.uuids[newd.uuid] = newd
                    if not "Other" in self.hd.keys():
                        self.hd['veracrypt'] = { 'SIZE': "mounted", 'MODEL': "", 'PARTITIONS': [] }
                    self.hd['veracrypt']['PARTITIONS'].append(newd)
                    cp("◆ OK ", "1;30"); cp(tcdev, "36"); cp(" ══▶ "); cp(tcmnt, "36");
            banner()
        
    
    def show(self):
        '''
        pretty printing of all discovered devices
        '''
        heading("Available Storage Devices")
        ksort = self.hd.keys()
        ksort.sort()
        for k in ksort:
            v = self.hd[k]
            cp(k,"1;36")
            cp(" is ")
            cp(v['SIZE'],"1;34")
            cp(" - ")
            cp(v['MODEL'],"1;34")
            cp("\n")
            npart = len(v['PARTITIONS'])
            L = "├─"
            for i in range(npart):
                tp = v['PARTITIONS'][i]
                if i == (npart - 1): L = "└─"
                label = tp.label
                cp(L, "1;30")
                cp(tp.dev, "36")
                cp(" ══▶ ")
                cp(tp.mount[0:5],"32")
                cp(tp.mount[5:],"1;32")
                cp(" (")
                cp(tp.fstype, "1")
                cp("; ")
                cp(tp.used,"1")
                cp(" of ")
                cp(tp.size,"1")
                cp(" used; ")
                cp(tp.free,"1")
                cp(" free)\n")
            cp("\n")


class Profile():
    '''
    This class stores one profile. Profiles are kept in a list in main()
    (and pickled through the sessions)
    Also the main part (launching rsync) is done here.
    '''
    done = False # setting this as a class-variable is a work-around.
    def __init__(self, sd, base=None):
        '''
        interactively create a new profile, based on the given Storage
        '''
        self.name = None     # set by rename
        self.steps = []      # list of dicts: {sourcedev: "UUID", sourcedir: "/path", 
                             #                 targetdev: "UUID", targetdir: "/path", 
                             #                 option: "parameters"}
        self.shutdown = ""   # set by toggleshutdown
        self.done = False    # will be set to True after execute()
        self.sd = sd         # we also have our (current) storage here.
        
        if base is None: # this is a new one
            heading("Create new profile")
            self.rename()
        else:        # this one is loaded from a previous session
            self.name = base['name']
            self.steps = base['steps']
            self.shutdown = base['shutdown']
    
    def __del__(self):
        '''
        check wheter this profile was executed an shutdown-flag is set.
        if it is, well, than the computer will be shut down.
        '''
        if self.done and self.shutdown:
            for i in range(15):
                cp("Shutdown in " + str(15 - i) + " seconds " + chr(13) ,"31")
                cmd("sleep 1")
            cp("◆ Shutdown initiated ("+self.shutdown.encode("ascii", "replace")+")      \n\n", "1;31")
            cmd(self.shutdown)
    
    def __getstate__(self):
        '''
        getstate and setstate are used for (un)pickling the instances of
        this class. The Storage-instance isn't stored. And a unpickled
        profile is always NOT done.
        '''
        state = {"name" : self.name,
                 "shutdown": self.shutdown,
                 "steps" : self.steps
        }
        return state
    
    def __setstate__(self, state):
        self.name = state["name"]
        self.shutdown = state["shutdown"]
        self.steps = state["steps"]
        self.sd = None    # must be reassigned "from outside" after unpickling
        self.done = False # loaded profiles are not done yet
    
    def modify(self, cls=True):
        '''
        show modify-menu. profile-tasks (renaming, executing, etc) can 
        be launched from here.
        '''
        self.done = False
        funmap = {
            ''  : self.execute,
            'a' : self.add,
            'd' : self.delete,
            't' : self.toggleshutdown,
            'r' : self.rename,
            'n' : banner,
        }
        ci = "?"
        while ci != "n" and ci != "":
            self.show(cls)
            cls = True # only one time no clear.
            cp("\n")
            cp("(");cp("A","1");cp(")dd command  ")
            cp("(");cp("D","1");cp(")elete command  ")
            cp("(");cp("T","1");cp(")oggle shutdown  ")
            cp("(");cp("R","1");cp(")ename profile  ")
            cp("(");cp("N","1");cp(")ext or new profile\n")
            cp("(");cp("Enter","1");cp(") start doing all this\n\n")
            ci = vinput("", funmap.keys(), "1")
            funmap[ci]()
    
    def rename(self):
        self.name = vinput("Please enter a name for this profile (e.g. the hostname)", None)
    
    def add(self):
        '''
        append a rsync-command
        '''
        self.sd.show()
        srcdev = vinput("Which partition do you want to backup?", self.sd.devs.keys(), "36")
        cp("\n")
        src=""
        while src == "":
            srcdir = vinput("Which subdirectory? (Leave empty to backup the hole partition)", None, "32")
            if len(srcdir) > 0 and not srcdir.startswith("/"): srcdir = "/" + srcdir
            src = self.sd.devs[srcdev].mount + srcdir
            if not os.path.exists(src):
                cp ("Source path ", "31")
                cp (src, "31;1")
                cp (" does not exist.\n", "31")
                src = ""
        
        cp("OK. Source is ", "32")
        cp(src, "1;32")
        cp("\n\n")
        
        dstdev = vinput("On which partition do you want to store the backup?", self.sd.devs.keys(), "36")
        snam = self.name.replace(" ","_").lower() # suggested name
        cp("\n")
        dstdir = vinput("Store Backup in a subdirectory? (I suggest \""+snam+"\").", None, "32")
        if len(dstdir) > 0 and not dstdir.startswith("/"): dstdir = "/" + dstdir
        cp("OK. Destination is ", "32")
        vdst = self.sd.devs[dstdev].mount + dstdir
        if not srcdir.endswith("/"): vdst += srcdir
        cp(vdst, "1;32")
        if not os.path.exists (vdst):
            cp("\nDestination path doesn't exist. It will be created.","33")
        cp("\n\n")
        
        sugg = "-avh --del"
        if self.sd.devs[dstdev].fstype in ["veracrypt", "vfat"]:
            sugg += " --no-g --no-o"
        option = vinput("Now specify rsync-options. (I suggest \""+sugg+"\"). See rsync --help for more details.\n"+
                        "(Hint: you can switch to another terminal using Alt+F2)", None, "33")
        
        self.steps.append({'sourcedev': self.sd.devs[srcdev].uuid, 'sourcedir': srcdir,
                           'targetdev': self.sd.devs[dstdev].uuid, 'targetdir': dstdir,
                           'option': option})
    
    def delete(self):
        '''
        delete item (rsync-command) from list
        '''
        items = map(lambda x: str(x+1), range(len(self.steps)))
        what = vinput("Which item do you want to delete? (Enter to cancel)", [""] + items, "31")
        if what != "": del self.steps[int(what)-1]
    
    def toggleshutdown(self):
        '''
        toggle through poweroff, reboot and nothing.
        '''
        items = ("", "poweroff", "reboot")
        self.shutdown = items[(items.index(self.shutdown) + 1) % len(items)]
    
    def show(self, cls=True):
        '''
        show current profile & steps
        '''
        if cls: banner()
        heading("Profile: "+self.name)
        for i in range(len(self.steps)):
            # list of dicts: {sourcedev: UUID, sourcedir: "/path", 
            #                 targetdev: UUID, targetdir: "/path", 
            #                 option: "parameters"}
            cp (str(i+1)+") ")
            e = self.steps[i]
            cp (self.sd.uuids[e['sourcedev']].mount + e['sourcedir'], "32")
            cp (" ══▶ ")
            cp (self.sd.uuids[e['targetdev']].mount + e['targetdir'], "32")
            cp ("  " + e['option'] + "\n", "33")
        if self.shutdown: 
            cp("   Shutdown ("+self.shutdown+") when finished.\n", "33")
    
    def execute(self):
        '''
        main purpose of this whole script: run rsync
        '''
        # you can design all kinds of 1-line-"animation" here...
        # the simples case:
        # spin = ["\\\r", "|\r", "/\r", "─\r"]
        # or a sophisticated one:
        
        fg = "35" # Foreground. Violet, in this case
        bg = "44" # Background. Blue, in this case
        wt = 25   # Width
        pre = "  \033[1;30m▐\033[" + bg + "m"
        pst = "\033[0;1;30m▌\033[0m" + chr(13)
        
        chr1 = ["\033[0;"+fg+";"+bg+"m░",
                "\033[0;"+fg+";"+bg+"m▒", "\033[1;"+fg+";"+bg+"m▒",
                "\033[1;"+fg+";"+bg+"m▓", "\033[1;"+fg+";"+bg+"m█"]
        chr2 = chr1[:-1]
        chr2.reverse()
        chrz = chr1 + chr2

        spin = []
        
        for j in range(len(chrz) / 2, len(chrz)):
            spin.append(pre + "".join(chrz[(-1 - j):]) + (" "*(wt-j+len(chrz)-2)) + pst)

        for j in range(wt):
            spin.append(pre + (j*" ") + "".join(chrz) + (" "*(wt-j-1)) + pst)

        for j in range(len(chrz) / 2):
            spin.append(pre + (" "*(wt+j-1)) + "".join(chrz[:(len(chrz)-j)]) + pst)

        spin2 = spin[:-1]
        spin2.reverse()
        spin += spin2
        
        def enqueue_output(out, outQ, err, errQ):
            for line in iter(out.readline, b''):
                outQ.put(line.strip())
            out.close()
            for line in iter(err.readline, b''):
                errQ.put(line.strip())
            err.close()
        
        for e in self.steps:
            rsync = "rsync " + e['option'] + " " + \
                    "\"" + self.sd.uuids[e['sourcedev']].mount + e['sourcedir'] + "\" " + \
                    "\"" + self.sd.uuids[e['targetdev']].mount + e['targetdir'] + "\""
            cp("\n◆ "+rsync.encode("ascii", "replace")+"\n", "33")
            
            proc = subprocess.Popen(shlex.split(rsync), bufsize=1,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            oQ = Queue.Queue()
            eQ = Queue.Queue()
            t = threading.Thread(target=enqueue_output, args=(proc.stdout, oQ, proc.stderr, eQ))
            t.daemon = True # thread dies with the program
            t.start()
            
            # two counters (new & deleted files) and 2 status-lines
            newc = -1 # start with -1 because first line from rsyncs
                      # output is "sending incremental file list"
            delc = 0
            sent = ""
            total = ""
            a = 0
            # write log to tmp-file (because rsync would probably delete it at dst)
            log = gzip.open("/tmp/aubacke.log.gz", "w")
            sc = 0 # spin-counter
            lc = 0 # last time i spinned
            while t.is_alive() or not (oQ.empty() and eQ.empty()):
                stderr = ""
                stdout = ""
                try: # ERROR ?
                    stderr = eQ.get(False)
                    if len(stderr) > 0: 
                        cp("│ ", "33")
                        cp(stderr + "\n", "31")
                        log.write("ERROR: " + stderr + "\n")
                except Queue.Empty: 
                    pass
                
                try: # SOMETHING ?
                    stdout = oQ.get(True, timeout=.2)
                    if len(stdout) > 0:
                        log.write(stdout + "\n")
                        if stdout.startswith("deleting "): 
                            delc += 1
                        elif stdout.startswith("sent "):
                            sent = stdout
                        elif stdout.startswith("total "):
                            total = stdout
                        else:
                            newc += 1
                    # SPIN! But don't spin too often because terminal-
                    # output can be a bottleneck.
                    
                    tens = int(time.time() * 10)
                    if tens != lc:
                        lc = tens
                        sc += 1
                        cp(spin[sc % len(spin)])
                    
                except Queue.Empty: 
                    pass
            # finished, print summary and copy logfile from tmp to dst
            log.close()
            total += " ("+str(newc)+" new files, "+str(delc)+" deleted)"
            cp("│ ", "33"); cp(sent + "\n")
            cp("│ ", "33"); cp(total + "\n")
            cp("└ ","33")
            
            # construct a meaningfull logfile-name and copy it from tmp
            ttrg = self.sd.uuids[e['sourcedev']].mount + e['sourcedir']
            ttrg = ttrg.replace("/mnt/","").replace("/","_")
            logfile = self.sd.uuids[e['targetdev']].mount + e['targetdir'] + \
                    "/rsync_"+ttrg+"_"+cmd("date +%y%m%d").strip() + ".log.gz"
            # we need to do this, since JSON.load always creates unicode-strings
            logfile = logfile.encode("ascii", "replace")
            cmd("mkdir -p \"" + logfile[:logfile.rindex("/")]+"\"").strip()
            cmd("cp /tmp/aubacke.log.gz \""+logfile+"\"")
            
            cp("Finished. Log written to " + logfile + " \n","32")
        cp("\n")
        heading(" " * 30 + "ALL DONE" + " " * 30, "1;32")
        self.done = True
    
    def matches(self, sd):
        '''
        return True, if all Devices, used in this profile, are present
        in the given Storage-instance.
        '''
        usid = {}
        for s in self.steps:
            usid[s['sourcedev']] = True
            usid[s['targetdev']] = True
        pres = map(lambda x: x in sd.uuids.keys(), usid.keys())
        return all(pres)


class ProfileStore():
    '''
    This class does profile-management. load/save profile to a file, 
    add, remove and match profiles against local storage
    '''
    def __init__(self, sd, PROFILE="/aubacke.profiles.gz"):
        '''
        this function is used to discover the file where the profiles are 
        pickled. If several profile-stores (i.e. files named PROFILE) are found,
        you can interactively select one.
        '''
        self.filename = None  # Where to store the profiles
        self.profiles = []    # main list of available profiles
        self.current  = None  # currently choosen/active profile
        self.sd       = sd    # pointer to Storage-instance
        self.skipsave = False # set to True to disable autosaving on exit
        
        prostore = []
        devs = sd.devs.keys()
        devs.sort()
        for k in devs:
            pf = sd.devs[k].mount + PROFILE
            if os.path.exists(pf): prostore.append(pf)
        if len(prostore) == 0:
            cp("◆ No profile-store found.\n\n","1;33")
            sd.show()
            tdev = vinput("On which device do you want me to store the profiles?", sd.devs.keys(), "36")
            banner()
            cp ("Your profiles will be stored to: ")
            cp (sd.devs[tdev].mount + PROFILE, "32")
            self.filename = self.sd.devs[tdev].mount + PROFILE
            cp("\n\n")
        elif len(prostore) == 1:
            cp("◆ Profile-store found: " + prostore[0] + "\n", "33")
            self.filename = prostore[0]
            self.load()
        else:
            cp("◆ More than one profile-store found.\n\n","33")
            what = zip(map(lambda x: str(x+1), range(len(prostore))),prostore)
            for k,v in what: cp(k + ") " + v + "\n")
            what = dict(what) 
            dit = what[vinput("\nWhich one should i use?", what.keys(), "0")]
            self.filename = dit
            banner()
            self.load()
    
    def __del__(self):
        '''
        Destroy all profile-instances
        '''
        if not self.skipsave: self.save()
        del self.current
        for p in self.profiles: del p
    
    def load(self):
        '''
        load all profiles from file, determined by init. Since i don't know how
        to get a new instance of a class and set some vars, I modified the 
        Profile-constructor to also allow loading.
        '''
        self.profiles = []

        try:
            with gzip.open(self.filename, "r") as f:
                lop = json.load(f) # list of profile-dicts (see Profile.export)
            for li in lop: self.profiles.append(Profile(self.sd, li))
        except Exception, e:
            cp("◆ Loading Profiles from "+self.filename+" failed: "+str(e)+"\n","1;33")
    
    def save(self):
        '''
        store all profiles to file (gziped JSON). We have to "convert" the 
        profile to a simple dict. This could also be done in (static) class-
        functions, so that the conversion is handled by json.dump itself.
        '''
        if self.filename is None: return
        lop = []
        for li in self.profiles: 
            lop.append({"name": li.name, 
                        "steps": li.steps, 
                        "shutdown": li.shutdown})
        
        try:
            cp("◆ Writing Profiles to " + self.filename + "\n","33")
            with gzip.open(self.filename, "w") as f: 
                json.dump(lop, f, indent=2, separators=(',', ': '), sort_keys=True)
        except Exception, e:
            cp("◆ Saving Profiles to "+self.filename+" failed: "+str(e)+"\n","1;33")
    
    def getMatching(self):
        '''
        find matching profiles, if only one is matching: set self.current to it.
        returns a list of tuples with readable keys and profile index:
        [("1", 0), ("2", 4), ...]
        '''
        prom = []
        i = 0
        for p in range(len(self.profiles)):
            if self.profiles[p].matches(self.sd): 
                i += 1
                prom.append((str(i), p))
        return prom
    
    def select(self, idx):
        '''
        select a profile by index. (also reassign Storage-instance)
        '''
        self.current = self.profiles[idx]
        self.current.sd = self.sd
    
    def delete(self, idx):
        '''
        delete whole profile
        '''
        self.profiles[idx].show()
        cp("\n\nReally delete this profile?", "1;31")
        if vinput("", ("yes","no",""), "31") == "yes": 
            del self.profiles[idx]
            self.current = None
        
    def add(self):
        '''
        create a new profile, append it to the list and set it to current
        '''
        self.current = Profile(self.sd)
        self.profiles.append(self.current)
        

def main():
    if os.getuid() > 0: 
        cp("Must be root.\n")
        return 1
    
    banner()
    cp ("Mounting ","1;30")
    stor = Storage() 
    cp("\n")
    prof = ProfileStore(stor)

    ## MAIN LOOP / MENU
    what = "?"
    while True:
        mp = prof.getMatching()
        cls = True 
        
        if not mp: # no profile found: create a new one
            what = "c"
        elif len(mp) == 1 and what == "?": # one profile matches. choose it (one time!)
            what = "1"
            cls = False # don't clear screen in case of auto-select.
        else:
            heading("Select profile")
            for k, v in mp: cp(k+") " + prof.profiles[v].name + "\n")
            cp("\n")
            cp("c) Create new profile\n")
            cp("d) Delete existing profile\n")
            cp("x) Exit AuBackE\n")
            what = vinput("", zip(*mp)[0] + ("c","d","x"))
        
        if what == "c": 
            prof.add()
        elif what == "d":
            lm = vinput("Which profile do you want to delete? (Enter to abort)", zip(*mp)[0] + ("",), "31")
            if (lm): prof.delete(dict(mp)[lm])
        elif what == "x": 
            break
        else:
            prof.select(dict(mp)[what])
        
        if prof.current:
            prof.current.modify(cls)
            prof.save()
            if (prof.current.done and prof.current.shutdown):
                # profile was just stored, we don't need to do it again
                prof.skipsave=True
                break
        
    ## CLEANUP
    # saving profiles is done in ProfileStore-destructor (also destructs all Profiles)
    # shutdown (if set in Profile) is invoked via Profile-destructor.
    # unmounting of all partitions is done in Device-destructor
    # since all Devices are part of Storage, they will be destructed too.
    #
    # deleting these isn't really neccessary (as python does this on its own),
    # but i include it anyway for good readability.
    del prof
    del stor
    
    return 0

if __name__ == '__main__': main()


'''
 Flow:
 
 - get currently installed storage-devices, create 1 instance of 
   Storage, containing several instances of Device
 - create a ProfileStore instance. On init, it looks on all mounted
   Devices for a stored profile ("aubacke.profiles.gz") which is a 
   gziped JSON textfile.
   If more than one is found, user will be asked which one to use.
   If none is found, one is created.
 - a ProfileStore contains a list of Profile instances.
 - each Profile-instance contains a list of steps.
 - on init, if a ProfileStore is loaded from file, containing several
   Profiles, only the matching one(s) are shown. By matching I mean,
   the used UUIDs (or labels, if UUIDs are not available, which is the
   case for veracrypt-volumes) in all steps of a profile are compared
   to the currently existing UUIDs from Storage.

'''

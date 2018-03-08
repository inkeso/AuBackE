#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  pusher.py
#
# This is meant for debugging, a simple server that answers each request
# with the content of "aubacke.py", so we don't have to repack the 
# ramdisk & restart qemu (or whatever) every time we change something.
#
# We cannot use a real debugger, but in this case a few extra prints
# will be sufficient.

CONNECTION = ("127.0.0.1", 6677)

import SocketServer

class AHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        #s = self.request.recv(1024)
        f = open("src/aubacke.py", "r")
        for line in f: self.request.send(line)
        f.close()
        self.request.send("#")
        

server = SocketServer.ThreadingTCPServer(CONNECTION, AHandler)
print "On QEMU-client use: telnet 10.0.2.2 6677 > tmp ; sudo python tmp"

server.serve_forever()

## Im going through changes

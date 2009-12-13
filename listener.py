#!/usr/bin/python

import asynchat
import asyncore
import socket

class Handler(asynchat.async_chat):
    def __init__(self, server, (conn, addr)):
        asynchat.async_chat.__init__(self, conn)

        self.set_terminator('\n')
        self.server = server
        self.buffer = ''

    def collect_incoming_data(self, data):
        self.buffer += data

    def found_terminator(self):
        print self.buffer
        self.buffer = ''

class Listener(asyncore.dispatcher):
    def __init__(self, port=12345):
        asyncore.dispatcher.__init__(self)
        self.port = port

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', self.port))
        self.listen(5)

    def handle_accept(self):
        Handler(self, self.accept())

Listener()
asyncore.loop()
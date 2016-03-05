#!/usr/bin/python

from twisted.internet import protocol, reactor, endpoints
from twisted.protocols.basic import LineReceiver


import json
import logging
import time
import datetime
import re
import sys

SERVERS = {
    'Alford'   : 14560,
    'Bolden'   : 14562,
    'Hamilton' : 14564,
    'Parker'   : 14566,
    'Welsh'    : 14568,
}

COMM = {
    'Alford'   : ['Parker', 'Welsh'],
    'Bolden'   : ['Parker', 'Welsh'],
    'Hamilton' : ['Parker'],
    'Parker'   : ['Alford', 'Bolden', 'Hamilton'],
    'Welsh'    : ['Alford', 'Bolden'],
}

API_KEY = 'AIzaSyD7jJGM_xBuQHpIzGtFqN2bQa8P40mAHyo'
PLACES_URL = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?'

class ChatserverReceiver(LineReceiver):
    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        self.factory.numConnections = self.factory.numConnections + 1
        logging.info("New connection made: now at %d connections" % self.factory.numConnections)

    def connectionLost(self, reason):
        self.factory.numConnections = self.factory.numConnections - 1
        logging.info("Connection lost: now at %d connections" % self.factory.numConnections)

    def lineReceived(self, line):
        param = line.split(' ')[0]
        if (param == 'IAMAT'):
            self.handle_IAMAT(line)
        elif (param == 'AT'):
            self.handle_AT(line)
        elif (param == 'WHATSAT'):
            self.handle_WHATSAT(line)
        else:
            logging.error("Received invalid line '%s'" % line)
            self.transport.write("? %s\n" % line)

    def handle_IAMAT(self, line):
        print 'IAMAT'

    def handle_AT(self, line):
        print 'AT'

    def handle_WHATSAT(self, line):
        print 'WHATSAT'


class ChatserverFactory(protocol.ServerFactory):
    def __init__(self, server_name):
        self.server_name = server_name
        self.port = SERVERS[self.server_name]
        self.clients = {}
        self.numConnections = 0
        logfile = "%s-%s.log" % (self.server_name, datetime.now().isoformat())
        logging.basicConfig(filename=logfile, level=logging.DEBUG)
        logging.info('Server %s:%d started' % (self.server_name, self.port))
        
    def buildProtocol(self, addr):
        return ChatserverReceiver(self)

def main():
    if len(sys.argv) != 2:
        print "Error: incorrect number of arguments"
        exit()
        
    factory = ChatserverFactory(sys.argv[1])
        
    reactor.listenTCP(SERVERS[sys.argv[1]], factory)
    reactor.run()

if __name__ == '__main__':
    main()
    
    

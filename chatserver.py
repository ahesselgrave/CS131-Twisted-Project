#!/usr/bin/python

from twisted.internet import protocol, reactor, endpoints
from twisted.protocols.basic import LineReceiver
from twisted.web.client import getPage

import json
import logging
import time
import datetime
import re
import sys

DEBUG = True

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
        logging.debug('Received IAMAT')
        # Expect syntax of IAMAT kiwi.cs.ucla.edu +34.068930-118.445127 1400794645.392014450
        params = line.split(' ')
        try:
            client_id = params[1]
            lat_lon = params[2]
            client_time = params[3]
        except IndexError:
            logging.error('IAMAT got an invalid line')
            self.transport.write('? %s\n' % line)
            return
            
        # Get current time and subtract from client time
        time_diff = time.time() - float(client_time)
        return_msg = 'AT %s %s %s %s %s' % (self.factory.server_name,
                                            str(time_diff) if time_diff < 0.0 else '+' + str(time_diff),
                                            params[1],
                                            params[2],
                                            params[3])

        self.factory.clients[client_id] = {'message': return_msg, 'time': client_time}
        self.transport.write('%s\n' % return_msg)
        logging.debug('Sent message to client %s: %s' % (client_id, return_msg))
        self.send_location_to_neighbors(return_msg)

    def handle_AT(self, line):
        logging.debug('Received AT')
        # Should only be sent by server
        params = line.split(' ')
        try:
            AT = params[0]
            sending_server = params[1]
            time_diff = params[2]
            client_id = params[3]
            lat_lon = params[4]
            original_client_time = params[5]
        except IndexError:
            logging.error('AT got an invalid line')
            self.transport.write('? %s\n' % line)
            return

        return_msg = '%s %s %s %s %s %s' % (AT,
                                            self.factory.server_name,
                                            time_diff,
                                            client_id,
                                            lat_lon,
                                            original_client_time,)
        
        # Propogate to neighbors if the timestamp is ahead of the cache
        if client_id in self.factory.clients and original_client_time <= self.factory.clients[client_id]['time']:
            logging.debug('Already propogated message')
            return
        else:
            self.factory.clients[client_id] = {'message': line, 'time': original_client_time}
            self.send_location_to_neighbors(return_msg)
        

    def handle_WHATSAT(self, line):
        logging.debug('Received WHATSAT')
        params = line.split(' ')
        try:
            WHATSAT = params[0]
            client_id = params[1]
            radius = int(params[2])
            upper_bound = int(params[3])
        except IndexError:
            logging.error('WHATSAT got an invalid line')
            self.transport.write('? %s\n' % line)
            return
            
        stored_message = self.factory.clients[client_id]['message']
        lat_lon = stored_message.split(' ')[4]
        
        self.get_places_location(client_id, lat_lon, radius, upper_bound)
        
    def send_location_to_neighbors(self, msg):
        for neighbor in COMM[self.factory.server_name]:
            reactor.connectTCP('localhost', SERVERS[neighbor], InterserverClient(msg))
            logging.debug('Sent message to %s: %s' % (neighbor, msg))

    def get_places_location(self, client_id, lat_lon, radius, upper_bound):
        # lat_lon needs to be 'lat,lon'
        formatted_lat_lon = re.sub(r'([+-]?\d+\.\d+)([+-]\d+\.\d+)', r'\1,\2', lat_lon)
        
        url = "%slocation=%s&radius=%s&sensor=false&key=%s" % (PLACES_URL, formatted_lat_lon, str(radius), API_KEY)
        response = getPage(url)
        logging.debug('Sent request to URL "%s"' % url)
        response.addCallback(callback=lambda r: (self.writePlacesJSON(r, client_id, upper_bound)))

    def writePlacesJSON(self, response, client_id, upper_bound):
        logging.debug('In response callback')
        response_json = json.loads(response)
        location_results = response_json['results']
        location_results = location_results[:upper_bound]
        logging.debug('Results are as follows:\n%s' % json.dumps(location_results, indent=4))
        message = self.factory.clients[client_id]['message']
        self.transport.write('%s\n%s\n\n' % (message, json.dumps(location_results, indent=4)))
        
class InterserverClientFactory(LineReceiver):
    def __init__ (self, factory):
        self.factory = factory

    def connectionMade(self):
        self.sendLine(self.factory.message)
        self.transport.loseConnection()

class InterserverClient(protocol.ClientFactory):
    def __init__(self, message):
        self.message = message

    def buildProtocol(self, addr):
        return InterserverClientFactory(self)
    
class ChatserverFactory(protocol.ServerFactory):
    def __init__(self, server_name):
        self.server_name = server_name
        self.port = SERVERS[self.server_name]
        self.clients = {}
        self.numConnections = 0
        logfile = "%s-%s.log" % (self.server_name, datetime.datetime.now().isoformat())
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
    
    

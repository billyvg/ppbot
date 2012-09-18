"""ppbot.py

A modular python bot that utilizes/will utilize postgresql as a data source.

TODO: Lots
"""
import traceback
from optparse import OptionParser

import irclib
import gevent
from gevent import monkey; monkey.patch_all()
from gevent import wsgi
from pong import application

from handlers.modulehandler import ModuleHandler
from handlers.eventhandler import EventHandler

from models.configuration import Configuration
from models.network import Network
from models.server import Server
from models.channel import Channel

from http.core import app as httpcore

from db import Db

from config import BotConfig

class ppbot(object):

    def __init__ (self):
        """Create an IRC object and do some initializations.
        Need to set handlers for events that may occur so that modules will be able to
        use them.

        """
        self.ircloop_timeout = 0.5

        self.irc = irclib.IRC()
        self.servers = []

        # initialize the databse
        self.engine = Db.engine
        self.session = Db.session
        self.session.expire_on_commit = False

        # load configuration
        self.config = Configuration()
        self.config.session_start()

        # initialize the module handler
        self.module_handler = ModuleHandler(self.servers, self.irc)
        # initialize the event handler
        self.event_handler = EventHandler(self.servers)
        self.event_handler.module_handler = self.module_handler

        # send all events to the event handler dispatcher
        self.irc.add_global_handler('all_events', self.event_handler.dispatcher)

        # load the default modules and auto-run modules
        self.load_modules()

    def connect(self):
        """ Create a server object, connect and join the channel. """

        networks = Network().val()

        for network in networks:
            # connect to the server
            server = self.irc.server()
            self.servers.append(server)
            server.server_config = network

            # TODO: should be using a queue for the servers to go through, 
            # since it could be possible to have more than one server to 
            # try to connect to.
            server_config = network.servers[0]
            try:
                server.connect(server_config.address, server_config.port, server_config.nickname, server_config.password, ircname=server_config.realname)
            except irclib.ServerConnectionError, e:
                print "<<Error>> Couldn't connect to %s:%s" % (server_config.address, server_config.port)

        # jump into an infinite loop
        jobs = [gevent.spawn(self.irc.process_forever)]
        gevent.joinall(jobs)

    def _run(self):
        self.irc.process_once(self.ircloop_timeout)
        gevent.sleep(self.ircloop_timeout)

    def load_modules(self):
        """ for now we will manually load modules, but this will eventually 
        call the database for what modules to auto-load

        """

        core = self.module_handler.load('Core')
        core.module_handler = self.module_handler

        self.module_handler.load('Irc')
        self.module_handler.load('Weather')
        self.module_handler.load('Stock')
        self.module_handler.load('Urldupe')
        self.module_handler.load('Urbandictionary')
        self.module_handler.load('Rottentomatoes')
        self.module_handler.load('Karmamod')
        self.module_handler.load('Yelp')
        self.module_handler.load('Quotemod')
        self.module_handler.load('Search')
        self.module_handler.load('Isup')
        self.module_handler.load('Notemod')
        self.module_handler.load('Urlparser')

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-i', '--init-db', dest='initdb', action='store_true',
                        help='Initialize the database.')
    # parser.add_option('-c', '--config', dest='config_file', action='store',
    #                     type='string', default='ppbot.cfg', help='Initialize the database.')

    (options, args) = parser.parse_args()


    if options.initdb:
        Db().init_db()

    config = BotConfig()
    irclib.DEBUG = config.getboolean('debug', 'irclib')

    server = wsgi.WSGIServer(('', 8088), httpcore)

    bot = ppbot()
    gevent.joinall([gevent.spawn(bot.connect), gevent.spawn(server.serve_forever)])

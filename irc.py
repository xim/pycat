import asynchat
import logging
import re
import socket
import time

logger = logging.getLogger('irc')

# FIXME irc message class that does parsing and building of messages
# FIXME class should also fix encoding

class IRC(object):
    max_per_second = 1

    def __init__(self, bot):
        self.bot = bot
        self.last_send = time.time()

    def __getattr__(self, key):
        key = key.upper()

        def wrapper(*args):
            self._command(key, *args)

        wrapper.__name__ = key
        return wrapper

    def _command(self, *args):
        if args[0].startswith('CTCP_'):
            ctcp = args[0][len('CTCP_'):]
            args = ['PRIVMSG', args[1], '\001%s %s\001' % (ctcp, args[2])]

        line = ' '.join(args[:-1]) + ' :' + args[-1]

        sleep = time.time() - self.last_send

        if sleep < self.max_per_second:
            time.sleep(self.max_per_second - sleep)

        logger.debug('Sending: %s', line)

        self.bot.push(line.encode('utf-8') + self.bot.get_terminator())
        self.last_send = time.time()

class Bot(asynchat.async_chat):
    # FIXME take in external config
    config = {
        'nick': 'pycat',
        'username': 'pycat',
        'hostname': socket.getfqdn(),
        'servername': socket.getfqdn(),
        'realname': 'pycat',
        'channel': '#foo',
    }

    def __init__(self, server, port=6667):
        asynchat.async_chat.__init__(self)

        self.server = server
        self.port = port

        self.buffer = ''
        self.handlers = {}
        self.current_nick = self.config['nick']

        self.irc = IRC(self)

        self.set_terminator("\r\n")

        self.add('PING', self.irc_pong)
        self.add('INVITE', self.irc_invite)
        self.add('376', self.irc_join)
        self.add('433', self.irc_nick_collision)

        self.reconnect()

    def reconnect(self):
        self.discard_buffers()

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self.server, self.port))

    # FIXME rename and fix signature. decorator?
    def add(self, command, handler):
        if command not in self.handlers:
            self.handlers[command] = []

        self.handlers[command].append(handler)

    def handle_command(self, prefix, command, args):
        for handler in self.handlers.get(command, []):
            handler(prefix, command, args)

    def handle_connect(self):
        logger.info('Connected to server')

        self.irc.nick(self.config['nick'])
        self.irc.user(self.config['username'],
                      self.config['hostname'],
                      self.config['servername'],
                      self.config['realname'])

    def handle_close(self):
        self.reconnect()

    def irc_pong(self, prefix, command, args):
        self.irc.pong(args[0])

    def irc_nick_collision(self, prefix, command, args):
        self.current_nick = args[1] + '_'
        self.irc.nick(self.current_nick)

    def irc_join(self, prefix, command, args):
        self.irc.join(self.config['channel'])

    def irc_invite(prefix, command, args):
        if args[0] == self.config['channel']:
            self.irc.join(self.config['channel'])

    # FIXME move to IRCMessage class?
    def parse_line(self, line):
        prefix = ''

        if line.startswith(':'):
            prefix, line = re.split(' +', line[1:],  1)

        if ' :' in line:
            line, trailing = re.split(' +:', line, 1)
            args = re.split(' +', line)
            args.append(trailing)
        else:
            args = re.split(' +', line)

        command = args.pop(0)

        if command == 'PRIVMSG' and args[1][0] == args[1][-1] == '\001':
            parts = re.split(' ', args[1][1:-1])
            command = 'CTCP_' + parts.pop(0)
            args[1] = ' '.join(parts)

        return prefix, command, args

    def collect_incoming_data(self, data):
        self.buffer += data

    def found_terminator(self):
        line, self.buffer = self.buffer, ''

        try:
            line = line.decode('utf-8')
        except UnicodeDecodeError:
            line = line.decode('iso-8859-1')

        logger.debug('Recieved: %s', line)

        prefix, command, args = self.parse_line(line)

        self.handle_command(prefix, command, args)

# m00se.py

from socket import socket
from redis import StrictRedis
from datetime import datetime
import pickle
from json import dumps, loads
import requests
from deps.hashid import HashChecker
from random import randint

class InfoMessage(object):
	def __init__(self, name, date, info):
		super(InfoMessage, self).__init__()
		self.name = name
		self.date = date
		self.info = info

class GistException(Exception):
	def __init__(self, message):
		Exception.__init__(self, message)

class Moose(object):
	def __init__(self, HOST, PORT, NICK):
		super(Moose, self).__init__()
		self.HOST = HOST
		self.PORT = PORT
		self.NICK = NICK
		self.redis_server = StrictRedis(host='127.0.0.1', port=6379, db=0)
		self.irc = socket()
		self.commands = {
			"challs": {
				"number_of_args": 0,
				"dep": ["redis_server"],
				"text": "!challs - Get all the challenges with info",
				"method": self.challs,
			},
			"add": {
				"number_of_args": 2,
				"dep": ["redis_server"],
				"text": "!add [challenge_name OR challenge_id] [url or text] - Add some info to a challenge to help others out",
				"method": self.add,
			},
			"get": {
				"number_of_args": 1,
				"dep": ["redis_server", "headers"],
				"text": "!get [challenge_name OR challenge_id] - Get a gist with all the info for a challenge",
				"method": self.get,
			},
			"calendar": {
				"number_of_args": 0,
				"text": "!calendar - Get the calendar url",
				"method": self.calendar,
			},
			"id": {
				"number_of_args": 1,
				"text": "!id [hash] - Identify a hash",
				"method": self.idhash
			},
			"purge": {
				"number_of_args": 0,
				"dep": ["redis_server"],
				"text": "!purge - Remove all challenges (zachzor only)",
				"method": self.purge
			},
			"farts": {
				"number_of_args": 0,
				"text": "!farts - Moose farts",
				"method": self.farts
			},
			"help": {
				"number_of_args": 1,
				"text": "!help [command] - Get info on how to use a command",
				"method": self.help
			},
		}
		f = open("github_oauth_token", "r")
		lines = f.readlines() 
		if len(lines) < 1:
			raise Exception("No token in github_oauth_token!")
		self.headers = {"Authorization": "token %s" % lines[0].strip(), "User-Agent": "ecxinc"}
		f.close()

	def create_gist(self, problem_name, problem_info):
		gist = {
			"files": {
				"%s.txt" % problem_name: { 
					"content": "\n".join("[%s %s] %s" % (info.name, info.date, info.info) for info in problem_info)
				}
			},
			"public": False
		}
		r = requests.post("https://api.github.com/gists", headers=self.headers, data=dumps(gist))
		if r.status_code != 201:
			raise GistException("Couldn't create gist!")
		return loads(r.text)["html_url"]

	def connect(self):
		print "Connecting..."
		self.irc.connect((self.HOST, self.PORT))
		self.irc.send("NICK %s\r\n" % self.NICK)
		self.irc.send("USER %s %s bla :%s\r\n" % (self.NICK, self.NICK, self.NICK))
		self.irc.send("JOIN #ctf\r\n")
		print "Connected!"
		self.serve_and_possibly_protect()

	def parsemsg(self, s):
		# Breaks a message from an IRC server into its username, command, and arguments.
		username, trailing = "", []
		if not s:
			return ""
		if s[0] == ':':
			username, s = s[1:].split(' ', 1)
			username_info = username.split("!")
			if len(username_info) > 1:
				username = username_info[0]
		if s.find(' :') != -1:
			s, trailing = s.split(' :', 1)
			args = s.split()
			args.append(trailing.strip().split(" "))
		else:
			args = s.split()
		command = args.pop(0)
		return username, command, args

	def send_message(self, message):
		self.irc.send("PRIVMSG #ctf :%s\r\n" % message)

	def handle_message(self, username, channel, args):
		if len(args) < 1:
			return
		arg = args.pop(0)[1:]
		if arg in self.commands.keys() and len(args[1:]) >= self.commands[arg]["number_of_args"]:
			params = args[1:self.commands[arg]["number_of_args"]]
			extra = [" ".join(args[self.commands[arg]["number_of_args"]:])]
			if extra != [""]:
				params = params + extra
			self.commands[arg]["method"](username, *params)
		elif arg == "help":
			self.help(username, "")
		elif arg in self.commands.keys():
			self.help(username, arg)

	def purge(self, username):
		if username == "zachzor":
			self.redis_server.delete("challs")
			self.send_message("All challenges removed")

	def get(self, username, challenge_name):
		if self.redis_server.hexists("challs", challenge_name) == False:
			self.send_message("%s is not a challenge" % challenge_name)
			return
		try:
			gist = self.create_gist(challenge_name, pickle.loads(self.redis_server.hget("challs", challenge_name)))
			self.send_message("%s" % gist)
		except GistException:
			self.send_message("Unable to create gist")

	def farts(self, username):
		self.send_message(" ".join(list(["pfffttt"] * randint(1, 7))))

	def add(self, username, challenge_name, description):
		new_info = InfoMessage(username, datetime.now().strftime("%m-%d-%Y %H:%M:%S"), " ".join(description))
		if self.redis_server.hget("challs", challenge_name) == None:
			self.redis_server.hset("challs", challenge_name, pickle.dumps([new_info]))
		else:
			old = pickle.loads(self.redis_server.hget("challs", challenge_name))
			old.append(new_info)
			self.redis_server.hset("challs", challenge_name, pickle.dumps(old))
		self.send_message("Added!")

	def idhash(self, username, hash):
		hash_type = HashChecker(hash)
		hashzor = hash_type.check_hash()
		if hashzor == None:
			self.send_message("Hmm... I'm not sure about that one")
		else:
			self.send_message("That's probably a %s hash" % hashzor)

	def challs(self, username):
		if self.redis_server.hlen("challs") == 0:
			self.send_message("No challenges")
		else:
			self.send_message("Challenges: %s" % ", ".join(["[%d] %s" % (i, s) for i, s in enumerate(self.redis_server.hkeys("challs"))]))

	def calendar(self, username):
		self.send_message("http://d.pr/Baur")

	def help(self, username, method_name):
		print method_name
		if method_name not in self.commands.keys():
			self.send_message(", ".join(self.commands.keys()))
		else:
			self.send_message(self.commands[method_name]["text"])

	def serve_and_possibly_protect(self):
		while 1:
			data = self.irc.recv(4096)
			username, command, args = self.parsemsg(data)
			if command == "PING":
				self.irc.send("PONG " + data[1] + '\r\n')
			elif command == "PRIVMSG":
				if len(args[1]) > 0 and args[1][0][0] == "!":
					self.handle_message(username, args[0], [x.lower() for x in args[1]])

def main():
	m = Moose("127.0.0.1", 6667, "m00se")
	m.connect()

if __name__ == '__main__':
	main()

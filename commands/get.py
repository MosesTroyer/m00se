from decorators import command
from deps.GistException import GistException
import json
from pickle import loads
from deps.helpers import update_seen
import requests
from hashlib import md5

@command("get", argc=1, text="!get [challenge_name] OR !get #[challenge_id] - Get a gist with all the info for a challenge", username=True)
def get(moose, username, challenge_name):
	name = ""
	if challenge_name[0] == '#':
		try:
			challenge_number = int(challenge_name[1:])
		except ValueError:
			moose.send_message("%s is not a valid challenge id" % challenge_name)
			return
		if moose.redis_server.hlen("challs") <= challenge_number or challenge_number < 0:
			moose.send_message("%s is not a valid challenge id" % challenge_name)
			return
		else:
			name = [(i, s) for i, s in enumerate(moose.redis_server.hkeys("challs"))][challenge_number][1]
	else:
		if not moose.redis_server.hexists("challs", challenge_name):
			moose.send_message("%s is not a valid challenge name" % challenge_name)
			return
		else:
			name = challenge_name
	try:
		gist = create_gist(moose, name, loads(moose.redis_server.hget("challs", name)))
		moose.send_message("%s" % gist)
		update_seen(moose, username, name)
	except GistException:
		moose.send_message("Unable to create gist")

def create_gist(moose, problem_name, problem_info):
	gist = {
		"files": {
			"%s.txt" % problem_name: { 
				"content": "\n".join("[%s %s] %s" % (info.name, info.date, info.info) for info in problem_info)
			}
		},
		"public": False
	}
	r = None
	for g in requests.get("https://api.github.com/gists", headers=moose.headers).json():
		if "%s.txt" % problem_name in  g["files"].keys():
			r = requests.patch("https://api.github.com/gists/%s" % g["id"], headers=moose.headers, data=json.dumps(gist))
			break
	if not r:
		r = requests.post("https://api.github.com/gists", headers=moose.headers, data=json.dumps(gist))
	if r.status_code != 201 and r.status_code != 200:
		raise GistException("Couldn't create gist!")
	return json.loads(r.text)["html_url"]

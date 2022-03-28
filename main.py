import socket
import logging
import sys
import requests
import time
import threading
from emoji import demojize
from datetime import datetime

"""
Please read the Readme.md before running!
"""

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s — %(message)s',
                    datefmt='%Y-%m-%d_%H:%M:%S',
                    handlers=[logging.FileHandler('chat.log', encoding='utf-8')])

logging.getLogger("urllib3").setLevel(logging.WARNING)

"""
To get a new token, visit https://twitchapps.com/tmi
"""
SERVER = 'irc.chat.twitch.tv'
PORT = 6667
NICKNAME = '<name of your app>'
TOKEN = '<paste from above>'
CHANNEL = '#<twitch channel name>'

"""
Register an application by going here: https://dev.twitch.tv/console/apps/create
paste the client ID and secret down below
"""

TWITCH_STREAM_API_ENDPOINT_V5 = "https://api.twitch.tv/helix/streams?user_login={}"

Client_ID = '<client id here>'
Client_Secret = '<client secret here>'
Accept = 'application/vnd.twitchtv.v5+json'

CHATTERS_AND_LURKERS_DICTIONARY = {}
IS_CHANNEL_ONLINE = True

"""
Main idea:
If a channel is ONLINE, only then do these below things:

Get the list of lurkers and chatters every 10 minutes or so
Let the message parser give points
Get new list of lurkers and chatters and join (don't delete old people)
After 2 hours, print the dict with points.
"""


def main():
    global IS_CHANNEL_ONLINE
    IS_CHANNEL_ONLINE = is_stream_live()
    global CHATTERS_AND_LURKERS_DICTIONARY

    if IS_CHANNEL_ONLINE:
        CHATTERS_AND_LURKERS_DICTIONARY = get_chatters_and_lurkers(CHANNEL[1:])
    else:
        print("Channel offline.")
        exit_handler()

    sock = socket.socket()
    sock.connect((SERVER, PORT))
    sock.send(f"PASS {TOKEN}\r\n".encode('utf-8'))
    sock.send(f"NICK {NICKNAME}\r\n".encode('utf-8'))
    sock.send(f"JOIN {CHANNEL}\r\n".encode('utf-8'))

    if IS_CHANNEL_ONLINE:
        try:
            thread1 = threading.Thread(target=connect_to_twitch, args=(sock,))
            thread1.start()

            thread2 = threading.Thread(target=update_chatters)
            thread2.start()

            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            exit_handler()
            sys.exit("Program finished")


"""
This method is to get an access token. The access token is based
on your login and is used to check if a channel is online or offline
"""


def get_access_token():
    body = {
        'client_id': Client_ID,
        'client_secret': Client_Secret,
        "grant_type": 'client_credentials'
    }
    r = requests.post('https://id.twitch.tv/oauth2/token', body)
    keys = r.json()

    return keys['access_token']


"""
This method is to use the access token from above and see if the specified
channel is live or not. If the channel is not live, we don't want to refresh chatters.
"""


def is_stream_live():
    access_token = get_access_token()
    url = TWITCH_STREAM_API_ENDPOINT_V5.format(CHANNEL[1:])

    api_headers = {
        'Client-ID': Client_ID,
        'Authorization': 'Bearer ' + access_token
    }

    try:
        req = requests.Session().get(url, headers=api_headers)
        json_data = req.json()
        if json_data.get('data'):
            if json_data.get('data')[0] is not None:
                if json_data.get('data')[0]['type'] == 'live':  # stream is online
                    return True
                else:
                    return False
        else:
            return False
    except Exception as e:
        print("Error checking user: ", e)
        return False


"""
Method to returns all the chatters, and give them 0 points to begin with
0 points means, lurkage only.
"""


def get_chatters_and_lurkers(user_channel):
    # https://tmi.twitch.tv/group/user/markettraderstv/chatters
    url = 'https://tmi.twitch.tv/group/user/' + user_channel + '/chatters'

    resp = requests.get(url=url)
    data = resp.json()

    # global mods and others omitted for now
    vips = data['chatters']['vips']
    moderators = data['chatters']['moderators']
    viewers = data['chatters']['viewers']

    all_viewers = [*vips, *moderators, *viewers]

    return dict.fromkeys(all_viewers, 0)


"""
Method to connect to Twitch with the provided socket
Also calls the parses message and award points methods.
"""


def connect_to_twitch(sock):
    global CHATTERS_AND_LURKERS_DICTIONARY
    counter = 0
    try:
        while True:
            try:
                resp = sock.recv(2048).decode('utf-8')

                if resp.startswith('PING'):
                    sock.send("PONG\n".encode('utf-8'))

                elif len(resp) > 0:
                    counter = counter + 1
                    if counter > 2:
                        now = datetime.now()
                        message = now.strftime("%Y_%m_%d_%H-%M-%S") + demojize(resp)
                        parse_message(message, CHATTERS_AND_LURKERS_DICTIONARY)
            except ConnectionResetError:
                print("Connection reset by Twitch. Re-run program")
            time.sleep(1)

    except KeyboardInterrupt:
        sock.close()
        exit()


"""
Method to parse the message received by the socket
Also calls the award points method.
"""


def parse_message(line, dict_of_users):
    try:
        username_message = line.split(':')[1:]
        username_message = ':'.join(username_message).strip()

        message = username_message.partition(':')[2]

        username = username_message.partition('!')[0]

        d = {
            'username': username,
            'message': message
        }

        logging.info(d)

        award_points(username, dict_of_users)

    except Exception:
        raise RuntimeError('Uh oh!')


"""
Method to award points to a user.
Currently, 1 chat = 1 point. We can chat if need be.
There can be abuse here, but we can set the point threshold higher
or even check if a message is not just a 1 word (besides !lurk)
Future enhancement maybe?
"""


def award_points(username, dict_of_users):
    original_value = dict_of_users.get(username, 0)
    dict_of_users[username] = original_value + 1


"""
Method to update the list of chatters
Run every 10 minutes or so, so that we don't miss
any members that come or go from the stream chat.
Calls out the refresh method
"""


def update_chatters():
    global IS_CHANNEL_ONLINE
    if IS_CHANNEL_ONLINE:
        print("It's been 10 minutes, let's refresh our chatters")
        new_chatters_and_lurkers_dictionary = get_chatters_and_lurkers(CHANNEL[1:])
        global CHATTERS_AND_LURKERS_DICTIONARY
        CHATTERS_AND_LURKERS_DICTIONARY = refresh_chatters_and_lurkers(CHATTERS_AND_LURKERS_DICTIONARY,
                                                                       new_chatters_and_lurkers_dictionary)
        # sleep for 10 minutes (in seconds)
        time.sleep(600)
    else:
        print("Channel is offline, not refreshing")


"""
Method to actually refresh the dictionary of members.
Returns a new list of combined members.
"""


def refresh_chatters_and_lurkers(chatters_and_lurkers_old, chatters_and_lurkers_new):
    new_dict_combined = {}
    for chatter in chatters_and_lurkers_new:
        if chatter in chatters_and_lurkers_old:
            new_dict_combined[chatter] = chatters_and_lurkers_new[chatter] + chatters_and_lurkers_old[chatter]
        else:
            new_dict_combined.update({chatter: chatters_and_lurkers_new[chatter]})

    return new_dict_combined


"""
Method to print out the dictionary list of points
at the end of a program exit (keyboardInterrupt mainly)
"""


def exit_handler():
    global CHATTERS_AND_LURKERS_DICTIONARY
    for key, value in CHATTERS_AND_LURKERS_DICTIONARY.items():
        print(key, " : ", value)


"""
This "thing" runs our program essentially.
"""


if __name__ == '__main__':
    main()

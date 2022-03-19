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
server = 'irc.chat.twitch.tv'
port = 6667
nickname = '<name of your app>'
token = '<paste from above>'
channel = '#<twitch channel name>'

chatters_and_lurkers_dict = {}

"""
Main idea:
Get the list of lurkers and chatters every 10 minutes or so
Let the message parser give points
Get new list of lurkers and chatters and join (don't delete old people)
After 2 hours, print the dict with points.
"""


def main():
    global chatters_and_lurkers_dict
    chatters_and_lurkers_dict = get_chatters_and_lurkers(channel[1:])

    sock = socket.socket()
    sock.connect((server, port))
    sock.send(f"PASS {token}\r\n".encode('utf-8'))
    sock.send(f"NICK {nickname}\r\n".encode('utf-8'))
    sock.send(f"JOIN {channel}\r\n".encode('utf-8'))

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

    global chatters_and_lurkers_dict
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
                        parse_message(message, chatters_and_lurkers_dict)
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
    while True:
        print("It's been 10 minutes, let's refresh our chatters")
        new_chatters_and_lurkers_dict = get_chatters_and_lurkers(channel[1:])
        global chatters_and_lurkers_dict
        chatters_and_lurkers_dict = refresh_chatters_and_lurkers(chatters_and_lurkers_dict,
                                                                 new_chatters_and_lurkers_dict)
        # sleep for 10 minutes (in seconds)
        time.sleep(600)


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
    global chatters_and_lurkers_dict
    for key, value in chatters_and_lurkers_dict.items():
        print(key, " : ", value)


"""
This "thing" runs our program essentially.
"""


if __name__ == '__main__':
    main()

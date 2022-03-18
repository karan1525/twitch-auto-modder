# Twitch Auto Modder

The point of this "modder" is to view chat messages as they come and award people points.
These points are then input on a spreadsheet and used to award people slots on the week's schedule.
The "modding" used to be a manual process but now, thanks to this bot, it won't be.
Feature enhancements to come.

Auto modder for Twitch. Used by Streamers Bureau
Check us out: https://discord.gg/hHyYtKZKPh

# Caveats

- Have to run the program in an IDE (I used PyCharm)
- Must kill the program twice (first kill prints out the final dictionary, 2nd kill, kills the program)
- chat.log must be cleaned up before every run (otherwise you'd see old stuff)
  - I'd recommend just deleting the file, cause it's created every time anyways.

# Must install packages:

Requests + Demojize

pip install requests <br/>
pip install emoji

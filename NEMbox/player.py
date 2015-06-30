#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: omi
# @Date:   2014-07-15 15:48:27
# @Last Modified by:   omi
# @Last Modified time: 2015-01-30 18:05:08


'''
网易云音乐 Player
'''
# Let's make some noise

import subprocess
import threading
import time
import os
import signal
import random
from ui import Ui
try:
    from mpd import MPDClient
except:
    MPDClient = None

# carousel x in [left, right]
carousel = lambda left, right, x: left if (x > right) else (right if x < left else x)

class MPEG123Player:
    def __init__(self):
        self.ui = Ui()
        self.datatype = 'songs'
        self.popen_handler = None
        # flag stop, prevent thread start
        self.playing_flag = False
        self.pause_flag = False
        self.songs = []
        self.idx = 0
        self.volume = 60

    def popen_recall(self, onExit, popenArgs):
        """
        Runs the given args in a subprocess.Popen, and then calls the function
        onExit when the subprocess completes.
        onExit is a callable object, and popenArgs is a lists/tuple of args that
        would give to subprocess.Popen.
        """

        def runInThread(onExit, popenArgs):
            self.popen_handler = subprocess.Popen(['mpg123', '-R', ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.popen_handler.stdin.write("SILENCE\n")
            self.popen_handler.stdin.write("V " + str(self.volume) + "\n")
            self.popen_handler.stdin.write("L " + popenArgs + "\n")
            # self.popen_handler.wait()
            while (True):
                if self.playing_flag == False:
                    break
                try:
                    strout = self.popen_handler.stdout.readline()
                except IOError:
                    break
                if strout == "@P 0\n":
                    self.popen_handler.stdin.write("Q\n")
                    self.popen_handler.kill()
                    break

            if self.playing_flag:
                self.idx = carousel(0, len(self.songs) - 1, self.idx + 1)
                onExit()
            return

        thread = threading.Thread(target=runInThread, args=(onExit, popenArgs))
        thread.start()
        # returns immediately after the thread starts
        return thread

    def recall(self):
        self.playing_flag = True
        item = self.songs[self.idx]
        self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time())
        self.popen_recall(self.recall, item['mp3_url'])

    def play(self, datatype, songs, idx):
        # if same playlists && idx --> same song :: pause/resume it
        self.datatype = datatype

        if datatype == 'songs' or datatype == 'djchannels':
            if idx == self.idx and songs == self.songs:
                if self.pause_flag:
                    self.resume()
                else:
                    self.pause()

            else:
                if datatype == 'songs' or datatype == 'djchannels':
                    self.songs = songs
                    self.idx = idx

                # if it's playing
                if self.playing_flag:
                    self.switch()

                # start new play
                else:
                    self.recall()
        # if current menu is not song, pause/resume
        else:
            if self.playing_flag:
                if self.pause_flag:
                    self.resume()
                else:
                    self.pause()
            else:
                pass

    # play another
    def switch(self):
        self.stop()
        # wait process be killed
        time.sleep(0.01)
        self.recall()

    def stop(self):
        if self.playing_flag and self.popen_handler:
            self.playing_flag = False
            self.popen_handler.stdin.write("Q\n")
            self.popen_handler.kill()

    def pause(self):
        self.pause_flag = True
        os.kill(self.popen_handler.pid, signal.SIGSTOP)
        item = self.songs[self.idx]
        self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time(), pause=True)

    def resume(self):
        self.pause_flag = False
        os.kill(self.popen_handler.pid, signal.SIGCONT)
        item = self.songs[self.idx]
        self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time())

    def next(self):
        self.stop()
        time.sleep(0.01)
        self.idx = carousel(0, len(self.songs) - 1, self.idx + 1)
        self.recall()

    def prev(self):
        self.stop()
        time.sleep(0.01)
        self.idx = carousel(0, len(self.songs) - 1, self.idx - 1)
        self.recall()

    def shuffle(self):
        self.stop()
        time.sleep(0.01)
        num = random.randint(0, 12)
        self.idx = carousel(0, len(self.songs) - 1, self.idx + num)
        self.recall()

    def volume_up(self):
        self.volume = self.volume + 7
        if (self.volume > 100):
            self.volume = 100
        self.popen_handler.stdin.write("V " + str(self.volume) + "\n")

    def volume_down(self):
        self.volume = self.volume - 7
        if (self.volume < 0):
            self.volume = 0
        self.popen_handler.stdin.write("V " + str(self.volume) + "\n")

    def update_size(self):
        try:
            self.ui.update_size()
            item = self.songs[self.idx]
            if self.playing_flag:
                self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time())
            if self.pause_flag:
                self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time(), pause=True)
        except IndexError:
            pass

class MPDPlayer:
    def __init__(self, config=None):
        self.mpd = MPDClient()
        self.ui = Ui()
        self.datatype = 'songs'
        # flag stop, prevent thread start
        self.songs = []
        self.idx = 0 # TODO: Not keep a local idx, but using mpd's playlist
        self.mpd.connect('127.0.0.1', '6600')
        self.volume = int(self.mpd.status()['volume'])

    def update_ui(self):
        self.check_connection()
        item = self.songs[self.idx]
        status = self.mpd.status()['state']
        self.ui.build_playinfo(item['song_name'], item['artist'], item['album_name'], item['quality'], time.time(), pause=(status != 'play'))

    def play(self, datatype, songs, idx):
        # if same playlists && idx --> same song :: pause/resume it
        self.datatype = datatype
        self.check_connection()
        print idx

        if datatype == 'songs' or datatype == 'djchannels':
            if idx == self.idx and songs == self.songs:
                self.toggle()
            else:
                #TODO: create a mpd play list.
                self.mpd.clear()
                for i in songs:
                    self.mpd.add(i['mp3_url'])
                self.songs = songs
                self.idx = idx
                # if it's playing
                self.mpd.play(idx)
        # if current menu is not song, pause/resume
        else:
            self.toggle()

    def check_connection(self):
        try:
            self.mpd.status()
        except:
            self.mpd.disconnect()
            self.mpd.connect('127.0.0.1', '6600')

    def stop(self):
        self.check_connection()
        self.mpd.stop()
        self.update_ui()

    def toggle(self):
        self.check_connection()
        self.mpd.pause()
        self.update_ui()

    def next(self):
        self.check_connection()
        self.idx = carousel(0, len(self.songs) - 1, self.idx + 1)
        self.mpd.next()
        self.update_ui()

    def prev(self):
        self.check_connection()
        self.idx = carousel(0, len(self.songs) - 1, self.idx + 1)
        self.mpd.prev()
        self.update_ui()

    def shuffle(self):
        pass # lazy to implement

    def volume_up(self):
        self.check_connection()
        self.volume = self.volume + 5 if self.volume < 95 else 100
        self.mpd.volume(5)
        self.update_ui()

    def volume_down(self):
        self.check_connection()
        self.volume = self.volume - 5 if self.volume > 5 else 0
        self.mpd.volume(-5)
        self.update_ui()

    def update_size(self):
        try:
            self.ui.update_size()
            self.update_ui()
        except IndexError:
            pass

if MPDClient:
    Player = MPDPlayer
else:
    Player = MPEG123Player

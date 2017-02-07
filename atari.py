#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: atari.py
# Author: Yuxin Wu <ppwwyyxxc@gmail.com>

import numpy as np
import time
import os
import cv2
from collections import deque
import threading
import six
from six.moves import range
from tensorpack.utils import (get_rng, logger, execute_only_once)
from tensorpack.utils.fs import get_dataset_path
from tensorpack.utils.stats import StatCounter

from tensorpack.RL.envbase import RLEnvironment, DiscreteActionSpace
from tanks import Game

import random

__all__ = ['AtariPlayer']

ROM_URL = "https://github.com/openai/atari-py/tree/master/atari_py/atari_roms"
_ALE_LOCK = threading.Lock()


class AtariPlayer(RLEnvironment):
    """
    A wrapper for atari emulator.
    Will automatically restart when a real episode ends (isOver might be just
    lost of lives but not game over).
    """

    def __init__(self, viz=0, height_range=(None, None),
                 frame_skip=4, image_shape=(84,84), nullop_start=30):
        """
        :param frame_skip: skip every k frames and repeat the action
        :param image_shape: (w, h)
        :param height_range: (h1, h2) to cut
        :param viz: visualization to be done.
            Set to 0 to disable.
            Set to a positive number to be the delay between frames to show.
            Set to a string to be a directory to store frames.
        :param nullop_start: start with random number of null ops
        :param live_losts_as_eoe: consider lost of lives as end of episode.  useful for training.
        """
        super(AtariPlayer, self).__init__()
        
        self.game = Game()

        # viz setup
        if isinstance(viz, six.string_types):
            assert os.path.isdir(viz), viz
            viz = 0
        if isinstance(viz, int):
            viz = float(viz)
        self.viz = viz
        if self.viz and isinstance(self.viz, float):
            self.windowname = 'Battle City'
            cv2.startWindowThread()
            cv2.namedWindow(self.windowname)
        
        self.width, self.height = 416,416
        self.actions = [0,1,2,3,4,5]
        
        self.frame_skip = frame_skip
        self.nullop_start = nullop_start
        self.height_range = height_range
        self.image_shape = image_shape

        self.current_episode_score = 0
        
        self.restart_episode()

    def _grab_raw_image(self):
        """
        :returns: the current 3-channel image
        """
        return self.game.getScreenRGB()

    def current_state(self):
        """
        :returns: a gray-scale (h, w, 1) uint8 image
        """
        ret = self._grab_raw_image()        
        # max-pooled over the last screen
        ret = np.maximum(ret, self.last_raw_screen)
        if self.viz:
            if isinstance(self.viz, float):
                cv2.imshow(self.windowname, ret)
                time.sleep(self.viz)
        ret = ret[self.height_range[0]:self.height_range[1], :].astype('float32')
        # 0.299,0.587.0.114. same as rgb2y in torch/image
        ret = cv2.cvtColor(ret, cv2.COLOR_RGB2GRAY)
        ret = cv2.resize(ret, self.image_shape)
        ret = np.expand_dims(ret, axis=2)
        return ret.astype('uint8')  # to save some memory

    def get_action_space(self):
        return DiscreteActionSpace(len(self.actions))

    def finish_episode(self):
        self.stats['score'].append(self.current_episode_score)

    def restart_episode(self):
        self.current_episode_score = 0        
        self.game.reset_game()
        # random null-ops start
        self.last_raw_screen = self._grab_raw_image()
        self.game.act(0)

    def action(self, act):
        """
        :param act: an index of the action
        :returns: (reward, isOver)
        """
        
        for k in range(self.frame_skip):
            if k == self.frame_skip - 1:
                self.last_raw_screen = self._grab_raw_image()
            self.game.act(act)
            if self.game.isGameOver():
                break

        self.current_episode_score = self.game.getScore()
        isOver = self.game.isGameOver()
        if isOver:
            self.finish_episode()
            self.restart_episode()
            
        return (self.current_episode_score, isOver)


if __name__ == '__main__':
    a = AtariPlayer(viz=0.03)    
    num = a.get_action_space().num_actions()    
    while True:
        # im = a.grab_image()
        # cv2.imshow(a.romname, im)
        act = random.randint(0,num)
        r, o = a.action(act)
        a.current_state()
        print(a.current_episode_score)
        # time.sleep(0.1)
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import traceback
import time
from menus import Menus

from menus import Menus

class TimeTrigger(object):

    known_triggers = {}

    def __init__(self,ref,menus):
        self.menus = menus
        self.ref = ref
        self.base = None
        self.triggered = False
        TimeTrigger.known_triggers[ref] = self

    def reset(self):
        self.base = int(time.time())
        self.triggered = False

    def trigger(self):
        if not self.triggered:
            if self.base:
                if int(time.time()) - self.base > self.menus.options[self.ref][3]:
                    self.triggered = True
                    return True
        return False

    @staticmethod
    def resets():
        for key, value in TimeTrigger.known_triggers.items():
            value.reset()

    @staticmethod
    def triggers():
        trigs = []
        for key, value in TimeTrigger.known_triggers.items():
            if value.trigger():
                trigs = trigs + key
        return trigs

#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import traceback

import datafiles
from TimeTrigger import TimeTrigger

class State(object):

    knownStates = { }
    ACTION_BEGIN = 1
    ACTION_RESUME = 2
    ACTION_END = 3

    current = None
    start = 0
    empty = False
    greasy = False

    delayed = None
    dstart = 0
    dempty = False
    dgreasy = False

    @staticmethod
    def get(letter,empty,greasy=False):
        return State.knownStates[letter][empty][greasy]

    @staticmethod
    def setCurrent(letter,empty,greasy=False):
        State.current = State.get(letter,empty,greasy)
        State.empty = empty
        State.greasy = greasy
        # print (State.current.letter)
        return State.current

    @staticmethod
    def transitCurrent(step, action, now=int(time.time()) ):
        (State.start,State.current, State.empty, State.greasy) = State.current.transit(State.empty, State.greasy, step, action, State.start, now=now)
        # print (State.current.letter)

    @staticmethod
    def transitDelayed(step, action, now=int(time.time()) ):
        (State.dstart,State.delayed, State.dempty, State.dgreasy) = State.current.transit(State.empty, State.greasy, step, action, State.start, toBeSaved=False, now=now)
        # print (State.delayed.letter)

    @staticmethod
    def loadCurrent(): # returns timestamp and current state
        try:
            with open(datafiles.paramfile("state.csv")) as f:
                stateData = f.read()
                # print (stateData)
                data = stateData.split('\n')
                if data and len(data) >= 2:
                    data = data[1].split('\t')
                    if len(data) >= 2:
                        since = data[0]
                        stateLetter = data[1]
                        if len(data) >= 4:
                            State.empty = bool(data[2])
                            State.greasy = bool(data[3])
                        if stateLetter and stateLetter[0] and stateLetter in State.knownStates:
                            State.current = State.knownStates[stateLetter[0]][State.empty][State.greasy]
                            return int(since), State.current, State.empty, State.greasy
                State.setCurrent('s',False,False)
                State.saveCurrent()
        except IOError: # unknown previous state
            State.setCurrent('s',False,False)
            State.saveCurrent()
        return 0,State.current,False,False # If state unknown, it is dirty !

    @staticmethod
    def saveCurrent(now=int(time.time())):
        try:
            State.current.save(State.empty,State.greasy,State.start)
        except IOError: # no place to save current state ?
            traceback.print_exc()

    @staticmethod
    def popDelayed(now=int(time.time())):
        if State.delayed:
            State.start = now
            State.empty = State.dempty
            State.greasy = State.dgreasy
            State.current = State.delayed
            TimeTrigger.resets()
            State.saveCurrent()
            State.delayed = None

    def __init__(self, letter, labels, color, transitions, emptiness=None, greasiness=None):
        #cohorts.catalog[address] = self Done by the threading class...
        if emptiness is None:
            emptiness = [False, True]
        if greasiness is None:
            greasiness = [False, True]
        self.letter = letter
        self.color = color
        self.labels = labels
        self.transitions = transitions
        if letter not in State.knownStates:
            State.knownStates[letter] = [[None,None],[None,None]]
        for empty in emptiness:
            for greasy in greasiness:
                State.knownStates[letter][empty][greasy] = self

    def transit(self,empty,greasy,step,action, start, toBeSaved=True, now=int(time.time()) ):
        for (actDone,nextState) in self.transitions:
            if actDone == action:
                if nextState is None:
                    newState = State.get(self.letter,empty,greasy)
                elif isinstance(nextState, list):
                    newLetter = None
                    if len(nextState):
                        if step == State.ACTION_BEGIN:
                            newLetter = nextState[0]
                        elif step == State.ACTION_RESUME:
                            newLetter = nextState[0 if (len(nextState) <= 1) else 1]
                        else: # ACTION_END
                            newLetter = nextState[len(nextState) - 1]
                    if isinstance(newLetter, list):
                        if newLetter[1] is not None:
                            empty = newLetter[1]
                        if newLetter[2] is not None:
                            greasy = newLetter[2]
                        newLetter = newLetter[0]
                    if not newLetter:
                        newLetter = self.letter
                    newState = State.get(newLetter,empty,greasy)
                elif nextState:
                    newState = State.get(nextState,empty,greasy)
                else: # empty = same state
                    newState = State.get(self.letter,empty,greasy)
                if newState.letter != self.letter:
                    if toBeSaved:
                        TimeTrigger.resets()
                        newState.save(empty, greasy, now)
                    return now, newState,empty, greasy
                else:
                    return start, newState,empty,greasy
        print ("Unknown action=%s for state=%s" % (action,self.letter))
        try:
            return State.get('?',empty,greasy).transit(empty,greasy,step,action, start, toBeSaved=toBeSaved, now=now )
        except:
            print ("IMPOSSIBLE action=%s for state=%s" % (action,self.letter))
            return start,self,empty,greasy

    def allowedActions (self):
        result = ""
        for (actDone,nextState) in self.transitions:
            result += actDone
        if 'O' in result:
            result += 'N' # Cleaning parameters and Pasteurisation parameters are both allowed most of the time.
        return result

    def save(self, empty, greasy=False, now=int(time.time()) ):
        try:
            with open(datafiles.paramfile("state.csv"), "w") as data_file:
                data_file.write("epoch_sec\tstate\tempty\tgreasy\n")
                data_file.write("%d\t%s\t%d\t%d\n"%(now, self.letter, empty, greasy))
                # print ("%d\t%s\t%d\t%d\n"%(now, self.letter, empty, greasy))
        except IOError: # unknown previous state
            traceback.print_exc()

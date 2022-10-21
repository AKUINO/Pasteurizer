#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import datetime
import traceback
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

    def get(letter,empty,greasy=False):
        return State.knownStates[letter][empty][greasy]

    def setCurrent(letter,empty,greasy=False):
        State.current = State.get(letter,empty,greasy)
        State.empty = empty
        State.greasy = greasy
        # print (State.current.letter)
        return State.current

    def transitCurrent(step, action, now=int(time.time()) ):
        (State.start,State.current, State.empty, State.greasy) = State.current.transit(State.empty, State.greasy, step, action, State.start, now)
        # print (State.current.letter)

    data_dir = None

    def loadCurrent(DIR_DATA_CSV): # returns timestamp and current state

        State.data_dir = DIR_DATA_CSV
        try:
            with open(DIR_DATA_CSV + "state.csv") as f:
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
        except IOError: # unknown previous state
            traceback.print_exc()
        State.setCurrent('s',False,False)
        return 0,State.current,False,False # If state unknown, it is dirty !

    def saveCurrent(now=int(time.time()) ):
        State.current.save(State.empty,State.greasy,State.start)

    def __init__(self,letter,labels,transitions,emptiness=[False,True],greasiness=[False,True]):
        #cohorts.catalog[address] = self Done by the threading class...
        self.letter = letter
        self.labels = labels
        self.transitions = transitions
        if not letter in State.knownStates:
            State.knownStates[letter] = [[None,None],[None,None]]
        for empty in emptiness:
            for greasy in greasiness:
                State.knownStates[letter][empty][greasy] = self

    def transit(self,empty,greasy,step,action, start, now=int(time.time()) ):
        for (actDone,nextState) in self.transitions:
            if actDone == action:
                if nextState == None:
                    newState = State.get(self.letter,empty,greasy)
                elif isinstance(nextState, list):
                    if step == State.ACTION_BEGIN:
                        newLetter = nextState[0]
                    elif step == State.ACTION_RESUME:
                        newLetter = nextState[(len(nextState)-1) if (len(nextState) > 2) else 1]
                    else: # ACTION_END
                        newLetter = nextState[len(nextState) - 1]
                    if isinstance(newLetter, list):
                        if newLetter[1] != None:
                            empty = newLetter[1]
                        if newLetter[2] != None:
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
                    TimeTrigger.resets()
                    newState.save(empty, greasy, now)
                    return now, newState,empty, greasy
                else:
                    return start, newState,empty,greasy
        print ("Unknown action=%s for state=%s"%(action,self.letter))
        return start,self,empty,greasy

    def allowedActions (self):
        result = ""
        for (actDone,nextState) in self.transitions:
            result += actDone
        return result

    def save(self, empty, greasy=False, now=int(time.time()) ):
        try:
            with open(State.data_dir + "state.csv", "w") as data_file:
                data_file.write("epoch_sec\tstate\tempty\tgreasy\n")
                data_file.write("%d\t%s\t%d\t%d\n"%(now, self.letter, empty, greasy))
        except IOError: # unknown previous state
            traceback.print_exc()

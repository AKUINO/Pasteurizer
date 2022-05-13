#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import datetime
import traceback

def load(DIR_DATA_CSV): # returns timestamp and current state
    try:
        with open(DIR_DATA_CSV + "state.csv") as f:
            stateData = f.read()
            print (stateData)
            data = stateData.split('\n')
            if data and len(data) >= 2:
                data = data[1].split('\t')
                if len(data) >= 2:
                    since = data[0]
                    stateLetter = data[1]
                    if stateLetter and stateLetter[0] and stateLetter in State.knownStates:
                        return int(since),State.knownStates[stateLetter[0]]
    except IOError: # unknown previous state
        traceback.print_exc()
    return 0,State.knownStates['s'] # If state unknown, it is dirty !

class State(object):

    knownStates = { }
    ACTION_BEGIN = 1
    ACTION_RESUME = 2
    ACTION_END = 3

    def __init__(self,letter,labels,transitions):
        #cohorts.catalog[address] = self Done by the threading class...
        self.letter = letter
        self.labels = labels
        self.transitions = transitions
        State.knownStates[letter] = self

    def transit(self,step,action,start,now = time.perf_counter()):
        for (actDone,nextState) in self.transitions:
            if action == actDone:
                if isinstance(nextState, list):
                    if step == State.ACTION_BEGIN:
                        newLetter = nextState[0]
                    elif step == State.ACTION_RESUME:
                        newLetter = nextState[(len(nextState)-1) if (len(nextState) > 2) else 1]
                    else: # ACTION_END
                        newLetter = nextState[len(nextState) - 1]
                    newState = State.knownStates[newLetter]
                else:
                    newState = State.knownStates[nextState]
                if newState.letter != self.letter:
                    newState.save()
                    return now, newState
                else:
                    return start, self
        print ("Unknown action=%s for state=%s"%(action,self.letter))
        return start,self

    def allowedActions (self):
        result = ""
        for (actDone,nextState) in self.transitions:
            result += actDone
        return result

    def save(self,DIR_DATA_CSV,nowT=time.perf_counter()):
        data_file = open(DIR_DATA_CSV + "state.csv", "w")
        data_file.write("epoch_sec\tstate\n")
        data_file.write("%d\t%s\n"%(int(nowT),self.letter))
        data_file.close()

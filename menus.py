#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import traceback
import codecs
import configparser

class Menus(object):

    NAM = 1 #multilingual name
    TIT = 2 #multilingual title
    VAL = 3 #current value
    INI = 4 #initial value
    UNI = 5 #unit
    MIN = -1 #not assigned, always 0.0 ...
    MAX = 7 #max value
    STP = 8 #step
    TYP = 9 #number, time per HTML input type
    REF = 10 #when a value is calculated another way

    singleton = None #initialized after class definition is closed

    def __init__(self):
        self.options = None
        self.sortedOptions = None
        self.actionName = None
        self.sortedActions1 = None
        self.sortedActions2 = None
        self.cleanActions = None
        self.dirtyActions = None
        self.optActions = None
        self.operName = None
        self.cleanOptions = None
        self.dirtyOptions = None

    def nam(self,letter):
        return self.options[letter][Menus.NAM]

    def tit(self,letter):
        return self.options[letter][Menus.TIT]

    def val(self,letter):
        return self.options[letter][Menus.VAL]

    def ini(self,letter):
        return self.options[letter][Menus.INI]

    def uni(self,letter):
        return self.options[letter][Menus.UNI]

    def max(self,letter):
        return self.options[letter][Menus.MAX]

    def stp(self,letter):
        return self.options[letter][Menus.STP]

    def type(self,letter):
        return self.options[letter][Menus.TYP]

    def ref(self,letter):
        if len(self.options[letter]) > Menus.REF:
            return self.options[letter][Menus.REF]
        else:
            return None

    def display(self,letter, field, value = None):
        fieldType = None
        if value is None and field:
            if field == Menus.MAX:
                value = self.max(letter)
            elif field == Menus.MIN:
                value = 0.0
            elif field == Menus.VAL:
                value = self.val(letter)
            elif field == Menus.INI:
                value = self.ini(letter)
            elif field == Menus.STP:
                value = self.stp(letter)
            fieldType = self.type(letter)
        if value is None:
            return ''
        if fieldType == 'time':
            if field == Menus.STP:
                if value >= 60.0:
                    return ''
                else:
                    return str(value)
            else:
                #return datetime.timedelta(seconds=value).strftime("%H:%M")
                return '%02d:%02d' % (value // 3600, (value % 3600) // 60)
        return str(value)

    def store(self,letter, value):
        try:
            if value is None or value == '':
                self.options[letter][Menus.VAL] = None
            fieldType = self.type(letter)
            if fieldType == 'time':
                date_time = datetime. datetime. strptime(value, "%H:%M") #%S:
                a_timedelta = date_time - datetime. datetime(1900, 1, 1)
                self.options[letter][Menus.VAL] = float( a_timedelta.total_seconds() )
            else:
                self.options[letter][Menus.VAL] = float(value)
        except:
            traceback.print_exc()

    def loadCurrent(self,DIR_DATA_CSV): # returns timestamp and current state

        Menus.option_file = DIR_DATA_CSV + "options.ini"
        configParsing = configparser.RawConfigParser()
        try:
            with codecs.open(Menus.option_file, 'r', 'utf8' ) as f:
                configParsing.read_file(f)
        except IOError:
            print(Menus.option_file+' not found. Using default options values.')
            configParsing = None

        if configParsing:
            if 'options' in configParsing.sections():
                for anItem in configParsing.items('options'):
                    if anItem[0] in self.options:
                        if anItem[1]:
                            try:
                                self.options[anItem[0]][Menus.VAL] = float(anItem[1])
                            except:
                                print ('In '+Menus.option_file+', option '+anItem[0]+'='+anItem[1]+' not a floating point number like 3.14')

    def save(self):
        try:
            with open(Menus.option_file, "w") as data_file:
                data_file.write("[options]\n")
                for (letter,anOption) in self.options.items():
                    if anOption[Menus.VAL] != anOption[Menus.INI]:
                        data_file.write(letter+"="+str(anOption[Menus.VAL])+"\n")
        except IOError: # unknown previous state
            traceback.print_exc()

Menus.singleton = Menus()



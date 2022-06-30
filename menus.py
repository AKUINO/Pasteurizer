#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import traceback

class Menus(object):

    VAL = 3
    INI = 4
    MIN = -1 #not assigned, always 0.0 ...
    MAX = 7
    STP = 8

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

    def val(self,letter):
        return self.options[letter][Menus.VAL]

    def ini(self,letter):
        return self.options[letter][Menus.INI]

    def max(self,letter):
        return self.options[letter][Menus.MAX]

    def stp(self,letter):
        return self.options[letter][Menus.STP]

    def type(self,letter):
        return self.options[letter][9]

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

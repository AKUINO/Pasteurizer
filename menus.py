#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import traceback

class Menus(object):
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
        return self.options[letter][3]

    def ini(self,letter):
        return self.options[letter][4]

    def max(self,letter):
        return self.options[letter][7]

    def stp(self,letter):
        return self.options[letter][8]

    def type(self,letter):
        return self.options[letter][9]

    def display(self,letter, field, value = None):
        if value is None and field:
            if field == 'MAX':
                value = self.max(letter)
            elif field == 'MIN':
                value = 0.0
            elif field == 'VAL':
                value = self.val(letter)
            elif field == 'INI':
                value = self.ini(letter)
            elif field == 'STP':
                value = self.stp(letter)
            fieldType = self.type(letter)
        if value is None:
            return ''
        if fieldType == 'time' and field != 'STP':
            return str(datetime.timedelta(seconds=value))
        return str(value)

    def store(self,letter, value):
        try:
            if value is None or value == '':
                self.options[letter][3] = None
            fieldType = self.type(letter)
            if fieldType == 'time':
                date_time = datetime. datetime. strptime(value, "%M:%S") #%H:
                a_timedelta = date_time - datetime. datetime(1900, 1, 1)
                self.options[letter][3] = float( a_timedelta.total_seconds() )
            else:
                self.options[letter][3] = float(value)
        except:
            traceback.print_exc()

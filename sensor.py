#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import datetime
import traceback
import term

# typeNum assignation
# 1 : One Wire
# 2 : Button
# 3 : ssr
# 4 : pump (not pwm)
# 5 : thermistor
# 6 : valve
# 7 : pump_pwm
#11 : RMeter
#12 : LED
#15 : solenoid

class Sensor(object):

    def __init__(self,sensorType,address,param):
        #cohorts.catalog[address] = self Done by the threading class...
        self.sensorType = sensorType
        self.address = address
        self.param = param
        self.value = 0.0
        self.last = time.perf_counter()
        self.changed = 0.0
        self.prv1 = None
        self.prv2 = None
        self.entry_sum = 0.0
        self.entry_size = 0

    def set(self,value):
        if not self.value:
            self.changed = 0.0
        else:
            self.changed = float(value) - self.value
        self.prv2 = self.prv1
        self.prv1 = self.value
        self.value = value
        if value is not None:
            self.entry_sum += value
            self.entry_size += 1
            self.last = time.perf_counter()
        return self.changed

    def reset(self):
        if not self.entry_size:
            return self.value
        entry = self.entry_sum / self.entry_size # mean data in the period
        self.entry_sum = 0.0
        self.entry_size = 0
        return entry

    def get(self):
        return self.value, self.last, self.changed

    def avg3(self):
        if self.value is None:
            return None
        if self.prv1 is None:
            return None
        if self.prv2 is None:
            return None
        return (self.value + self.prv1 + self.prv2) / 3.0

    def val(self,format="%.2f"):
        if not self.value:
            return ""
        else:
            return format % self.value

    def display(self,format=" %5.2f°C"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % self.value, attr, term.bgwhite)


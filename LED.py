#!/usr/bin/python3
# -*- coding: utf-8 -*-
import term
import sensor
import traceback

import hardConf


class LED(sensor.Sensor):

    typeNum = 12

    def __init__(self,address,param):
        try:
            if hardConf.localGPIOtype == 'gpio':
                hardConf.localGPIO.setup(param, hardConf.gpio_OUTPUT)
            elif hardConf.localGPIOtype == 'pigpio':
                hardConf.localGPIO.set_mode(param, hardConf.gpio_OUTPUT)
        except:
            print ("%s: init GPIO no.%d" % (address,param))
            traceback.print_exc()
        self.lastwrite = 0
        super().__init__(LED.typeNum,address,param)

    def write(self,value):
        self.lastwrite = value
        try:
            if hardConf.localGPIOtype == 'gpio':
                hardConf.localGPIO.output(self.param,1 if value > 0 else 0)
            elif hardConf.localGPIOtype == 'pigpio':
                hardConf.localGPIO.write(self.param,1 if value > 0 else 0)
            #print ("%d=%d" % (self.param,value))
            #traceback.print_stack()
        except:
            print ("%s: %d=%d" % (self.address, self.param,value))
            traceback.print_exc()

    def set(self,value):
        if float(value) > 1.0:
            value = int(value)
        elif float(value) > 0.0:
            value = 1
        else:
            value = 0
        self.write(value)
        changed = super().set(value)
        return changed

    def display(self,format=" %d"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % self.value, attr, term.bgwhite)

    def close(self):
        self.set(0) # Or whatever the "non heating" solenoid value

    def off(self):
        self.set(0)

    def blink(self,flashPerSeconds=2):
        if self.value == int(flashPerSeconds):
            if self.lastwrite == 0:
                self.write(1)
            else:
                self.write(0)
        else:
            self.set(flashPerSeconds)

    def on(self):
        self.set(1)

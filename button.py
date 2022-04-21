#!/usr/bin/python3
# -*- coding: utf-8 -*-
import term
import sensor
import traceback

import hardConf


class button(sensor.Sensor):

    typeNum = 13

    def __init__(self,address,param):
        try:
            if hardConf.localGPIOtype == 'pypi':
                hardConf.localGPIO.setup(param, hardConf.gpio_INPUT)
            elif hardConf.localGPIOtype == 'pigpio':
                hardConf.localGPIO.set_mode(param, hardConf.gpio_INPUT)
        except:
            print ("%s: init GPIO no.%d" % (address,param))
            traceback.print_exc()
        self.lastwrite = 0
        super().__init__(button.typeNum,address,param)

    def get(self):
        value = None
        try:
            if hardConf.localGPIOtype == 'pypi':
                value = hardConf.localGPIO.input(self.param)
            elif hardConf.localGPIOtype == 'pigpio':
                value = hardConf.localGPIO.read(self.param)
            #print ("%d=%d" % (self.param,value))
            #traceback.print_stack()
        except:
            print ("%s: %d=%d" % (self.address, self.param,value))
            traceback.print_exc()
        if value is not None:
            self.set(value)
        return value

    def display(self,format=" %d"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % self.value, attr, term.bgwhite)

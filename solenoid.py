#!/usr/bin/python3
# -*- coding: utf-8 -*-
import term
import sensor
import traceback

import hardConf


class Solenoid(sensor.Sensor):

    typeNum = 15
    onOff = ['off','ON ']

    def __init__(self,address,param):
        super().__init__(Solenoid.typeNum,address,param)

    def set(self,value):
        if float(value) > 0.0:
            value = 1
        else:
            value = 0
        changed = super().set(value)
        #if changed:
        # Value written may have to be reversed...
        try:
            if hardConf.io:
                hardConf.io.write_pin(self.param,value)
            #print ("%d=%d" % (self.param,value))
            #traceback.print_stack()
        except:
            print ("%d=%d" % (self.param,value))
            traceback.print_exc()
        return changed

    def display(self,format=" %s"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % Solenoid.onOff[self.value], attr, term.bgwhite)

    def close(self):
        self.set(0) # Or whatever the "non heating" solenoid value

if __name__ == "__main__":

    while True:
        try:
            onOff = input("(-)Port=")
            if not onOff:
                break
            onOff = int(onOff)
            if onOff < 0:
                port = -onOff
                val = 0
            else:
                port = onOff
                val = 1
            hardConf.io.write_pin(port,val)
        except:
            traceback.print_exc()
            break

    hardConf.close()

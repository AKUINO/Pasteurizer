#!/usr/bin/python3
# -*- coding: utf-8 -*-
import term
import sensor
import traceback
import time
import hardConf

class Valve(sensor.Sensor):

    typeNum = 6
    onOff = ['closing','OPENING','close','OPEN']

    def __init__(self,address,paramOpen,paramClose,duration=6.5,reverse=False, wire7=False):
        super().__init__(Valve.typeNum,address,paramClose)
        self.paramOpen = paramOpen #Brun et/ou rouge. ***Close=Bleu, GND=Brun+Blanc ou Bleu+Blanc ou Noir
        self.duration = duration
        self.reverse = reverse
        self.value = None
        self.wire7 = wire7

    def set(self,value): # 0.0: close, 1.0:open
        if not hardConf.io:
            return None
        mustBeSet = False
        if self.value is None:
            mustBeSet = True
        elif self.value != value:
            mustBeSet = True
        if mustBeSet:
            if (value > 0.0): # open
                value = 1.0
                try:
                    if self.wire7:
                        hardConf.io.write_pin(self.param,1)
                        hardConf.io.write_pin(self.paramOpen,1)
                    else:
                        hardConf.io.write_pin(self.param,1 if self.reverse else 0)
                        hardConf.io.write_pin(self.paramOpen,0 if self.reverse else 1)
                    #print ("%d=0,%d=1" % (self.param,self.paramOpen))
                except:
                    traceback.print_exc()
            else: # close
                value = 0.0
                try:
                    if self.wire7:
                        hardConf.io.write_pin(self.param,0)
                        hardConf.io.write_pin(self.paramOpen,1)
                    else:
                        hardConf.io.write_pin(self.paramOpen,1 if self.reverse else 0)
                        hardConf.io.write_pin(self.param,0 if self.reverse else 1)
                    #print ("%d=0,%d=1" % (self.paramOpen,self.param))
                except:
                    traceback.print_exc()
            changed = super().set(value)
            return changed
        else: # Check opening/closing duration
            if time.perf_counter() > self.last+self.duration: # stop action
                try:
                    if self.wire7:
                        hardConf.io.write_pin(self.paramOpen,0)
                        hardConf.io.write_pin(self.param,0)
                    else:
                        hardConf.io.write_pin(self.paramOpen if value > 0.0 else self.param,1 if self.reverse else 0)
                    #print ("%d=0" % (self.paramOpen if value > 0.0 else self.param))
                except:
                    traceback.print_exc()
            return None

    def setWait(self,value):
        if not hardConf.io:
            return None
        if value > 0.0:
            value = 1.0
        else:
            value = 0.0
        change = self.set(value)
        if change and change != 0.0:
            time.sleep(self.duration)
        else:
            remain = self.last+self.duration - time.perf_counter()
            if remain > 0.0:
                time.sleep(remain)
        if self.wire7:
            hardConf.io.write_pin(self.paramOpen,0)
            hardConf.io.write_pin(self.param,0)
        else:
            hardConf.io.write_pin(self.paramOpen if value > 0.0 else self.param,1 if self.reverse else 0)
        #print ("%d=0" % (self.paramOpen if value > 0.0 else self.param))
        return change

    def display(self,format=" %s"):
        i = 0
        if self.value >= 0.0:
            i = 1
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % Valve.onOff[int(self.value)+int(2*(1 if time.perf_counter() > valve.last+self.duration else 0))], attr, term.bgwhite)
        
    def close(self):
        pass # Caller must set the valve in desired position...

if __name__ == "__main__":
    openPort = input("Opening Port:")
    closePort = input("Closing Port:")

    valve = Valve("dump", int(openPort), int(closePort), wire7=False) 
    while True:
        try:
            onOff = input("Open=1, Close=0? ")
            if not onOff:
                break
            onOff = float(onOff)
            if onOff <= 0.0:
                val = 0
            else:
                val = 1
            print ("Valve="+str(valve.setWait(val)))
            print (valve.display())
        except:
            traceback.print_exc()
            break
    hardConf.close()


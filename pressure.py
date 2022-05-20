#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  pressure.py
#  
#  Copyright 2020 Christophe Dupriez <dupriez@destin.be>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
import time
import term
import sensor
import math
import traceback

import hardConf
import MICHApast

Vcc = 5.1  # power voltage applied to the pressure sensor

def calcBar(regVal):
    try:
        pressure_V = regVal / 1638  # pressure in V
        #pressure_psi = 125 * (pressure_V / Vcc) - 12.5  # pressure in Psi

        pressure_psi = (pressure_V - (Vcc*0.1) ) * (90 / (Vcc*0.8))  # pressure in Psi
        #pressure_psi = 100*(pressure_V/Vcc)
        pressure_bar = pressure_psi / 14.504  # pressure in bar
        return pressure_bar
    except:
        return 0.0

class Pressure(sensor.Sensor):

    typeNum = 8

    def __init__(self,address,param,enable_pin):
        super().__init__(Pressure.typeNum,address,param)
        self.enable_pin = enable_pin
        self.min = None
        self.max = None
        if hardConf.io:
            hardConf.io.write_pin(self.enable_pin,1) #Enable measurement

    def display(self,format=" %5.2f°C"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % (self.value if self.value else 0.0), attr, term.bgwhite)

    def getreading(self):
        if hardConf.io:
            regVal = hardConf.io.read_input(self.param)
            if regVal != None:
                press = calcBar(regVal)
                minVal = calcBar(hardConf.io.read_input(self.param+1))
                maxVal = calcBar(hardConf.io.read_input(self.param+2))
                #print ("%d(%f)=%f ohm; %f°C"%(self.param,volts,res,temp))
                return press,minVal,maxVal
        return 0.0

    def get(self):
        value,min,max = self.getreading()
        if value:
            self.min = min
            self.max = max
            self.set(value)
        return value

    def close(self):
        if hardConf.io:
            hardConf.io.write_pin(self.enable_pin,0) #Disable measurement

def main(args):
    try:
        press=Pressure("PRESS",MICHApast.PRESS_SENSOR_REG,MICHApast.PRESS_FLAG_REG)
        while True:
            p = press.get()
            term.write(press.address+": ")
            if p:
                press.display()
            term.writeLine("")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    except:
        traceback.print_exc()
    hardConf.close()
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

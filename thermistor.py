#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  thermistor.py
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

# Thermistor Resistance & Beta Parameter (from datasheet)
#bResistance = 3969

# Constants
t0 = 273.15  # 0°C in °Kelvin
t25 = t0 + 25.0 # 25°C in Kelvin

def calcResistance(voltage,top_resis):
    try:
        return (top_resis*voltage) / (hardConf.thermistors_voltage-voltage)
    except:
        return 0.0

class Thermistor(sensor.Sensor):

    typeNum = 5

    def __init__(self,address,param):
        super().__init__(Thermistor.typeNum,address,param)
        self.bResistance = None # A,B,C are prefered except if Beta is specified in config (old Beta is 3694.0)
        self.t25Resistance = 10000.0
        # Reinhart-hart contants (for the temperature range from 20°C to 100°C)
        self.A = 0.0010296697555538872
        self.B = 0.00023902485774993708
        self.C = 1.572127153105922e-07
        if hardConf.io and not hardConf.MICHA_device: # LOCAL ADC (not MICHA)
            self.stim_pin = ((int(param)-1)*2)+1
            hardConf.io.set_pin_direction(self.stim_pin,0) #Output
            hardConf.io.write_pin(self.stim_pin,1) #Disable measurement
    
    def display(self, format_param=" %5.2f°C"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format_param % (self.value if self.value else 0.0), attr, term.bgwhite)

    def calcTemp(self, resistance):
        try:
            if self.bResistance: # A,B,C are prefered except if Beta is specified in config (old Beta is 3694.0)
                # print ("%s: %dmV, b=%d, r25=%d" % (self.address,resistance,self.bResistance,self.t25Resistance))
                return 1 / ( (math.log(resistance / self.t25Resistance) / self.bResistance) + (1.0 / t25) ) - t0
            else:
                return 1/(self.A+self.B*math.log(resistance)+self.C*(math.log(resistance))**3) - t0   # Reinhart-hart formula
        except:
            return 0.0

    def getreading(self):
        if hardConf.io:
            if not hardConf.MICHA_device: # LOCAL ADC (not MICHA)
                hardConf.io.write_pin(self.stim_pin, 0)
                time.sleep(0.004) # DO NOT IMPROVE WHEN INCREASED !
                volts = hardConf.adc.read_adc_voltage(self.param,0)
                hardConf.io.write_pin(self.stim_pin, 1)
            else: # MICHA
                volts = hardConf.io.read_input(self.param)
                if volts is not None:
                    volts *= hardConf.thermistors_voltage/4096.0
            if volts is not None:
                res = calcResistance(volts,hardConf.thermistors_Rtop)
                temp = self.calcTemp(res)
                #print ("%d(%f)=%f ohm; %f°C"%(self.param,volts,res,temp))
                if (temp > 0.0) and (temp < 100.0):
                    return volts,res,temp
        return 0.0,0.0,None

    def get(self):
        value,res,temperature = self.getreading()
        if temperature:
            self.set(temperature)
        return temperature

    def close(self):
        if not hardConf.MICHA_device and hardConf.io: # LOCAL ADC (not MICHA)
            hardConf.io.set_pin_direction(self.stim_pin,0) #Output
            hardConf.io.write_pin(self.stim_pin,1) #Disable measurement

def main(args):
    try:
        # print(Thermistor("THE1",1).calcTemp(1868)) # test pour la resistance de 72°C
        therm = [Thermistor("THE1",1),Thermistor("THE2",2),Thermistor("THE3",3),Thermistor("THE4",4)]
        while True:
            for t in therm:
                temp = t.get()
                term.write(t.address+": ")
                if temp:
                    t.display()
                term.writeLine("")
            time.sleep(3.0)
    except KeyboardInterrupt:
        pass
    except:
        traceback.print_exc()
    hardConf.close()
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

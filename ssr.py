#!/usr/bin/python3
# -*- coding: utf-8 -*-
import traceback
import sensor
import term
import time

import hardDependencies
if hardDependencies.Raspberry:
    import mcp4922
    import RPi.GPIO as GPIO

class ssr(sensor.Sensor):

    typeNum = 3

# wattsVal = [0,0,0,1,17,51,104,207,357,544,779,976,1182,1354,1473,1494,1500]

    def interpolate(w):
    ##    j = 0
    ##    prec = 0
    ##    for i in wattsVal:
    ##        if w <= i:
    ##            return int(j-(255*(i-w)/(i-prec)))
    ##        prec = i
    ##        j=j+255
    ##    return 4095
        r = int(434.5583 + (3.957467*w) - (0.003550898*(w*w)) + (0.000001376311*(w*w*w)))
        if r < 0:
            r = 0
        elif r > 4095:
            r = 4095
        return r

    def __init__(self,address,param):
        super().__init__(ssr.typeNum,address,param)

        if hardDependencies.Raspberry:
            self.dac = mcp4922.MCP4922(cs=26)
            self.dac.setVoltage(0,0)
        else:
            self.dac = None
        self.prec_relay = 0

    def set(self,wattHour):
        change = super().set(wattHour)
        if wattHour <= 0.0:
            relay = 0
        elif wattHour >= 1500.0:
            relay = 4095
        else:
            relay = ssr.interpolate(wattHour)
        if relay != self.prec_relay:
            if self.dac:
                self.dac.setVoltage(0,relay)
            self.prec_relay = relay
        #print (relay)
        return change

    def display(self, format_param=" %5.0fW"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format_param % self.value, attr, term.bgwhite)

    def close(self):
        self.prec_relay = 0
        if self.dac:
            self.dac.setVoltage(0, 0)
            self.dac.shutdown(0)
            self.dac.close()

if __name__ == "__main__":
    if hardDependencies.Raspberry:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

    ssry = ssr("DAC1",0)
    prec = time.perf_counter()
    precW = 0.0
    print ("What a proportional SSR can do for you?")

##    for i in range(0,4095,100):
##        print (i)
##        ssry.dac.setVoltage(0,i)
##        time.sleep(15)

    while True:
        try:
            time.sleep(0.5)
            watts = input("Watts/hour=").upper()
            now = time.perf_counter()
            print ("%.3f seconds  at %.2f W/hour = %dWatts." % (now-prec,precW, int(precW*(now-prec)/3600) ) )
            if watts == "":
                break
            else:  
                try:
                    watts = float(watts)
                    prec = now
                    precW = watts
                    ssry.set(watts)
                except:
                    traceback.print_exc()
                    print ("Enter a number of watts or [Enter] to exit...")
        except KeyboardInterrupt:
            break
        except:
            traceback.print_exc()
            continue
    if not ssry.close():
        print ("Error closing!")
    else:
        print ("SSR stopped and closed.")

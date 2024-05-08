#!/usr/bin/python
import hardDependencies
if hardDependencies.Raspberry:
    import RPi.GPIO as GPIO
import mcp4922
import time
import pyownet
import math

owproxy = pyownet.protocol.proxy(host="localhost", port=4304)

setpoint = 72.0 # degree Celsius
reject = 71.7
tank = 5.0 # liters
kCalWatt = 1.16 # watts per kilo calories
tempInput = setpoint # pour le moment, à lire !
QtyLiterHour = 40.0 # pour le moment, dépend de la vitesse de la pompe (à calibrer!!!)

GPIO.setmode(GPIO.BOARD)
dac = mcp4922.MCP4922(cs=26)

def get_timestamp():
    now = time.time()
    now = math.floor(float(now))
    now = int(now)
    return now

wattsVal = [0,0,0,1,17,51,104,207,357,544,779,976,1182,1354,1473,1494,1500]

def interpolate(w):
    j = 0
    prec = 0
    for i in wattsVal:
        if w <= i:
            return j-(255*(i-w)/(i-prec))
        prec = i
        j=j+255

##dac.setVoltage(0,4095)
##time.sleep(300)

##i = 0
##for i in range(0,4095,255):
##    print i
##    dac.setVoltage(0,i)
##    time.sleep(6)

error = 0.0
nberror = 0
nbreject = 0
while (True):
    sum = 0.0
    nb = 0
    begin = get_timestamp()
    now = begin
    while (True):
        status = owproxy.write("/simultaneous/temperature", b'1')
        output_val = float(owproxy.read("/28.FFDD64931504/temperature"))
        input_val = float(owproxy.read("/28.CC3EAF040000/temperature"))
        tempInput = input_val
        print ("%d: in=%0.2f°C, out=%0.2f°C" % (now,input_val,output_val))
        nb = nb+1
        sum = sum+output_val
        x = setpoint - output_val
        if x < 0:
            error = error - x
        else:
            error = error + x
        nberror = nberror+1
        time.sleep(2)
        now = get_timestamp()
        if now >= (begin+8):
            break;
    mean = sum / nb
    value = 0
    wattHour = 0.0
    if mean <= setpoint:
        kCal = (setpoint-mean)*tank
        wattHour = (kCal * kCalWatt) * 60.0
        # refroidissement prévu
        wattHour = wattHour + ((setpoint-21.0)*240.0/37.0)
        # injection de lait prévue
        wattHour = wattHour + ((setpoint-tempInput)*QtyLiterHour*kCalWatt)
        if wattHour < 1.0:
            value = 0
        elif wattHour > 1500.0:
            value = 4095
        else:
            value = interpolate(wattHour)
    print ("W=%0.2f w, val=%d, err=%0.3f"%(wattHour,value,error/nberror))
    dac.setVoltage(0,int(value))

print ("off!")
dac.setVoltage(0,0)
dac.shutdown(0)
dac.close()

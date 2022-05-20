#!/usr/bin/python3
# -*- coding: utf-8 -*-
import struct

import time
import math
import threading
import traceback
import sensor
import term

import MICHApast
import hardConf

# Driver for SYNTRON Two-phase closed loop stepper driver SS-20806

TEST = False

# Must be coherent with switch setting on the stepping motor driver module:
REVOLUTION_STEPS = 6400 #1000, 2000, 4000, 5000, 8000, 10000, 20000, 25000
                    #200, 400, 800, 1600, 3200, 6400, 12800, 25600
                    
if hardConf.MICHA_device:
    SPEED_INCREMENT = None # Ramping is done by MICHA
    REAL_SPEED_INCREMENT = 20
else:
    SPEED_INCREMENT = 20 # When ramping up or down, speed change by tenth of a second
    REAL_SPEED_INCREMENT = 20


class ReadPump_PWM(threading.Thread):
    
    global TEST

    # 1:Over Current: Overcurrent alarm : constant red
    # 2:AD Sampling Bad: AD Midpoint sampling abnormal : slow flash, 2 times
    # 3:Power Down: Motor wire or encoder wire is not connected : slow flash, 3 times
    # 4:Under Voltage; Undervoltage(voltage < 20V ) : slow flash, 4 times
    # 5:Over Voltage: Overvoltage(voltage > 90V ) : slow flash, 5 times
    # 6:Out Tolerance: Out of tolerance : fast flash, 2 times
    # 7:Over Heating: The motor is overloaded for a long time : fast flash, 4 times

    errors = ["none","Over Current","AD Sampling Bad","Power Down","Under Voltage","Over Voltage",
              "Out Tolerance","Over Heating"]

    # The duration of the red light when flashing slowly is 280 ms, The red light will last for 140ms, The flashing interval is 1.8s
    # Sampling at 70ms will ensure that slow flash is repeating 4 to 5 "high" and then "low"
    # Fast flash will be repeating 2 to 3 "high" and then "low"
    # Constant "high" (more than 5 high in a row) = Over Current
    # 320ms or more of "low" is end of a flashing: Status can be signaled

    def __init__(self, pump, sampling = 0.070 ):
        threading.Thread.__init__(self)
        self.pump = pump
        self.OK = True
        self.sampling = sampling
        self.PERIOD_FACTOR = 26
        self.SYNC_FACTOR = 5
        self.LONG_FACTOR = 3
        self.SHORT_FACTOR = 1

    def close(self):
        self.OK = False

    def setStateStatus(self,state):
        if state == 1:
            self.pump.lastError = ReadPump_PWM.errors[1]
        elif state == 2:
            self.pump.lastError = ReadPump_PWM.errors[0]
        elif state == 14:
            self.pump.lastError = ReadPump_PWM.errors[2]
        elif state == 16:
            self.pump.lastError = ReadPump_PWM.errors[3]
        elif state == 18:
            self.pump.lastError = ReadPump_PWM.errors[4]
        elif state == 20:
            self.pump.lastError = ReadPump_PWM.errors[5]
        elif state == 34:
            self.pump.lastError = ReadPump_PWM.errors[6]
        elif state == 38:
            self.pump.lastError = ReadPump_PWM.errors[7]
        else:
            self.pump.lastError = "BAD="+str(state)

    def repr(self):
        return ("[%s, error=%s]" % (self.pump.address, self.pump.lastError) )

    def run(self):
        state = None # unknown state
        now = time.perf_counter()
        prv = now
        transition = now
        returnLine = -1 # silly value
        while self.OK:
            sleepTime = prv + self.sampling - now
            if sleepTime > 0:
                prv = now + sleepTime
                time.sleep(sleepTime)
            else:
                prv = now
            now = time.perf_counter()
            prvLine = returnLine
            returnLine = self.pump.read_return()
            if returnLine != prvLine:
                transition = now
            if returnLine: #LOW
                if (now - transition) >= (self.PERIOD_FACTOR * self.sampling):
                    self.setStateStatus(2)
                    stateTime = now
                    state = 2  # SYNCED on low, no problem !
                elif (now - transition) >= (self.SYNC_FACTOR * self.sampling):
                        if state and state != 2:
                            self.setStateStatus(state)
                        stateTime = now
                        state = 2  # SYNCED on low, no problem !
                elif state is None:
                    stateTime = now
                    state = 0 # low
                elif state == 3:
                    if (now - stateTime) >= (self.LONG_FACTOR*self.sampling):
                        stateTime = now
                        state = 10 # 1st of long flashes (slow)
                    elif (now - stateTime) >= (self.SHORT_FACTOR*self.sampling):
                        stateTime = now
                        state = 30 # 1st of short flashes (fast)
                    else:
                        pass
                elif state in [11,13,15,17,19]: # long flashes (slow)
                    if (now - stateTime) < (self.LONG_FACTOR*self.sampling): #Too short for a long...
                        stateTime = now
                        state = 0 # needs to resync...
                    else:
                        stateTime = now
                        state = state+1
                elif state in [31,33,35,37,39]: # short flashes (fast)
                    if (now - stateTime) >= (self.LONG_FACTOR*self.sampling): #Too long for a short...
                        stateTime = now
                        state = 0 # needs to resync...
                    else:
                        stateTime = now
                        state = state+1
                else:
                    pass
            else: #HIGH
                if (now - transition) >= (self.SYNC_FACTOR * self.sampling):
                    self.setStateStatus(1)
                    stateTime = now
                    state = 1  # SYNCED on high (Overcurrent...)
                elif state == 2: # SYNCED on low
                    stateTime = now
                    state = 3 # 1st HIGH
                elif state in [10,12,14,16,18]: # long flashes
                    if (now - stateTime) < (self.LONG_FACTOR*self.sampling): #Too short for a long...
                        stateTime = now
                        state = 0 # needs to resync...
                    else:
                        stateTime = now
                        state = state+1
                elif state in [30,32,34,36,38]: # short flashes
                    if (now - stateTime) >= (self.LONG_FACTOR*self.sampling): #Too long for a short...
                        stateTime = now
                        state = 0 # needs to resync...
                    else:
                        stateTime = now
                        state = state+1
                else:
                    pass

class pump_PWM(sensor.Sensor):

    typeNum = 7

    def __init__(self,
                 pinPWM = 12, # 12(board=32) or 18(board=12) CustardPi Digital out #2, RPi PWM
                 pinDirection = -14, # 17(board=11) CustardPi Digital out #2
                 pinStatus = -15,  # 23(board=16) CustardPi Digital in #1. RPi pin must be in "Pull-up"...
                 maxSpeed = 300,#437, #600 in theory. 400 is possible when pumping air (previous value: 284)
                 maximal_liters = None,
                 minimal_liters = 15.0
                 ):
        self.sensorType = pump_PWM.typeNum
        self.address = "PUMP"
        if hardConf.MICHA_device:
            self.pinPWM = MICHApast.PUMP_SPEED_REG #Holding register
            self.pinDirection = MICHApast.PUMP_DIR_REG #coil
            self.pinStatus = MICHApast.PUMP_ERR_REG #Input register
        else:
            self.pinPWM = pinPWM
            self.pinDirection = pinDirection
            self.pinStatus = pinStatus
        self.pumpSerial = None
        self.prec_entry = 0.0
        self.maxSpeed = maxSpeed
        self.minimal_liters = minimal_liters
        self.speed = 0.0
        self.speed_liters = 0.0
        self.reverse = False
        self.requestedVolume = None
        self.now = None
        self.previous_change = time.perf_counter()
        self.previous_volume = 0.0
        self.previous_speed = 0.0
        self.lastError = None
        self.running = False
        self.subdivision = 8
        if not maximal_liters:
            self.maximal_liters = self.speedLitersHour(self.maxSpeed)
        else:
            self.maximal_liters = maximal_liters

    set = None
    avg3 = None



    # Those two functions are not perfectly reciprocal: beware!
    def litersHourSpeed(self,liters):
        reverse = False
        if liters == 0:
            return 0
        elif liters < 0:
            liters = -liters
            reverse = True
        #speed = 1.767022 + (1.27568*liters) - (0.0001245927*liters*liters)
        speed = 2.862497 + (1.384241*liters) - (0.0002019344*liters*liters)
        if reverse:
            speed = -speed
        return speed

    def speedLitersHour(self,speed):
        reverse = False
        if speed == 0:
            return 0.0
        elif speed < 0:
            speed = -speed
            reverse = True
        #speed = speed / self.LitersHour_Speed
        #LH = -2.286407 + (2.275162*speed) - (0.009631488*speed*speed)
        #LH = -1.553908 + (0.7883528*speed) + (0.00004403381*speed*speed)
        LH = -2.255906 + (0.7268268*speed) + (0.00006146902*speed*speed)
        if LH <= 0.0:
            LH = 0.0
        elif reverse:
            LH = -LH
        return LH

    def speed_freq(self, speed_rpm):
        return int((speed_rpm/60.0)*REVOLUTION_STEPS)

    def reset_pump(self):
        self.stop()
        if hardConf.MICHA_device:
            try:
                time.sleep(2)
                hardConf.io.set_pump_power(0) # Disable power. (pins are managed by MICHA board)
                time.sleep(2)
                hardConf.io.set_pump_power(1) # Enable power. (pins are managed by MICHA board)
            except:
                traceback.print_exc()

    def open(self):

        OK = True
        try:
            if hardConf.MICHA_device:
                hardConf.io.set_pump_power(1) # Enable power. (pins are managed by MICHA board)
            elif hardConf.localGPIOtype == "pigpio":
                # GPIO.setmode(GPIO.BOARD)
                # GPIO.setwarnings(False)
                # GPIO.setup(self.pinStatus, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                # GPIO.setup(self.pinDirection, GPIO.OUT)
                # GPIO.setup(self.pinPWM, GPIO.OUT)
                # self.pwm = GPIO.PWM(self.pinPWM, 1000)  # create PWM instance with frequency
                # self.pwm.start(0)  # keep PWM quiet for now. Should be 50 when running
                if self.pinStatus > 0:
                    hardConf.localGPIO.set_mode(self.pinStatus, hardConf.gpio_INPUT)
                    hardConf.localGPIO.set_pull_up_down(self.pinStatus, hardConf.gpio_PUD_UP)
                elif self.pinStatus < 0:
                    hardConf.io.set_pin_direction(-self.pinStatus, 1)
                    hardConf.io.set_pin_pullup(-self.pinStatus, 1)
                if self.pinDirection > 0:
                    hardConf.localGPIO.set_mode(self.pinDirection, hardConf.gpio_OUTPUT)
                else:
                    hardConf.io.set_pin_direction(-self.pinDirection, 0)
                # PWM is not possible through IOexpanding board...
                hardConf.localGPIO.set_mode(self.pinPWM, hardConf.gpio_OUTPUT)
                #hardConf.pi.set_mode(self.pinPWM, pigpio.ALT5)
                #hardConf.pi.set_PWM_dutycycle(self.pinPWM, 128)
                #hardConf.pi.set_PWM_frequency(self.pinPWM, 0)
                #hardConf.pi.hardware_PWM(self.pinPWM, 1,0)
            else:
                self.lastError = ReadPump_PWM.errors[3]
                OK = False
            if not self.maxSpeed:
                time.sleep(0.1)
            self.reset_volume()
            self.speed = 0.0
            self.speed_liters = 0.0
            return OK
        except:
            traceback.print_exc()
        return False

    def read_return(self):
        
        if hardConf.processor and hardConf.processor != 'pc' and not hardConf.MICHA_device:
            if self.pinStatus > 0:
                return 0 if hardConf.localGPIO.read(self.pinStatus) else 1
            else:
                return 0 if hardConf.io.read_pin( -self.pinStatus ) else 1
        else:
            return 0 # Always LOW

    def close(self):
        if hardConf.MICHA_device:
            hardConf.io.set_pump_power(0) # Disable power. (pins are managed by MICHA board)
        else:
            self.stop()
            time.sleep(0.1)
        self.speed = 0.0
        self.speed_liters = 0.0
        return True

    def run_liters(self, liters=None):
        if not liters:
            return False
        speed = self.litersHourSpeed(liters)
        return self.run(speed,liters)
    
    def setPWM(self,speed):
        duty = speed != 0
        #(" Speed=%d \r" % speed)
        if duty:
            if hardConf.MICHA_device:
                hardConf.io.write_pin(self.pinDirection, (0 if speed > 0 else 1) if hardConf.reversedPump else (1 if speed > 0 else 0) )
            else:
                if self.pinDirection > 0:
                    hardConf.localGPIO.write(self.pinDirection, 1 if speed > 0 else 0)
                elif self.pinDirection < 0:
                    hardConf.io.write_pin( -self.pinDirection, 1 if speed > 0 else 0)
            time.sleep(0.01)
            
        if hardConf.MICHA_device:
            hardConf.io.write_holding(self.pinPWM, self.speed_freq(speed if speed >= 0 else -speed) ) #, 500000 if duty else 0)
        elif hardConf.localGPIOtype == 'pigpio':
            status = hardConf.localGPIO.hardware_PWM(self.pinPWM,
                                                     self.speed_freq(speed if speed >= 0 else -speed) if duty else 1000,
                                                     500000 if duty else 0)
            if status:
                print(" PWM err=%d \r" % status)
        #hardConf.pi.set_PWM_frequency(self.pinPWM,self.speed_freq(speed))
        #hardConf.pi.set_PWM_dutycycle(self.pinPWM,32 if duty else 0) #128 is 50% but 32 seems to work and save energy and wear especially because we use 12V and not 5V...
        #print ("%d Hz" % hardConf.pi.get_PWM_frequency(self.pinPWM))
        
    def setSpeed(self,currSpeed,speed=0,reverse=False):
        if reverse:
            speed = -speed
        if (currSpeed < 0) and (speed > 0):
            self.setSpeed(currSpeed,0)
            self.setSpeed(0,speed)
        elif (currSpeed < 0) and (speed > 0):
            self.setSpeed(currSpeed,0)
            self.setSpeed(0,speed)
        else:
            if SPEED_INCREMENT:
                if speed > currSpeed:
                    while currSpeed < speed:
                        currSpeed = min([currSpeed+SPEED_INCREMENT,speed])
                        self.setPWM(currSpeed)
                        time.sleep(0.05)
                elif speed < currSpeed:
                    while currSpeed > speed:
                        currSpeed = max([currSpeed-SPEED_INCREMENT,speed])
                        self.setPWM(currSpeed)
                        time.sleep(0.05)
            else: #MICHA
               self.setPWM(speed)
               time.sleep(0.5)
        if speed == 0 and SPEED_INCREMENT:
            self.setPWM(0)
        
    def run(self, speed=None, liters = None):
        
        prvSpeed = -self.speed if self.reverse else self.speed
        print(" %s=%d \r" % (self.address,speed) )
        if speed is None:
            speed = self.maxSpeed
        running = True
        if self.speed ==0:
            running = False
        self.previous_volume = self.volume()
        self.previous_speed = -self.speed if self.reverse else self.speed
        self.previous_change = self.now
        if speed < 0:
            self.reverse = True
            self.speed = - speed # store positive version of speed
            if liters:
                self.speed_liters = -liters
            else:
                self.speed_liters = None
        elif speed > 0:
            self.reverse = False
            if speed >= self.speed:
                inc = True
            self.speed = speed
            self.speed_liters = liters
        if self.maxSpeed and self.speed > self.maxSpeed:
            self.speed = self.maxSpeed
            self.speed_liters = self.maximal_liters
        elif not self.speed_liters:
            self.speed_liters = self.speedLitersHour(self.speed)
        if hardConf.MICHA_device or hardConf.processor != 'pc':
            self.setSpeed(prvSpeed,self.speed,self.reverse)
            return True
        else:
            self.lastError = ReadPump_PWM.errors[3]
            return False

    def stop(self):
        
        #traceback.print_stack()
        print(" STOP %s \r"%self.address)
        if hardConf.MICHA_device or hardConf.processor != 'pc':
            try:
                self.setSpeed(-self.speed if self.reverse else self.speed, 0)
            except:
                traceback.print_exc()
            # GPIO.output(self.pinDirection, 1)
            # if self.pinDirection > 0:
                # hardConf.pi.write(self.pinDirection, 0)
            # elif self.pinDirection < 0:
                # self.IOextender.write_pin(-self.pinDirection, 0)
            # self.pwm.ChangeDutyCycle(0)  # keep PWM quiet for now. Should be 50 when running
            #hardConf.pi.set_PWM_dutycycle(self.pinPWM, 0)
            # self.setPWM(0)
            # time.sleep(0.01)
        else:
            self.lastError = ReadPump_PWM.errors[3]
        self.previous_volume = self.volume()
        self.previous_speed = -self.speed if self.reverse else self.speed
        self.reverse = False
        self.speed = 0.0
        self.speed_liters = 0.0
        self.previous_change = self.now
        return True

    def liters(self):
        if not self.speed:
            return 0.0
        liters = self.speed_liters;
        return (-liters if self.reverse else liters)

    def current_liters(self,now=None):
        if not now:
            now = time.perf_counter()
        rampTime = (( (-self.speed if self.reverse else self.speed) - self.previous_speed) / REAL_SPEED_INCREMENT) / 20.0 # 20 ramping increments per second
        previous_litersH = self.speedLitersHour(self.previous_speed)
        now_litersH = self.liters()
        elapsedTime = now-self.previous_change
        if elapsedTime < rampTime:
            rampVolume = (elapsedTime/3600.0) * (previous_litersH + ((elapsedTime/rampTime) * (now_litersH - previous_litersH) / 2.0))
            return rampVolume
        else:
            rampVolume = (rampTime/3600.0) * (previous_litersH + ((now_litersH - previous_litersH) / 2.0))
            return rampVolume + (now_litersH * ((elapsedTime-rampTime) / 3600.0))

    def volume(self):
        self.now = time.perf_counter()
        return self.previous_volume + self.current_liters(self.now)

    def reset(self): # Over reset in Sensor!
        now = time.perf_counter()
        new_vol = self.previous_volume + self.current_liters(now)
        entry = new_vol - self.prec_entry
        self.prec_entry = new_vol
        return entry

    def get(self): # Over get in Sensor!
        self.now = time.perf_counter()
        curr = self.current_liters(self.now)
        return self.previous_volume+curr, self.previous_change, curr

    def display(self,format=" %6.0fmL"): # Over display in Sensor!
        if self.reverse:
            attr = term.blue
        elif self.speed > 0.0:
            attr = term.yellow
        else:
            attr = term.black
        term.write(format % (self.volume()*1000.0), attr, term.bgwhite)

    def reset_volume(self):
        self.previous_change = time.perf_counter()
        self.previous_volume = 0.0

    def message(self):
        if self.lastError:
            return ("[%s, error=%s]" % (self.address, self.lastError))
        return ""

if __name__ == "__main__":

    RPM = True # False for liters

    TEST = True
    
    pumpy = pump_PWM()
    prec = time.perf_counter()
    precL = 0
    if not pumpy.open():
        print ("Not open!")
    else:
        print ("What "+pumpy.address+" can do for you?")

        Reading = None
        if not hardConf.MICHA_device and hardConf.MICHA_version < 40:
            Reading = ReadPump_PWM(pumpy)
            Reading.daemon = True
            Reading.start()

        prvError = "--"

        while True:
          try:
            time.sleep(0.5)
            if RPM:
                liters = input("RPM=").upper()
            else:
                liters = input("Liters/hour=").upper()
            now = time.perf_counter()
            print ("%.3f seconds  at %.2f L/hour = %dmL." % (now-prec,precL, int(precL*(now-prec)/3.600) ) )
            if liters == "":
                pass # go to read status...
            elif liters == "X":
                if Reading:
                    Reading.OK = False
                break
            elif liters == "?":
                print ("{-}"+("RPM" if RPM else "liters")+", 0, X=exit")
            else:  
                try:
                    liters = float(liters)
                    prec = now
                    precL = liters
                    if liters == 0:
                        if not pumpy.stop():
                           print ("Error stopping!")
                        print ("Stop!")
                    else:
                        if RPM:
                            if not pumpy.run(liters):
                                print ("Error running!")
                        else:
                            if not pumpy.run_liters(liters):
                                print ("Error running!")
                        precL = pumpy.liters()
                        #precL = pumpy.speed
                        print ("Speed=%.2f, %.2f L/hour" % (pumpy.speed,precL) )
                except:
                    traceback.print_exc()
                    print ("? for help...")

            time.sleep(0.3)
            if Reading:
                status = Reading.status()
            elif hardConf.MICHA_device and hardConf.MICHA_version < 40:
                status = hardConf.io.read_input(pumpy.pinStatus)
            else:
                status = "--"
            if status != prvError :
                if (status):
                    print( "Error=%d" % status )
                else:
                    print("Motor OK")
                prvError = status
          except KeyboardInterrupt:
              break
          except:
              traceback.print_exc()
              continue
                
        if not pumpy.stop():
            print ("Error stopping!")
        if not pumpy.close():
            print ("Error closing!")
        else:
            print ("Pump stopped and closed.")
        if hardConf.localGPIOtype == "pigpio":
            hardConf.localGPIO.cleanup()
            pass

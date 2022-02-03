#!/usr/bin/python3
# -*- coding: utf-8 -*-
import struct

import hardDependencies
if hardDependencies.Raspberry:
    import serial
import time
import math
import threading
import traceback
import sensor
import term

TEST = False

class PumpStatus(object):

    errors = ["none","Communication","TimeOut","Bad Parameter","Bad Address",
              "Bad Command","Bad Request","Motor Busy","Over Heating","Power Down",
              "Fatal Error"]
    requests = ["none","Status","Command","-3-","Maint"]
    
    def __init__(self):
        self.addr = None
        self.command = 0
        self.type = 0
        self.value = 0

    def repr(self):
        return ("[Pump %d, query %s.%d, value=%d]" % (self.addr, PumpStatus.requests[self.command] if self.command in PumpStatus.requests else str(self.command), self.type, self.value) )

class ReadPump(threading.Thread):
    
    global TEST

    def __init__(self, pump):
        threading.Thread.__init__(self)
        self.pump = pump
        self.buffer = b""
        self.lastStatus = None
        self.OK = True

    def close(self):
        self.OK = False

    def run(self):
        while self.OK and self.pump.pumpSerial:
            time.sleep(0.005)
            if self.pump.opened:
                try:
                    result = self.pump.pumpSerial.read(100)
                    if result:
                        self.buffer += result
                        #print ('['+str(result)+']')
                    elif len(self.buffer):
                        #self.print()
                        self.lastStatus = self.decodeStatus()
                except serial.serialutil.SerialException:
                    print ('no serial data')
                    pass
                except:
                    traceback.print_exc()
            else:
                time.sleep(5)
                someDelay = False

    def status(self):
        time.sleep(0.001)
        status = self.lastStatus
        self.lastStatus = None
        return status

    def decodeStatus(self):
        status = None
        time.sleep(0.001)
        if len(self.buffer):
            if self.buffer[0] == 0xFF: # anormal message
                status = PumpStatus()
                status.addr = self.pump.addr
                status.command = pump.REQUEST_STATUS
                status.type = pump.ERROR[0]
                status.value = 10 #Fatal error
                self.pump.lastError = status.value
                self.print() # ('['+str(self.buffer)+']')
                self.buffer = b""
                return status
        while len(self.buffer):
            if self.buffer[0] == 0xBD:
                self.buffer = self.buffer[1:]
            else:
                break
        while len(self.buffer):
            if self.buffer[0] == 0xFE:
                self.buffer = self.buffer[1:]
            else:
                break
        checksum = 0
        if len(self.buffer):
            if self.buffer[0] == 0x68:
                checksum += 0x68
                self.buffer = self.buffer[1:]
        if len(self.buffer):
            if self.buffer[0] in list(range(pump.baseAddr,pump.baseAddr+0x10)):
                checksum += self.buffer[0]
                self.buffer = self.buffer[1:]
        if len(self.buffer):
            if self.buffer[0] == 0x68:
                checksum += 0x68
                self.buffer = self.buffer[1:]
        if len(self.buffer) >= 4:
            status = PumpStatus()
            status.command = self.buffer[0]
            if status.command > 4:
                self.print() #(self.buffer)
                self.buffer = b''
                return status
            data_length = self.buffer[1]
            #print(" DL=%d" % data_length)
            status.addr = -1
            if self.buffer[2] in list(range(pump.baseAddr,pump.baseAddr+0x10)):
                status.addr = self.buffer[2] - pump.baseAddr
            status.type = self.buffer[3]-1 # response type is request type+1
            if len(self.buffer) >= (2+data_length):
                weight = 1
                status.value = 0
                for i in range(4, data_length+2):
                    status.value += self.buffer[i]*weight
                    weight = weight*256
            #print (status.repr())
            if len(self.buffer) >= data_length+2+1:
                for i in range(0, 2+data_length):
                    checksum += self.buffer[i]
                if self.buffer[2+data_length] == (checksum & 0xFF):
                    if status.command == pump.REQUEST_STATUS:
                        if status.type == pump.ERROR:
                            self.pump.lastError = status.value
                        elif status.type == pump.STATUS:
                            self.pump.running = status.value > 0
                    elif status.command == pump.REQUEST_COMMAND:
                        if status.type in [1,3,9]:
                            self.pump.lastError = status.value
                            if not self.pump.lastError:
                                self.pump.running = True
                        elif status.type == 7:
                            self.pump.running = False
                    elif status.command == pump.REQUEST_MAINTENANCE:
                        if status.type == 5:
                            self.pump.subdivision = status.value
                        elif status.type == 9:
                            self.pump.DAC = status.value
                        elif status.type == 0x19:
                            self.pump.maxSpeed = status.value * 0.75 # Under load, 75% power
                else:
                    print ("Read error, checksum %d != %d."%(checksum&0xFF,self.buffer[data_length+2]))
                    print (self.buffer)
                self.buffer = self.buffer[data_length+2+1:]
            else:
                print ("Not enough data in response?")
                self.print() # (self.buffer)
                self.buffer = b""
        else:
            self.print() # (self.buffer)
            self.buffer = b''
            return status
        if len(self.buffer):
            if self.buffer[0] == 0x16:
                self.buffer = self.buffer[1:]
        if len(self.buffer):
            self.print() # (self.buffer)
        return status

    def print(self):
        time.sleep(0.001)
        if not TEST:
            return
        if len(self.buffer):
            out = ""
            for c in self.buffer:
                out += "%x " % c
            print ("Answer: [ "+out+"]")
        time.sleep(0.001)

class pump(sensor.Sensor):

    typeNum = 4

    brand = "Kamoer"
    family = "KTS"
    synbeg = b"\xFE\xFE"
    synend = b"\x16"
    prefix_addr = b"\x68"
    baseAddr = 0xC0

    rotationSteps = 200*8  # Number of steps in a rotation x subdivision ? ...

    REQUEST_STATUS = 1
    ERROR = b"\x01"
    STATUS = b"\x03"

    REQUEST_COMMAND = 2
    RUN = b"\x01"
    DELIVER = b"\x03"
    STOP = b"\x07"
    SPEED = b"\x09"

    REQUEST_MAINTENANCE = 4
    SUBDIV = b"\x05"
    DAC = b"\x09"
    MAXSPEED = b"\x19"

    def __init__(self,
                 addr=0,
                 serialPort = "/dev/serial0",
                 bauds = 9600,
                 LitersHour_Speed = 200.0 / 65.45, # Old fashion way to calculate speed for single head, light load
                 maxSpeed = 275,
                 maximal_liters = None,
                 minimal_liters = 24.0
                 ):
        self.sensorType = pump.typeNum
        self.address = "P"+str(addr)
        self.prec_entry = 0.0
        self.addr = addr
        self.serialPort = serialPort
        self.bauds = bauds
        self.opened = False
        self.maxSpeed = maxSpeed
        self.minimal_liters = minimal_liters
        self.pumpSerial = None
        self.speed = 0.0
        self.speed_liters = 0.0
        self.reverse = False
        self.requestedVolume = None
        self.now = None
        self.previous_change = time.perf_counter()
        self.previous_volume = 0.0
        self.lastError = None
        self.running = False
        self.subdivision = 8
        self.DAC = None
        self.LitersHour_Speed = LitersHour_Speed
        if not maximal_liters:
            self.maximal_liters = self.speedLitersHour(self.maxSpeed)
        else:
            self.maximal_liters = maximal_liters

    set = None
    avg3 = None

    # Those two functions are not perfectly reciprocal: beware!
    def litersHourSpeed(self,liters):
        reverse = False
        if liters < 0:
            liters = -liters
            reverse = True
        speed = self.LitersHour_Speed * ( 8.291098 + (0.1099444*liters) + (0.004270619*liters*liters) )
        if reverse:
            speed = -speed
        return speed * 96.0 / 115.0 #Geraud

    def speedLitersHour(self,speed):
        reverse = False
        if speed < 0:
            speed = -speed
            reverse = True
        speed = speed / self.LitersHour_Speed
        LH = -2.286407 + (2.275162*speed) - (0.009631488*speed*speed)
        if LH <= 0.0:
            LH = 0.0
        elif reverse:
            LH = -LH
        return LH * 115.0 / 96.0 #Geraud
        
    def open(self):
        if self.opened:
            return True
        try:
            if hardDependencies.Raspberry:
                self.pumpSerial = serial.Serial(
                    self.serialPort, self.bauds, timeout=0.01)
            else:
                self.pumpSerial = None
            self.opened = True
            if not self.maxSpeed:
                time.sleep(0.1)
            self.reset_volume()
            self.speed = 0.0
            self.speed_liters = 0.0
            return True
        except:
            traceback.print_exc()
        return False
    
    def close(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        self.stop()
        time.sleep(0.1)
        self.pumpSerial.close()
        self.pumpSerial = None
        self.status = 0
        self.speed = 0.0
        self.speed_liters = 0.0
        return True

    def send (self, commandtype,command):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        time.sleep(0.01)
        out = pump.prefix_addr
        out += bytes([pump.baseAddr+self.addr])
        out += pump.prefix_addr
        out += bytes([commandtype,len(command)+1,pump.baseAddr+self.addr])
        out += command
        checksum = 0
        for c in out:
            checksum += c
        #print(pump.synbeg+out+bytes([checksum & 0xFF])+pump.synend)
        result = self.pumpSerial.write(pump.synbeg+out+bytes([checksum & 0xFF])+pump.synend)
        time.sleep(0.1)
        return result
        
    def run_liters(self, liters=None):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        if not liters:
            return False
        speed = self.litersHourSpeed(liters)
        return self.run(speed,liters)
        
    def run(self, speed=None, liters = None):
        print("run%d=%d" % (self.addr,speed) )
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        if speed is None:
            speed = self.maxSpeed
        running = True
        inc = False
        if self.speed:
            half = self.speed
        else:
            half = 0
            running = False
        if self.reverse:
            half = -half
        half = (half + speed) / 2.0
        self.previous_volume = self.volume()
        self.previous_change = self.now
        if speed < 0:
            if not self.reverse:
                half = 0.0
                self.reverse = True
            self.speed = - speed # store positive version of speed
            if liters:
                self.speed_liters = -liters
            else:
                self.speed_liters = None
        elif speed > 0:
            if self.reverse:
                half = 0.0
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
        if (half > 0.0) and running and inc:
            return self.send (pump.REQUEST_COMMAND, pump.SPEED \
                              +struct.pack('<f',self.speed) )
        else:
            if (half == 0.0) and running:
                #traceback.print_stack()
                self.send (pump.REQUEST_COMMAND, pump.STOP)
                time.sleep(0.2)
            return self.send (pump.REQUEST_COMMAND, pump.RUN+b"\x01" \
                              +( b"\x01" if self.reverse else b"\x00") \
                              +struct.pack('<ff',15,self.speed) # 15 was half...
                              +b"\x05\x00")

    def deliver_liters(self, qty=0.0): # deliver liters
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        if self.speed != 0.0:
            self.stop() # seems to be always necessary for good working
        self.requestedVolume = qty
        self.reverse = False
        if qty < 0.0:
            self.reverse = True
            qty = -qty
        self.speed = self.maxSpeed
        self.speed_liters = self.maximal_liters
        self.previous_volume = self.volume()
        self.previous_change = self.now
        return self.send (pump.REQUEST_COMMAND, pump.DELIVER+b"\x01" \
                          +( b"\x01" if self.reverse else b"\x00") \
                          +struct.pack('<iff',int(self.litersHourSpeed(qty*60.0)*pump.rotationSteps),15,self.speed) # 15 was speed/2.0
                          +b"\x05\x00\x00")

    def query_run(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        return self.send (pump.REQUEST_STATUS, pump.STATUS)

    def query_error(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        return self.send (pump.REQUEST_STATUS, pump.ERROR+b"\x00")

    def query_DAC(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        return self.send (pump.REQUEST_MAINTENANCE, pump.DAC)

    def query_subdiv(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        return self.send (pump.REQUEST_MAINTENANCE, pump.SUBDIV)

    def query_maxspeed(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        return self.send (pump.REQUEST_MAINTENANCE, pump.MAXSPEED)

    def stop(self):
        if not self.opened or not self.pumpSerial:
            self.opened = False
            return False
        self.previous_volume = self.volume()
        self.reverse = False
        self.speed = 0.0
        self.speed_liters = 0.0
        self.previous_change = self.now
        #traceback.print_stack()
        print("STOP#%d"%self.addr)
        return self.send (pump.REQUEST_COMMAND, pump.STOP)

    def liters(self):
        if not self.speed:
            return 0.0
        liters = self.speed_liters;
        return (-liters if self.reverse else liters)

    def current_liters(self,now=None):
        if not now:
            now = time.perf_counter()
        return self.liters() * ((now-self.previous_change) / 3600.0)

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
        if self.lastError is not None:
            if self.lastError < len(PumpStatus.errors):
                return ("Pump #"+str(self.addr)+": "+PumpStatus.errors[self.lastError])
        return ""

##def time.perf_counter():
##    now = time.time()
##    now = math.floor(float(now))
##    now = int(now)
##    return now

class double_pump(pump):
    def __init__(self,
                 addr0=0,
                 addr1=1,
                 inverse1=False,
                 serialPort = "/dev/serial0",
                 bauds = 9600,
                 LitersHour_Speed = 200.0 / 65.45, # Old fashion way to calculate speed for single head, light load
                 maxSpeed = 275, # 90 => 275.02 double head, loaded, gives about 124 L / hour
                 maximal_liters = None,
                 minimal_liters = 24.0
                 ):
        super().__init__(addr0,serialPort,bauds,LitersHour_Speed,maxSpeed,maximal_liters,minimal_liters)
        self.inverse1 =inverse1
        self.traction = 1.04 #1.13
        self.maximal_liters = self.speedLitersHour(self.maxSpeed)
        self.pump1 = pump(addr1,serialPort,bauds,LitersHour_Speed,maxSpeed*self.traction,self.maximal_liters,minimal_liters)

    # Those two functions are not perfectly reciprocal: beware!
    # RECALCULATED WITH A NEW CALIBRATION WITH TWO PUMPS INLINE:
    # y = 8.735073 + 1.087485*x + 0.005004839*x^2
    def litersHourSpeed(self,liters):
        reverse = False
        if liters < 0:
            liters = -liters
            reverse = True
        #speed = self.LitersHour_Speed * ( 8.291098 + (0.1099444*liters) + (0.004270619*liters*liters) )
        speed = 8.735073 + (1.087485*liters) + (0.005004839*liters*liters)
        if reverse:
            speed = -speed
        return speed

    #T RECALCULATED WITH A NEW CALIBRATION WITH TWO PUMPS INLINE:
    # y = -2.802961 + 0.7392672*x - 0.0007275534*x^2
    def speedLitersHour(self,speed):
        reverse = False
        if speed < 0:
            speed = -speed
            reverse = True
        #speed = speed / self.LitersHour_Speed
        #LH = -2.286407 + (2.275162*speed) - (0.009631488*speed*speed)
        LH = -2.802961 + (0.7392672*speed) - (0.0007275534*speed*speed)
        if LH <= 0.0:
            LH = 0.0
        elif reverse:
            LH = -LH
        return LH
        
    def open(self):
        if super().open():
            self.pump1.opened = True
            self.pump1.pumpSerial = self.pumpSerial
            return True
        else:
            self.pump1.opened = False
            self.pump1.pumpSerial = None
            return False

    def close(self):
        self.stop()
        self.pump1.opened = False
        time.sleep(0.1)
        return super().close()
        
    def stop(self):
        #print("stopD")
        if super().stop():
            time.sleep(0.1)
            self.pump1.stop()
            return True
        return False

    def run(self, speed=None, liters = None):
        #print("runD")
        if speed < 0:
            if super().run(speed*self.traction,liters):
                time.sleep(0.1)
                self.pump1.run( speed = None if speed is None else (-speed if self.inverse1 else speed), liters = None if liters is None else (-liters if self.inverse1 else liters) )
                return True
        else:
            if self.pump1.run( speed = None if speed is None else self.traction*(-speed if self.inverse1 else speed), liters = None if liters is None else (-liters if self.inverse1 else liters) ):
                time.sleep(0.1)
                super().run(speed,liters)
                return True
        return False

    def deliver_liters(self, qty=0.0): # deliver liters
        #print("dlvD")
        if self.pump1.deliver_liters(qty):
            time.sleep(0.1)
            super().deliver_liters(qty)
            return True
        return False

    def message(self):
        if self.lastError is not None:
            if self.lastError < len(PumpStatus.errors):
                return ("Pump #"+str(self.addr)+": "+PumpStatus.errors[self.lastError])
        if self.pump1.lastError is not None:
            if self.pump1.lastError < len(PumpStatus.errors):
                return ("Pump #"+str(self.pump1.addr)+": "+PumpStatus.errors[self.pump1.lastError])
        return ""

if __name__ == "__main__":

    TEST = True
    
    #pumpy = double_pump(addr0=0,addr1=1,inverse1=True)
    pumpy = pump()
    prec = time.perf_counter()
    precL = 0
    if not pumpy.open():
        print ("Not open!")
    else:
        print ("What a "+pump.brand+" "+pump.family+" pump can do for you?")

        Reading = ReadPump(pumpy)
        Reading.daemon = True
        Reading.start()

        while True:
          try:
            time.sleep(0.5)
            liters = input("Liters/hour=").upper()
            #liters = input("RPM=").upper()
            now = time.perf_counter()
            print ("%.3f seconds  at %.2f L/hour = %dmL." % (now-prec,precL, int(precL*(now-prec)/3.600) ) )
            if liters == "":
                pass # go to read status...
            elif liters == "X":
                Reading.OK = False
                break
            elif liters[0] == "D":
                liters = float(liters[1:])
                prec = now
                if not pumpy.deliver_liters(liters):
                    print ("Error delivering!")
                precL = pumpy.liters()
                print ("Deliver "+str(liters)+" L, max speed")
            elif liters == "A":
                if not pumpy.query_DAC():
                    print ("Error querying!")
            elif liters == "R":
                if not pumpy.query_run():
                    print ("Error querying!")
            elif liters == "S":
                if not pumpy.query_maxspeed():
                    print ("Error querying!")
            elif liters == "V":
                if not pumpy.query_subdiv():
                    print ("Error querying!")
            elif liters == "E":
                if not pumpy.query_error():
                    print ("Error querying!")
            elif liters == "?":
                print ("{D}{-}liters, 0, E=error, R=running?, X=exit, S=max RPM,a=DAC, v=Motor Subdiv.")
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
                        #if not pumpy.run(liters):
                        if not pumpy.run_liters(liters):
                            print ("Error running!")
                        precL = pumpy.liters()
                        #precL = pumpy.speed
                        print ("Speed=%.2f, %.2f L/hour" % (pumpy.speed,precL) )
                except:
                    traceback.print_exc()
                    print ("? for help...")

            time.sleep(0.3)
            status = Reading.status()
            if status and status.addr is not None:
                print( status.repr() )
                mess = pumpy.message()
                if mess:
                    print ("Error, "+mess)
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


#!/usr/bin/env python
import spidev
import traceback

import time
import pigpio
import MCP3201

import hardConf

class R_Meter:
        
        def calculate_r (self, Rx, IFB, Voltage,V2):
            Gain = (Voltage / self.Vin);
            #Gain = Voltage - self.Vin; #mV

            Rm = Rx * (Gain - 1);
            #Rm = Gain / IFB
            Rm = Rm - 2000; # Resistance of feedback
            print ("V0=%.1fmV, V2=%.1fmV, Ref=%d ohm, Gain=%.1f, Res=%.1f" % (Voltage,V2,Rx,Gain,Rm) )
            return Rm
            
        def ohm_200 (self, V):
            return (2.8297 * V) - 2280.287044

        def ohm_1000 (self, V):
            return (10.8985301 * V) - 3175.335463

        def ohm_100K (self, V):
            return (975.00339684 * V) - 96680.02904
            #return 1000 * (V-100)

        def ohm_10K (self, V):
            return 101.1175 * V - 12011.4

        def read_voltage_average( self, adcnum = 0, sampling = 3, delay=0.01 ):
            count = 0
            tot = 0.0
            minv = 4096.0
            maxv = -1.0
            retries = sampling*2
            while count < sampling and retries > 0:
                time.sleep(delay)
                try:
                    retries -= 1  # Avoid infinite loop if sensor is disconnected !
                    a0 = self.read3201(adcnum)
                    if a0 > 200.0 and a0 < 2048.0:
                        #print (a0)
                        count += 1
                        tot += a0
                        if a0 < minv:
                                minv = a0
                        if a0 > maxv:
                                maxv = a0
                except:
                    traceback.print_exc()
                    break                                

            if not count or count <= 2:
                return 0.0
            if minv > 2048:
                return 0.0
            if maxv < 0.0:
                return 0.0
            if minv == maxv:
                return 0.0   
            resul = (tot-minv-maxv) / (count-2)
            #print ("T=%d mn=%d mx=%d count=%d, mV=%d" % (tot, minv,maxv, count, resul) )
            return resul

        def r_meter_get_ohms( self, adcnum = 0  ):

            hardConf.pi.write(self.polarityIO, 0 if self.polarity else 1)
            self.polarity = not self.polarity

            #Rx = 283 #236
            #IFB = 71.82
            # GPIO.output(self.S1,GPIO.HIGH)
            # GPIO.output(self.S2,GPIO.LOW)
            # GPIO.output(self.S3,GPIO.LOW)
            hardConf.pi.write(self.S1, 1)
            hardConf.pi.write(self.S2, 0)
            hardConf.pi.write(self.S3, 0)
            time.sleep(0.1)

            Voltage = self.read_voltage_average(adcnum) #6

            #V2 = spi.read(0)
            #GPIO.output(self.S1,GPIO.LOW)
            hardConf.pi.write(self.S1, 0)
            
            if ( Voltage > 0 and Voltage < 2045 ):
                #return self.calculate_r(Rx,IFB,Voltage,V2)
                return self.ohm_200(Voltage),Voltage
            else:
                #Rx = 1100
                #IFB = 92.88
                # GPIO.output(self.S1,GPIO.LOW)
                # GPIO.output(self.S2,GPIO.HIGH)
                # GPIO.output(self.S3,GPIO.LOW)
                hardConf.pi.write(self.S1, 0)
                hardConf.pi.write(self.S2, 1)
                hardConf.pi.write(self.S3, 0)
                time.sleep(0.02)

                Voltage = self.read_voltage_average(adcnum) #6
                #V2 = spi.read(0)
                #GPIO.output(self.S2,GPIO.LOW)
                hardConf.pi.write(self.S2, 0)
                
                if (Voltage > 0 and Voltage < 2045 ):
                    #return self.calculate_r(Rx,IFB,Voltage,V2)
                    return self.ohm_1000(Voltage),Voltage
                else:
                    #Rx = 100000 #95000
                    #IFB = 100.0
                    # GPIO.output(self.S1,GPIO.LOW)
                    # GPIO.output(self.S2,GPIO.LOW)
                    # GPIO.output(self.S3,GPIO.HIGH)
                    hardConf.pi.write(self.S1, 0)
                    hardConf.pi.write(self.S2, 0)
                    hardConf.pi.write(self.S3, 1)
                    time.sleep(0.02)

                    Voltage = self.read_voltage_average(adcnum) #60
                    #V2 = spi.read(0)
                    #GPIO.output(self.S3,GPIO.LOW)
                    hardConf.pi.write(self.S3, 0)
                    if (Voltage > 0 and Voltage < 2047 ):
                        #return self.calculate_r(Rx,IFB,Voltage,V2)
                        return self.ohm_10K(Voltage),Voltage
            return 0,Voltage # Over Range

        def __init__(self, bus=0, spi_channel=0, bus2=1, spi_channel2=0, S1=25, S2=6, S3=5, polarityIO=16):
                #GPIO.setmode(GPIO.BCM)
                self.S1 = S1
                self.S2 = S2
                self.S3 = S3
                self.Vin = 100 # mV
                self.polarityIO = polarityIO
                self.polarity = False

                # GPIO.setup(self.S1, GPIO.OUT)
                # GPIO.setup(self.S2, GPIO.OUT)
                # GPIO.setup(self.S3, GPIO.OUT)
                # GPIO.output(self.S1,GPIO.LOW)
                # GPIO.output(self.S2,GPIO.LOW)
                # GPIO.output(self.S3,GPIO.LOW)
                hardConf.pi.set_mode(self.S1, pigpio.OUTPUT)
                hardConf.pi.set_mode(self.S2, pigpio.OUTPUT)
                hardConf.pi.set_mode(self.S3, pigpio.OUTPUT)
                hardConf.pi.set_mode(self.polarityIO, pigpio.OUTPUT)
                hardConf.pi.write(self.S1, 0)
                hardConf.pi.write(self.S2, 0)
                hardConf.pi.write(self.S3, 0)
                hardConf.pi.write(self.polarityIO, 0)
                    
                self.bus = bus
                self.spi_channel = spi_channel
                self.MCP3201 = MCP3201.MCP3201(self.bus, self.spi_channel) # SPI accessed at less than 1MHz
                
                # ~ try:   # PI3 clik board (not used)        
                        # ~ self.conn = spidev.SpiDev(bus2,spi_channel2)
                        # ~ self.conn.max_speed_hz = 1000000 # 1MHz
                # ~ except:
                        # ~ traceback.print_exc()

        def __del__( self ):
                self.close

        def close(self):
                self.MCP3201.close()
                # if self.conn != None:
                        # self.conn.close
                        # self.conn = None

        def read3201(self,adcnum=0):
            ADC_output_code = self.MCP3201.readADC_LSB()
            ADC_voltage = self.MCP3201.convert_to_voltage(ADC_output_code,VREF=2.048)
            return ADC_voltage*1000.0
               
        # For PI3 clik board (not used)        
        def bitstring(self, n):
                s = bin(n)[2:]
                return '0'*(8-len(s)) + s

        # Read by PI3 clik board (not used)        
        def read(self, adc_channel=0):
                # build command
                cmd  = 128 # start bit
                cmd +=  64 # single end / diff
                if adc_channel % 2 == 1:
                        cmd += 8
                if (adc_channel/2) % 2 == 1:
                        cmd += 16
                if (adc_channel/4) % 2 == 1:
                        cmd += 32

                # send & receive data
                reply_bytes = self.conn.xfer2([cmd, 0, 0, 0])

                #
                reply_bitstring = ''.join(self.bitstring(n) for n in reply_bytes)
                # print reply_bitstring

                # see also... http://akizukidenshi.com/download/MCP3204.pdf (page.20)
                reply = reply_bitstring[5:19]
                return int(reply, 2)

        # Read by PI3 clik board (not used)        
        def readadc(self,adcnum):
            spi = spidev.SpiDev()
            spi.open(1,0)
            # read SPI data from MCP3004 chip, 4 possible adc (0 thru 3)
            if ((adcnum > 3) or (adcnum < 0)):
                return-1
            r = spi.xfer2([1,8+adcnum <<4,0])
            spi.close()
            #print(r)
            adcout = ((r[1] &3) <<8)+r[2]
            return adcout 

if __name__ == '__main__':

        #data = open("RMETER.csv","a")

        count = 0
        try:
                while True:
                        count += 1
                        r,v = hardConf.Rmeter.r_meter_get_ohms(0)
                        print ("Ohm=%.0f; V=%.1f mV" % (r,v))
                        time.sleep(2)
        except:
                traceback.print_exc()
        #data.close()
        hardConf.Rmeter.close()
 

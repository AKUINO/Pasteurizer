#!/usr/bin/python3
# -*- coding: utf-8 -*-
# This module helps keeping track of measurements of "cohorts" of events and to take decision upon them
import time
import sensor
import datetime
import sched
import traceback
import math
import csv

class Cohort(object):

    def __init__(self,periodicity,depth):
        self.periodicity = periodicity # e.g. 3 seconds intervall between cohort data
        self.depth = depth # e.g. 100 x 3 seconds of data kept
        self.catalog = {} # Catalog of all sensors in the system with their last values and some historical data
        self.history = {} # Data from sensors
        self.history_base = time.perf_counter() # To synchronize all data series
        self.calibration = {} # Calibrations of sensors
        self.old_base = None # To synchronize all data series
        self.period = 0
        self.sequence = [] # sequence of sensors with their distance in L
        self.pumpAddress = None
        self.reft = sensor.Sensor(111,'reft',None) # Calibration data received by Internet

    def addSensor(self,address,sensor):
        self.addCatalog(address)
        self.catalog[address] = sensor

    def addCatalog(self,address):
        if not address in self.catalog:
            self.catalog[address] = None
            self.history[address] = [None] * self.depth            
            self.calibration[address] = []

    def nextPeriod(self):
        for address in self.history:
            self.history[address][self.period] = self.getCalibratedValue(address, self.catalog[address].reset())
        self.period += 1
        if self.period >= self.depth:
            self.old_base = self.history_base
            self.history_base = time.perf_counter()
            self.period = 0

    def previous_period(self,per):
        period = per - 1
        if period < 0:
            period = self.depth-1
        return period

    def last_period(self):
        period = self.period - 1
        if period < 0:
            period = self.depth-1
        return period

    def dump(self):
        per = self.last_period()
        total = 0
        for entr in self.sequence:
            val = self.history[entr[1]][per]
            total += entr[0]
            print("%2d: [%s] +%6.1fmL %7.5f°C" % (per,entr[1],entr[0],val if val else 0.0))
        print("    [TOTAL] =%6.1fmL" % total)

    def last_travel(self,address):
        per = self.last_period()
        pseq = 0
        for entr in self.sequence:
            if entr[1]==address:
                break
            pseq += 1
        if pseq >= len(self.sequence): # unknown address
            return None
        result = []
        volTotal = 0.0
        while True:
            entr = self.sequence[pseq]
            temp = self.history[entr[1]][per]
            if not temp:
                break
            result.insert(0,[per,entr[1],temp])
            volTube = entr[0]
            volTotal += volTube
            volPer = 0
            while True:
                vol = self.history[self.pumpAddress][per]
                if not vol:
                    break
                volPer += vol*1000.0
                if volPer >= volTube:
                    break
                per = self.previous_period(per)
                if per is None:
                    break
            pseq = pseq-1
            if pseq < 0:
                break
##        for entr in result:
##            print("%2d: [%s] %7.5f°C" % (entr[0],entr[1],entr[2]))
        return volTotal/1000.0,result

    def diff_time(self,beginPer,endPer):
        if endPer >= beginPer:
            return (endPer-beginPer)*self.periodicity
        else:
            return (endPer + (self.depth-beginPer))*self.periodicity

    # return the begin+end temperature between a begin and an arrival + time spent + volume transfered
    def evolution(self,begAddr,endAddr):
        begin = None
        end = None
        volTotal, tablo = self.last_travel(endAddr)
        for line in tablo:
            if line[1] == begAddr:
                begin = line[2]
                begPer = line[0]
            if line[1] == endAddr:
                end = line[2]
                endPer = line[0]
        if not begin or not end:
            return None,None,None,None
        return volTotal,self.diff_time(begPer,endPer),begin,end
        
    def saveCalibration(self,directory,address,means):
        try:
            data_file = open(directory + address+".csv", "w")
            for tuples in means:
                mean = tuples[1]
                data_file.write("%.1f\t%d\t%.3f\t%.3f\n" \
                            % (tuples[0],mean[0],mean[1],mean[2]) )
            self.calibration[address] = means
            data_file.close()
        except:
            traceback.print_exc()
            pass
        
    def readCalibration(self,directory,address):
        try:
            with open(directory + address+".csv") as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=['key','qty','app','tru'], delimiter="\t")
                means = []
                for row in reader:
                    means.append([float(row['key']),[int(row['qty']),float(row['app']),float(row['tru'])]])
                self.calibration[address] = means
                #print(means)
        except FileNotFoundError:
            print ('No calibration found for sensor "'+address+'" in directory '+directory)
        except:
            traceback.print_exc()
            pass
    def mergeCalibration(self,current_observ):
        # TODO: merge current calibration in future calibration: for one sensor only?
        #<a href="/calibrate/merge"><button class="btn btn-danger">$(ml.T("Fusionner Actuel","Merge Current","Huidige Samenvoegen"))</button></a> 
        return current_observ
        
    def getCalibratedValue(self,address,apparentValue=None):
        if not address in self.catalog:
            return None
        if apparentValue is None:
            apparentValue = self.catalog[address].value
            if apparentValue is None:
                return None
        #print("**A="+address)
        trueValue = apparentValue
        siz = len(self.calibration[address])
        if siz > 0:
            for i in range(siz):
                if apparentValue <= self.calibration[address][i][1][1]:
                    if i > 0:
                        p = self.calibration[address][i][1][1] - apparentValue
                        comp_p = apparentValue - self.calibration[address][i-1][1][1]
                        offset_bottom = self.calibration[address][i-1][1][2] - self.calibration[address][i-1][1][1]
                        offset_top = self.calibration[address][i][1][2] - self.calibration[address][i][1][1]
                        trueValue = apparentValue + ( ((offset_bottom*comp_p) + (offset_top*p)) / (self.calibration[address][i][1][1] - self.calibration[address][i-1][1][1]) )
                        #print("**%s=%.3f,p=%.3f,1-p=%.3f,ob=%.3f,ot=%.3f,adj=%.3f" % (address,apparentValue,p,comp_p,offset_bottom,offset_top,trueValue))
                        break
                    else:
                        trueValue = apparentValue - self.calibration[address][i][1][1] + self.calibration[address][i][1][2]
                        #print("**2="+str(trueValue))
                        break
                elif i == siz-1:
                    trueValue = apparentValue - self.calibration[address][i][1][1] + self.calibration[address][i][1][2]
                    #print("**3="+str(trueValue))
                    break
        #print("**4="+str(trueValue))
        return trueValue

    def val(self,address,format="%.2f",peak=0):
        if not address in self.catalog:
            return ""
        sensor = self.catalog[address]
        if not sensor.value:
            return ""
        else:
            if peak == 0:
                return format % self.getCalibratedValue(address)
            elif peak < 0:
                return format % self.getCalibratedValue(address,apparentValue=sensor.min)
            else: # peak > 0:
                return format % self.getCalibratedValue(address,apparentValue=sensor.max)

    def display(self,term,address,format=" %5.2f°C"):
        if not address in self.catalog:
            return
        sensor = self.catalog[address]
        if sensor.changed < 0.0:
            attr = term.blue
        elif sensor.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        if sensor.value:
            term.write(format % self.getCalibratedValue(address), attr, term.bgwhite)

if __name__ == "__main__":
    cohort = Cohort(3,10)
    cohort.addSensor("1",sensor.Sensor("X","1","params"))
    cohort.addSensor("2",sensor.Sensor("X","2","params"))
    i = 0
    while (True):
        cohort.catalog["1"].set(time.time() % 60)
        cohort.catalog["1"].set(i % 11)
        i += 1
        time.sleep(1.11)
                     
    

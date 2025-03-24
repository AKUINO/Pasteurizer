#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import datafiles
import json
import pandas
import numpy.polynomial
import traceback
import hardConf
import os

import ml

class Pump_Calibration:
# implements option "L" and replaces options:
#                   'E':['E',ml.T("Amont(mL)","Upstream(mL)","StroomOPwaarts(mL)") \
#                          ,ml.T("Volume des tuyaux en amont(cm*0,7854*d²)","Upstream Pipes Volume(cm*0,7854*d²)","StroomOPwaarts leidingvolume(cm*0,7854*d²)") \
#                          ,0.0,0.0,'mL',False,2000,1,"number"],  # Volume des tuyaux en entrée du pasteurisateur
#                   'S':['S',ml.T("Aval(mL)","Downstream(mL)","StroomAFwaarts(mL)") \
#                          ,ml.T("Volume des tuyaux en aval(cm*0,7854*d²)","Downstream Pipes Volume(cm*0,7854*d²)","StroomAFwaarts leidingvolume(cm*0,7854*d²)") \
#                          ,0.0,0.0,'mL',False,15000,1,"number"],  # Volume des tuyaux en sortie du pasteurisateur

    def __init__(self):
        self.id = '0'
        self.ongoing = False # Calibration currently done: stops all other operations !
        self.description = str(ml.T("Initial","Default","Startwaarde"))
        self.uphill = 0.0 # mL added before pasteurization point
        self.downhill = 0.0 # mL added after pasteurization point
        self.maxRPM = hardConf.pumpMaxRPM
        self.stepRPM = 50 # 50, 100, 150, 200, 250, 300, 350, Max RPM...
        self.timeslice = 15 # seconds between each "bip" to measure water quantity pumped
        self.newRPM = None # if a new RPM row has to be displayed
        self.measures:pandas.DataFrame = None  # array of measures kept sorted by RPM and then by date: each are a RPM, a date and a number of liters/hour
        # Liters/hour = a*RPM² + b*RPM + c LH = -9.831412 + (0.9269884*speed) - (0.0004694142*speed*speed)
        self.RPM_to_LH = numpy.polynomial.Polynomial([-9.831412,0.9269884,-0.0004694142])
        # RPM = ra*LH² + rb*LH + rc
        # speed = 12.28124 + (1.03637*liters) + (0.001046376*liters*liters)
        self.LH_to_RPM = numpy.polynomial.Polynomial([12.28124,1.03637,0.001046376])
        self.maximal_liters = self.RPM_to_LH(self.maxRPM)
        self.currspeed = 0 # last speed requested (RPM)
        self.tap_open = None # time when water tap was opened (tap timing)

    def __str__(self):
        return 'Pump LH='+str(self.RPM_to_LH)+", RPM="+str(self.LH_to_RPM)+", MaxRPM="+str(self.maxRPM)+(", "+str(self.measures.shape[0])+" measures" if self.measures is not None else "")

    def to_dict(self):
        return {
         'maxRPM' : self.maxRPM
         ,'description' : self.description
         ,'stepRPM' : self.stepRPM
         ,'timeslice' : self.timeslice
         ,'uphill' : self.uphill # mL
         ,'downhill' : self.downhill # mL
         ,'measures' : self.measures.to_dict() if self.measures is not None else None
         ,'RPM_to_LH' : self.RPM_to_LH.coef.tolist() if self.RPM_to_LH is not None else None
         ,'LH_to_RPM' : self.LH_to_RPM.coef.tolist() if self.LH_to_RPM is not None else None
        }

    def from_dict(self,input):
        self.maxRPM = input['maxRPM']
        self.description = input['description']
        self.stepRPM = input['stepRPM']
        self.timeslice = input['timeslice']
        self.uphill = input['uphill'] # mL
        self.downhill= input['downhill'] # mL
        self.measures = pandas.DataFrame.from_dict(input['measures']) if input['measures'] is not None else None
        self.RPM_to_LH = numpy.polynomial.Polynomial(input['RPM_to_LH']) if input['RPM_to_LH'] is not None else None
        self.LH_to_RPM = numpy.polynomial.Polynomial(input['LH_to_RPM']) if input['LH_to_RPM'] is not None else None

    # Fonction pour sauvegarder un objet de la classe courante en utilisant JSON : normalement on édite les JSON a la main !
    def save(self, interpolate = False, config=0):
        if interpolate and self.measures is not None:
            self.RPM_to_LH = numpy.polynomial.Polynomial.fit(self.measures["RPM"].tolist(), self.measures["LH"].tolist(), 2).convert()
            self.LH_to_RPM = numpy.polynomial.Polynomial.fit(self.measures["LH"].tolist(), self.measures["RPM"].tolist(), 2).convert()
        self.maximal_liters = self.RPM_to_LH(self.maxRPM)
        print(self.maxRPM,'RPM = ',self.maximal_liters,' Liters/hour')
        with open(datafiles.linearfile("pump"+str(config)), 'w') as f:
            #print(json.dumps(self.to_dict()))
            self.id = config
            json.dump(self.to_dict(),f)

    # Fonction pour lire un objet de la classe courante depuis le disque en utilisant JSON
    def load(self,config=0):
        self.id = int(float(str(config)))
        try:
            with open(datafiles.linearfile("pump"+str(self.id)), 'r') as f:
                objdict = json.load(f)
                self.from_dict(objdict)
                print("Load "+str(self))
            return True
        except:
            traceback.print_exc()
            return False

    @staticmethod
    def scale_mL_to_LH(seconds, mL): # Liters per hour from milliliters during some seconds
        return (mL / seconds) * 3.6 # 3600 seconds/hour / 1000 mL/liter

    @staticmethod
    def scale_LH_to_mL(self,seconds,LH): # mL per time slice of some seconds
        return (LH / 3.6) * seconds # 3600 seconds/hour / 1000 mL/liter

    def get(self): # returns three lists of measures (time, RPM and LH)
        if self.measures is None:
            return [],[],[]
        else:
            return self.measures["time"].tolist(), self.measures["RPM"].tolist(), self.measures["LH"].tolist()

    def get_spaced(self): # returns three lists of measures (time, RPM and LH) with place holders for RPM remaining to collect
        t = []
        r = []
        l = []
        if self.measures is None or self.measures.shape[0] < 1:
            if self.maxRPM >= self.stepRPM:
                for i in range(self.stepRPM, self.maxRPM+1, self.stepRPM):
                    t.append(None)
                    l.append(None)
                    r.append(i)
        else:
            prev = self.stepRPM
            rpms = self.measures["RPM"].tolist()
            for j in range(0,self.measures.shape[0]):
                rpm = rpms[j]
                if prev < min(rpm,self.maxRPM):
                    for i in range(prev, min(rpm,self.maxRPM), self.stepRPM):
                        t.append(None)
                        l.append(None)
                        r.append(i)
                r.append(rpm)
                t.append(self.measures["time"].tolist()[j])
                l.append(self.measures["LH"].tolist()[j])
                prev = int(rpm/self.stepRPM)*self.stepRPM
                if prev <= rpm:
                    prev = prev+self.stepRPM
            if self.maxRPM > prev:
                for i in range(prev, self.maxRPM+1, self.stepRPM):
                    t.append(None)
                    l.append(None)
                    r.append(i)
        return t,r,l

    def get_graph(self): # returns three lists of measures (time, RPM and LH)
        points = []
        if self.measures is not None:
            r = self.measures['RPM'].tolist()
            l = self.measures['LH'].tolist()
            for i in range(self.measures.shape[0]):
                points.append("cx="+str(int(r[i]*5/6))+" cy="+str(400-int(l[i])))
        return points

    def get_graph_formula(self): # returns three lists of measures (time, RPM and LH)
        line = ""
        for i in range(0,self.maxRPM+1,self.stepRPM):
            line += str(i*5/6)+','+str(int(400-self.RPM_to_LH(i)))+' '
        return line

    def add (self, rpm, lh):
        global last_add
        if 0 < rpm <= self.maxRPM and lh > 0:
            now = datetime.datetime.now(datetime.timezone.utc).timestamp()
            data = {
                "time" : now,
                "RPM" : rpm,
                "LH" : lh
            }
            df = pandas.DataFrame([data])
            if self.measures is None:
                self.measures = df
            else:
                self.measures = pandas.concat([self.measures, df], ignore_index=True).sort_values(["RPM","time"])
            return now
        else:
            return 0

    def remove (self,timestamp):
        if self.measures is None:
            return False
        else:
            try:
                self.measures = self.measures.drop(self.measures[self.measures['time']==timestamp].index, axis="rows")
                return True
            except:
                traceback.print_exc()
                return False

    def index(self): # Returns [['0', 'Initial'], ['1', 'Modifié'], ... ] based on the configurations in "param" directory
        result = {}
        try:
            for filename in os.listdir(datafiles.DIR_DATA_CALIB):
                if filename.startswith("pump"):
                    pext = filename.index(".json")
                    if pext > 0:
                        config = filename[pext-1]
                        if '0' <= config <= '9':
                            fullpath = os.path.join(datafiles.DIR_DATA_CALIB, filename)
                            if os.path.isfile(fullpath) :
                                with open(fullpath, 'r') as f:
                                    objdict = json.load(f)
                                    result[int(config)] = objdict['description'] if 'description' in objdict else "+++"
        except:
            traceback.print_exc()
            print ('Error accessing '+datafiles.DIR_DATA_CALIB+' directory')
            pass
        return result

if __name__ == "__main__":
    speed = hardConf.pumpMaxRPM+0.0
    print (speed,"RPM,LH=",-9.831412 + (0.9269884*speed) - (0.0004694142*speed*speed))
    liters = 271.777777
    print (liters,"LH, RPM=",12.28124 + (1.03637*liters) + (0.001046376*liters*liters))
    calib = Pump_Calibration()
    print (calib)
    lh = calib.RPM_to_LH(calib.maxRPM+0.0)
    print(calib.maxRPM,"RPM,LH=",lh)
    rpm = calib.LH_to_RPM(lh)
    print(lh,"LH,RPM=",rpm)
    rpm = calib.LH_to_RPM(liters)
    print(liters,"LH,RPM=",rpm)
    print(calib.index())
    calib.load()
    calib.maxRPM = 1000
    calib.description = "Modifié"
    calib.add(150,100)
    x=calib.add(300,200)
    calib.add(450,300)
    calib.add(600,400)
    print("drop")
    print("x=",x)
    calib.remove(x)
    t,r,l = calib.get()
    print (len(t),len(r),len(l))
    #for i in range(0, len(t)):
    print("time=",t)
    print("RPM=",r)
    print("LH=",l)
    #print("drop")
    #calib.remove(x)
    # id,t,r,l = calib.get()
    # for i in range(0, len(t)):
    #     print(t[i], r[i], l[i])
    calib.save(True,1)
    print("200LH,RPM=",calib.LH_to_RPM(200))
    print("400RPM,LH=",calib.RPM_to_LH(400))
    print(calib.maxRPM,"RPM,LH=",calib.RPM_to_LH(calib.maxRPM))
    print("END.")

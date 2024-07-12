#!/usr/bin/python3
# -*- coding: utf-8 -*-

import math
import os

import Heating_Profile
import datafiles
import json
import traceback

import hardConf

DEFAULT_REDUCTION = 5.0 # Log10 of the desired bacterial reduction
lines = {}
minTime = 0.0
maxTime = 9999.9
ref_speed = 0.0
ref_temp = 0.0
ref_tag = 'L'
ref_ratio = 1.0
ref_duration = 15.0

class Dt_line:

    # def __init__(self):
    #     self.t = None
    #     self.Dt = 0.0
    #     self.z = None
    #     self.reduction = DEFAULT_REDUCTION
    #     self.address = None
    #     self.source = None
    #     self.tags = []

    def __init__(self,t,Dt,z,reduction=DEFAULT_REDUCTION):
        self.t = t # seconds
        self.Dt = Dt # °C
        self.z = z # °C
        self.reduction = reduction # Log10
        self.address = None
        self.source = None
        self.tags = []

    def __str__(self):
        return self.address+": D"+str(self.Dt)+"°="+str(self.t)+'", z='+str(self.z)+'°C, tags='+','.join(self.tags)+", source="+(self.source if self.source else "")

    def to_dict(self):
        return {
         't' : self.t
         ,'Dt' : self.Dt
         ,'z' : self.z
         ,'reduction' : self.reduction
         ,'address' : self.address
         ,'source' : self.source
         ,'tags' : self.tags
        }

    def getByAddress(address):

        global lines

        if not address in lines.keys():
            return None
        else:
            return lines[address]

    def get_Dt(self):
        global ref_temp
        return self.Dt if self.Dt != 0.0 else ref_temp

    def minTemp(self):
        temp = self.get_Dt() - (math.log10(maxTime / (self.reduction * self.t)) * self.z)
        #addr,dur = tagged_time_to_kill(temp,"Y")
        #print ("max.sec="+str(maxTime)+'", temp='+str(int(temp))+', '+addr+'='+str(dur)+'"')
        return temp

    def maxTemp(self):
        temp = self.get_Dt() - (math.log10(minTime / (self.reduction * self.t)) * self.z)
        #addr,dur = tagged_time_to_kill(temp,"Y")
        #print ("min.sec="+str(minTime)+'", temp='+str(int(temp))+', '+addr+'='+str(dur)+'"')
        return temp

    def real_reduction(self):
        return self.reduction * ref_ratio

    # Fonction pour sauvegarder un objet de la classe courante en utilisant JSON : normalement on édite les JSON a la main !
    def save(self):
        with open(datafiles.dtzfile(self.address), 'w') as f:
            #print(json.dumps(self.to_dict()))
            json.dump(self.to_dict(),f)

    def validate_tags(self):
        OK = True
        for tag in self.tags:
            if tag not in Heating_Profile.profiles:
                OK = False
                print(self.address+': Tag '+tag+' is not an heating profile.')
        return OK

    def set_address(self,address):

        global lines

        if self.address != address:
            if self.address:
                del lines[self.address]
                # try:
                #     os.remove(datafiles.dtzfile(self.address))
                # except:
                #     pass

        if address is not None:
            self.address = address
            lines[address] = self
            #self.save() DTZ FILES ARE READ ONLY BY DEFAULT

    # Returns the time in seconds to get the desired log reduction at a given temperature
    def D_kill(self,temp):
        duration = self.reduction * self.t * (10.0 ** ((self.get_Dt() - temp) / self.z) )
        #print (self.address+": "+str(temp)+"°C = "+str(duration)+"sec.")
        return duration

    def include(self, criteria):
        return eval(criteria)

    def include_tag(self, tag: str):
        tag = tag.upper()
        try:
            x = self.tags.index(tag) >= 0
            return x
        except:
            return False

# Fonction pour lire un objet de la classe courante depuis le disque en utilisant JSON
def load():
    #filenames = []
    try:
        for filename in os.listdir(datafiles.DIR_BASE_DTZ):
            pext = filename.index(".json")
            if pext > 0:
                fullpath = os.path.join(datafiles.DIR_BASE_DTZ, filename)
                if os.path.isfile(fullpath) and not filename.startswith('profile_') :
                    with open(fullpath, 'r') as f:
                        objdict = json.load(f)
                        newDTZ = Dt_line(objdict['t'],objdict['Dt'],objdict['z'],objdict['reduction'] if 'reduction' in objdict else DEFAULT_REDUCTION)
                        newDTZ.source = objdict['source']
                        newDTZ.tags = objdict['tags']
                        newDTZ.set_address(filename[:pext])
                        print("Load "+str(newDTZ))
                        newDTZ.validate_tags()
    except:
        traceback.print_exc()
        print ('Error accessing '+datafiles.DIR_BASE_DTZ+' directory')
        pass

    try:
        for filename in os.listdir(datafiles.DIR_PRIV_DTZ):
            pext = filename.index(".json")
            if pext > 0:
                fullpath = os.path.join(datafiles.DIR_PRIV_DTZ, filename)
                if os.path.isfile(fullpath) and not filename.startswith('profile_') :
                    with open(fullpath, 'r') as f:
                        objdict = json.load(f)
                        newDTZ = Dt_line(objdict['t'],objdict['Dt'],objdict['z'],objdict['reduction'] if 'reduction' in objdict else DEFAULT_REDUCTION)
                        newDTZ.source = objdict['source']
                        newDTZ.tags = objdict['tags']
                        newDTZ.set_address(filename[:pext])
                        print("Load private "+str(newDTZ))
                        newDTZ.validate_tags()
    except:
        traceback.print_exc()
        print ('Error accessing '+datafiles.DIR_PRIV_DTZ+' directory')
        pass


def set_pump(pump):

    global maxTime, minTime

    maxTime = (3600.0 * hardConf.holding_volume) / (pump.minimal_liters * 1000.0)
    minTime = (3600.0 * hardConf.holding_volume) / (pump.maximal_liters * 1000.0)

def set_ref_speed(speed):

    global ref_speed, ref_duration

    ref_speed = speed
    ref_duration = hardConf.holding_volume / ( speed*1000.0/3600.0 )
    print("ref_duration="+str(ref_duration))

def set_ref_temp(temp,tag):

    global ref_temp, ref_ratio, ref_duration

    if not temp:
        return None
    #ref_tag = tag
    ref_temp = temp
    address,base_duration = tagged_time_to_kill(temp,tag)
    #print(address+": duration="+str(base_duration))
    if base_duration > 0.0:
        ref_ratio = ref_duration / base_duration
        #print("ref_ratio="+str(ref_ratio))
        return ref_ratio
    return None

load()

# if not 'Coxiella_burnetii' in lines.keys():
#     newDt = Dt_line(36,65.6,5.5,DEFAULT_REDUCTION+(15/12.35))
#     newDt.tags.append('L')
#     newDt.set_address('Coxiella_burnetii')
#
# # Mycobacterium avium paratuberculosis
# if not 'MAP' in lines.keys():
#     newDt = Dt_line(2.03,72.0,8.6,DEFAULT_REDUCTION+(15/12.35))
#     newDt.tags.append('L')
#     newDt.set_address('MAP')
#
# # Listeria
# if not 'Listeria' in lines.keys():
#     # 5 log reduction of Listeria is not possible with thermization
#     newDt = Dt_line(19.8,65.6,6.7,DEFAULT_REDUCTION-(43.39/15))
#     newDt.tags.append('T')
#     newDt.set_address('Listeria')
#
# # Yaourt 89°C: only adjust to recover equilibrium (10% margin added)
# if not 'Yoghurt 89' in lines.keys():
#     newDt = Dt_line(15.0,89.0,17.0,1.1)
#     newDt.tags.append('Y89')
#     newDt.set_address('Yoghurt 89')
#
# # Yaourt 89°C: only adjust to recover equilibrium (10% margin added)
# if not 'Yoghurt 85' in lines.keys():
#     newDt = Dt_line(15.0,85.0,17.0,1.1)
#     newDt.tags.append('Y85')
#     newDt.set_address('Yoghurt 85')

def max_time_to_kill(temp,criteria):
    time_to_kill = -1.0
    killingAddress = ""
    for (address, itemDt) in lines.items():
        if itemDt.include(criteria):
            t2k = itemDt.D_kill(temp)
            if t2k > time_to_kill:
                killingAddress = address
                time_to_kill = t2k
    return killingAddress,(time_to_kill if time_to_kill >= 0.0 else None)

def tagged_time_to_kill(temp,tag):
    time_to_kill = -1.0
    killingAddress = None
    for (address, itemDt) in lines.items():
        if itemDt.include_tag(tag):
            t2k = itemDt.D_kill(temp)
            if t2k > time_to_kill:
                killingAddress = address
                time_to_kill = t2k
    #print (killingAddress+"="+str(time_to_kill)+'"')
    return killingAddress,(time_to_kill if time_to_kill >= 0.0 else None)

def scaled_time_to_kill(temp,tag):

    global ref_ratio

    address,time_to_kill = tagged_time_to_kill(temp,tag)
    return address,(time_to_kill*(ref_ratio if ref_ratio else 1.0) if time_to_kill >= 0.0 else None)

def tag_index():
    tags = {}
    for (address, itemDt) in lines.items():
        for tag in itemDt.tags:
            if tag not in tags.keys():
                tags[tag] = []
            tags[tag].append(itemDt)
    return tags

# LEGAL_LOG_REDUCTION = 5.0 # 10^5 reduction of bacterias
#
# LEGAL_PAST = [63.0, 72.0, 89.0]
# LEGAL_TIME = [1800.0, 15.0, 1.0]
# LEGAL_KILL = [max_time_to_kill(LEGAL_PAST[0], "'_LEGAL_' in self.tags")[1]
#               ,max_time_to_kill(LEGAL_PAST[1], "'_LEGAL_' in self.tags")[1]
#               ,max_time_to_kill(LEGAL_PAST[2], "'_LEGAL_' in self.tags")[1] ]
# LEGAL_RATIO = [LEGAL_TIME[0] / LEGAL_KILL[0], LEGAL_TIME[1] / LEGAL_KILL[1], LEGAL_TIME[2] / LEGAL_KILL[2] ]
#
# # We do not take into account 89.0°C / 1 second anymore as it overheats over 72°C and destroys peroxidase.
# # We must not heat the heating bath over 75°C as it will promote over heating.
# def legal_safe_time_to_kill(temp):
#     address,time_needed = max_time_to_kill(temp, "'_LEGAL_' in self.tags")
#     if temp <= LEGAL_PAST[0]:
#         return LEGAL_RATIO[0] * time_needed
#     elif temp <= LEGAL_PAST[1]:
#         return time_needed * ((LEGAL_RATIO[0]*(LEGAL_PAST[1]-temp))+(LEGAL_RATIO[1]*(temp-LEGAL_PAST[0])))/(LEGAL_PAST[1]-LEGAL_PAST[0])
#     #elif temp < LEGAL_PAST[2]:
#     #    return time_needed * ((LEGAL_RATIO[1]*(LEGAL_PAST[2]-temp))+(LEGAL_RATIO[2]*(temp-LEGAL_PAST[1])))/(LEGAL_PAST[2]-LEGAL_PAST[1])
#     else:
#         #return LEGAL_RATIO[2] * time_needed
#        return LEGAL_RATIO[1] * time_needed
#
# #print("Legal72="+str(legal_safe_time_to_kill(72.0))+" sec.")

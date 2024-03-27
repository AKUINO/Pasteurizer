#!/usr/bin/python3
# -*- coding: utf-8 -*-

import menus

import datafiles
import json
import os
import ml

import traceback

profiles = {}

class Heating_Profile:

    def set_letter(self,letter):

        global profiles

        if self.letter != letter:
            if self.letter:
                del profiles[self.letter]
                # try:
                #     os.remove(datafiles.dtzfile(self.letter))
                # except:
                #     pass

        if letter is not None:
            self.letter = letter
            profiles[letter] = self

    def __init__(self,letter,temp,duration, FR, EN, NL):
        self.letter = None
        self.temp = temp
        self.duration = duration
        self.label = ml.T(FR,EN,NL)
        self.set_letter(letter)

    def __str__(self):
        return self.letter+": "+str(self.temp)+"°C, "+str(self.duration)+'" : '+self.label.french

    def to_dict(self):
        return {
         'letter' : self.letter
         ,'temp' : self.temp
         ,'duration' : self.duration
         ,'FR': self.label.french
         ,'EN': self.label.english
         ,'NL': self.label.dutch
        }

    def getByLetter(self,letter):

        global profiles

        if letter not in profiles.keys():
            return None
        else:
            return profiles[letter]

    # Fonction pour sauvegarder un objet de la classe courante en utilisant JSON : normalement on édite les JSON a la main !
    def save(self):
        with open(datafiles.dtzfile('profile_'+self.letter), 'w') as f:
            #print(json.dumps(self.to_dict()))
            json.dump(self.to_dict(),f)

# Fonction pour lire un objet de la classe courante depuis le disque en utilisant JSON
def load():
    #filenames = []
    try:
        for filename in os.listdir(datafiles.DIR_BASE_DTZ):
            pext = filename.index(".json")
            if pext > 0:
                fullpath = os.path.join(datafiles.DIR_BASE_DTZ, filename)
                if os.path.isfile(fullpath) and filename.startswith('profile_') :
                    with open(fullpath, 'r') as f:
                        objdict = json.load(f)
                        newDTZ = Heating_Profile(objdict['letter'],objdict['temp'],objdict['duration'],objdict['FR'],objdict['EN'],objdict['NL'])
                        newDTZ.set_letter(filename[len('profile_'):pext])
                        print("Load "+str(newDTZ))
    except:
        traceback.print_exc()
        print ('Error accessing '+datafiles.DIR_BASE_DTZ+' directory')
        pass
    try:
        for filename in os.listdir(datafiles.DIR_PRIV_DTZ):
            pext = filename.index(".json")
            if pext > 0:
                fullpath = os.path.join(datafiles.DIR_PRIV_DTZ, filename)
                if os.path.isfile(fullpath) and filename.startswith('profile_') :
                    with open(fullpath, 'r') as f:
                        objdict = json.load(f)
                        newDTZ = Heating_Profile(objdict['letter'],objdict['temp'],objdict['duration'],objdict['FR'],objdict['EN'],objdict['NL'])
                        newDTZ.set_letter(filename[len('profile_'):pext])
                        print("Load private "+str(newDTZ))
    except:
        traceback.print_exc()
        print ('Error accessing '+datafiles.DIR_PRIV_DTZ+' directory')
        pass


def setProfile(letter, menus_param : menus):

    global profiles

    if letter in profiles.keys():
        prof = profiles[letter]
        menus_param.store('z', letter)
        menus_param.store('P', prof.temp)
        menus_param.store('M', prof.duration)
        #menus.store('F', prof.letter)
        menus_param.save()

# Heating_Profile('T',68.0,15.0,"Thermiser","Thermize","Thermis.")
# Heating_Profile('L',72.0,15.0,"Lait","miLk","meLk")
# Heating_Profile('J',75.0,15.0,"Jus+Crème","Juices+Cream","Saap+Room")
# Heating_Profile('Y',89.0,15.0,"Yaourt","Yogurt","Yoghurt")
# for (letter, prof) in profiles.items():
#     with open(datafiles.dtzSharedFile('profile_'+prof.letter), 'w') as f:
#         #print(json.dumps(self.to_dict()))
#         json.dump(prof.to_dict(),f)

load()

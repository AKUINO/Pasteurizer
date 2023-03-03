#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import datetime
import traceback
import owner

import datafiles
import os
import json

import menus

# Fonction pour lister les fichiers d'un répertoire et retourner une liste de noms de fichiers
def list_reports(dummy = None):
    filenames = []
    for filename in os.listdir(datafiles.DIR_DATA_REPORT):
        if os.path.isfile(os.path.join(datafiles.DIR_DATA_REPORT, filename)):
            pext = filename.index(".json")
            if pext > 0:
                filenames.append(filename[:pext])
    return reversed(sorted(filenames))

# Fonction pour lire un objet de la classe courante depuis le disque en utilisant JSON
def load(reportname):
    #print(reportname)
    try:
        with open(datafiles.reportfile(reportname), 'r') as f:
            objdict = json.load(f)
            #print(objdict)
        return Report(None).from_dict(objdict)
    except:
        pass
    return None

class Report(object): # Info about the Owner of the Pasteurizee

    def __init__(self, menuOptions:menus.Menus = None):
        self.batch = None
        self.owner = owner.owner
        self.duration = 0
        self.volume = 0.0
        self.temp = menuOptions.val('P') if menuOptions else 0
        self.hold = menuOptions.val('M') if menuOptions else 0
        self.pauses = []
        self.startRegulating = 0
        self.regulations = []
        self.state = ''
        self.begin = 0

    def from_dict (self,reportDict: dict):
        self.batch = reportDict['batch']
        self.owner = owner.Owner(reportDict['owner'])
        self.duration = reportDict['duration']
        self.volume = reportDict['volume']
        self.temp = reportDict['temp']
        self.hold = reportDict['hold']
        self.pauses = reportDict['pauses']
        self.startRegulating = reportDict['startRegulating']
        self.regulations = reportDict['regulations']
        self.state = reportDict['state']
        self.begin = reportDict['begin']
        return self

    def to_dict(self):
        return {
            'batch': self.batch
            ,'owner': self.owner.to_dict()
            ,'duration': self.duration
            ,'volume' : self.volume
            ,'temp' : self.temp
            ,'hold' : self.hold
            ,'pauses' : self.pauses
            ,'startRegulating' : self.startRegulating
            ,'regulations' : self.regulations
            ,'state' : self.state
            ,'begin' : self.begin
        }

    # Fonction pour sauvegarder un objet de la classe courante en utilisant JSON
    def save(self):
        with open(datafiles.reportfile(self.batch), 'w') as f:
            json.dump(self.to_dict(),f)

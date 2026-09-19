#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import datetime
import traceback

import datafiles
import os
import json

import menus
import owner

# Fonction pour lister les fichiers d'un répertoire et retourner une liste de noms de fichiers
def list_reports(dummy = None):
    filenames = []
    for filename in os.listdir(datafiles.DIR_DATA_REPORT):
        if os.path.isfile(os.path.join(datafiles.DIR_DATA_REPORT, filename)) and filename.startswith("2") :
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

def delete(reportname):
    if reportname:
        try:
            os.remove(datafiles.reportfile(reportname))
            return True
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

        self.total_time_heating = 0
        self.total_temperature = 0.0
        self.count = 0
        self.first_performance = 0.0
        self.last_performance = 0.0

        self.input_source = ""
        self.customer = ""
        self.planned_volume = 0
        self.deviations = ''
        self.total_count = 0
        self.phosphatase_destroyed = 0 # 0: not tested, 1: destroyed (OK), 2: still there (NOK)...
        self.signature = ""

    def start(self, menuOptions:menus.Menus, state):
        self.state = state
        self.owner = owner.Owner.load()
        nowD = datetime.datetime.now()
        self.batch = nowD.strftime(datafiles.FILENAME_FORMAT)
        self.duration = 0
        self.volume = 0.0
        self.temp = menuOptions.val('P') if menuOptions else 0
        self.hold = menuOptions.val('M') if menuOptions else 0
        self.pauses = []
        self.startRegulating = 0
        self.regulations = []
        self.begin = time.perf_counter()
        print ('report start at %d' % self.begin)
        self.total_temperature = 0.0
        self.total_time_heating = 0
        self.count = 0
        self.first_performance = 0.0
        self.last_performance = 0.0

        self.input_source = ""
        self.customer = ""
        self.planned_volume = 0
        self.deviations = ''
        self.total_count = 0
        self.phosphatase_destroyed = 0
        self.signature = ""

    def from_form (self,reportDict: dict):
        if 'input_source' in reportDict:
            self.input_source = reportDict['input_source']
        if 'customer' in reportDict:
            self.customer = reportDict['customer']
        if 'planned_volume' in reportDict:
            self.planned_volume = reportDict['planned_volume']
        if 'total_count' in reportDict:
            self.total_count = reportDict['total_count']
        if 'deviations' in reportDict:
            self.deviations = reportDict['deviations']
        if 'phosphatase_destroyed' in reportDict:
            self.phosphatase_destroyed = reportDict['phosphatase_destroyed']
        if 'signature' in reportDict:
            self.signature = reportDict['signature']
        return self

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
        self.total_temperature = reportDict['total_temperature']
        if self.total_temperature is None:
            self.total_temperature = 0.0
        self.total_time_heating = reportDict['total_time_heating']
        if 'count' in reportDict:
            self.count = reportDict['count']
        else:
            self.count = 0
        if 'first_perf' in reportDict:
            self.first_performance = reportDict['first_perf']
        else:
            self.first_performance = 0.0
        if 'last_perf' in reportDict:
            self.last_performance = reportDict['last_perf']
        else:
            self.last_performance = 0.0

        self.from_form(reportDict)
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
            ,'total_temperature' : self.total_temperature
            ,'total_time_heating' : self.total_time_heating
            ,'count' : self.count
            ,'first_perf' : self.first_performance
            ,'last_perf' : self.last_performance
            ,'input_source' : self.input_source
            ,'customer' : self.customer
            ,'planned_volume' : self.planned_volume
            ,'deviations' : self.deviations
            ,'total_count' : self.total_count
            ,'phosphatase_destroyed' : self.phosphatase_destroyed
            ,'signature' : self.signature
        }

    # Fonction pour sauvegarder un rapport en utilisant JSON
    def save(self, flush = False):
        with open(datafiles.reportfile(self.batch), 'w') as f:
            json.dump(self.to_dict(),f)
            if flush:
                f.flush()
                os.fsync(f.fileno())
                # --- SYNCHRONISATION DU RÉPERTOIRE PARENT ---
                # Récupère le chemin absolu du dossier contenant le rapport
                report_dir = os.path.dirname(os.path.abspath(f.name))
                # Ouvre le répertoire en lecture seule (requis par l'OS pour faire un fsync sur un dossier)
                dir_fd = os.open(report_dir, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)

def record(self,data):
        self.from_form(data)
        self.save()

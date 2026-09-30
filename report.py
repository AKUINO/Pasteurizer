#!/usr/bin/python3
# -*- coding: utf-8 -*-
import copy
import time
import datetime
import traceback

import datafiles
import os
import json

import menus
import owner
import menus

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

    def __init__(self, menuOptions:menus.Menus.singleton = None):
        self.batch = None
        self.owner = owner.owner
        self.duration = 0
        self.volume = 0.0
        self.temp = menuOptions.val('P') if menuOptions else 0
        self.hold = menuOptions.val('M') if menuOptions else 0
        self.pauses = []
        self.startRegulating = 0
        self.regulations = []
        self.state = None
        self.begin = 0

        self.total_time_heating = 0
        self.total_temperature = 0.0
        self.count = 0
        self.first_performance = 0.0
        self.last_performance = 0.0
        self.speed_squared = 0.0

        self.input_source = ""
        self.customer = ""
        self.planned_volume = 0
        self.deviations = ''
        self.total_count = 0
        self.phosphatase_destroyed = 0 # 0: not tested, 1: destroyed (OK), 2: still there (NOK)...
        self.signature = ""

        self.cohorts = None # used only in reports re-creation (report_csv_line)
        self.prec_line_epoch = 0.0
        self.begin_volume = 0.0
        self.performance_vol_slice_0 = 0.0
        #self.performance_vol_slice_1 = 0.0
        #self.performance_vol_slice_2 = 0.0
        self.some_heating = False
        self.slice_volume = 0.0
        self.startPause = 0

    def start(self, menuOptions:menus.Menus, state, now=None):
        self.state = state
        self.owner = owner.Owner.load()
        if now is None:
            nowD = datetime.datetime.now()
        else:
            nowD = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
        self.batch = nowD.strftime(datafiles.FILENAME_FORMAT)
        print("Report start ",self.batch)
        self.duration = 0
        self.volume = 0.0
        self.temp = menuOptions.val('P') if menuOptions else 0
        self.hold = menuOptions.val('M') if menuOptions else 0
        self.pauses = []
        self.startRegulating = 0
        self.regulations = []
        self.begin = time.perf_counter()
        self.begin_volume = 0.0
        print ('report %s start at %d' % (self.batch, self.begin) )
        self.total_temperature = 0.0
        self.total_time_heating = 0
        self.count = 0
        self.first_performance = 0.0
        self.last_performance = 0.0
        self.speed_squared = 0.0

        self.input_source = ""
        self.customer = ""
        self.planned_volume = 0
        self.deviations = ''
        self.total_count = 0
        self.phosphatase_destroyed = 0
        self.signature = ""
        self.startPause = 0

        self.performance_vol_slice_0 = 0.0
        #self.performance_vol_slice_1 = 0.0
        #self.performance_vol_slice_2 = 0.0
        self.some_heating = False
        self.slice_volume = self.cohorts.total_volume

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

        if 'speed2' in reportDict:
            self.speed_squared = reportDict['speed2']
        else:
            self.speed_squared = 0.0

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
            ,'speed2' : self.speed_squared
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
        print(self.batch)
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

    def performance_heat_exchanger(self, cohorts):
        # ( Exchanger recuperation output temperature - Intake temperature ) / (Pasteurization temperature - Intake temperature)

        performance = 0.0
        last_period = cohorts.last_period()
        if last_period:
            Voutlet = cohorts.history[cohorts.VOLUME][last_period]
            if Voutlet:
                Vinlet = Voutlet - cohorts.up_to_mL('intake','input')
                Vreturn = Voutlet - cohorts.holding_volume
                Toutlet = cohorts.history['input'][last_period]
                Tinlet = None
                Treturn = None
                if Toutlet:
                    Dinlet = cohorts.find_period_by_volume(Vinlet)
                    if Dinlet:
                        Tinlet = cohorts.history['intake'][Dinlet]
                        if Toutlet > Tinlet:
                            Dreturn = cohorts.find_period_by_volume(Vreturn)
                            if Dreturn:
                                Treturn = cohorts.history['warranty'][Dreturn]
                                if Treturn > Tinlet:
                                    performance = 100.0*(Toutlet-Tinlet)/(Treturn-Tinlet)
        return performance

    def report_csv_line(self,
                        # 0: epoch_sec
                        log_epoch_sec,
                        # 1: state
                        # 2: action
                        log_action,
                        # 3: oper
                        log_oper,
                        # 4: still
                        # 5: qrem
                        # 6: watt
                        # 7: volume
                        log_vol,
                        # 8: pump
                        log_speed,
                        # 9: pause
                        log_pause,
                        # 10: input
                        log_input_temp,
                        # 11: warant
                        log_warant_temp,
                        # 12: intake
                        log_intake_temp,
                        # 13: heat
                        log_isheating,
                        # 14: heatbath
                        log_heat_temp,
                        # 15: press
                        # 16: linput
                        # 17: loutput
                        base_cohorts
                        ):

        if self.cohorts is None:
            self.cohorts = copy.deepcopy(base_cohorts)
            self.slice_volume = self.cohorts.total_volume
            print('Vol total:%.1f, holding=%.3f'% (self.cohorts.total_volume,self.cohorts.holding_volume))
        self.cohorts.setPeriod(log_epoch_sec,log_intake_temp,log_input_temp,log_warant_temp,log_heat_temp,log_vol)

        if log_action not in ['P','I']:
            if self.state is not None:
                self.save(True)
                self.state = None
        else:
            if log_oper in ['PasP']:
                if self.state is None:
                    self.start(menus.Menus.singleton,'p',log_epoch_sec)
                    self.begin = log_epoch_sec
                    self.begin_volume = log_vol
                    self.signature = '---'
                if log_pause == 1:
                    self.startPause = log_epoch_sec
                else:
                    if self.startPause > 0:
                        duration = log_epoch_sec-self.startPause
                        self.pauses.append((duration, self.cohorts.up_to_mL('warranty') / 1000.0))
                        self.startPause = 0
                    self.volume = log_vol - self.begin_volume
                    self.duration = log_epoch_sec - self.begin
                    if log_isheating > 0.0:
                        self.some_heating = True
                        if self.prec_line_epoch > 0:
                            self.total_time_heating = self.total_time_heating + (log_epoch_sec - self.prec_line_epoch)
                    self.total_temperature += log_warant_temp
                    self.count += 1
                    curr_performance = self.performance_heat_exchanger(self.cohorts)
                    #print('%.1f, %.1f' % (curr_performance,log_speed))
                    if curr_performance > 0.0 and log_speed > 0.0:
                        if self.volume > (self.cohorts.total_volume*2) and self.first_performance <= 0.0:
                            self.first_performance = curr_performance
                        if self.volume > self.slice_volume:
                            if self.some_heating:
                                self.last_performance = self.performance_vol_slice_0
                                self.performance_vol_slice_0 = curr_performance
                                self.some_heating = False
                            self.slice_volume = self.volume + self.cohorts.total_volume
                        self.speed_squared = self.speed_squared + ( (log_speed / 60.0) ** 2.0 )
        self.prec_line_epoch = log_epoch_sec

    def record(self,data):
            self.from_form(data)
            self.save(True)

#report = Report()
#print ('%.1f' % (((report.speed_squared/report.count)-(((report.volume*60.0)/report.duration)^2.0))^0.5))
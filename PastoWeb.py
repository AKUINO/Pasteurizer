#!/usr/bin/python3
# -*- coding: utf-8 -*-
import socket
import sys
import os
import signal
import subprocess
import argparse
import json
import time
import web
from datetime import datetime

global render,_lock_socket

import tty
import termios
import subprocess
import traceback
import math

import pyownet
import term
import threading

import hardConf
import ml
import sensor
#import pump
import pump_pwm
import cohort

from thermistor import Thermistor
from solenoid import Solenoid
from LED import LED
from button import button
from valve import Valve
from menus import Menus

DEBUG = True

DIR_BASE = os.path.dirname(os.path.abspath(__file__)) + '/'

DIR_STATIC = os.path.join(DIR_BASE, 'static/')
URL_STATIC = u'/static/'

DIR_DATA_CSV = os.path.join(DIR_BASE, 'csv/')

DIR_WEB_TEMP = os.path.join(DIR_STATIC, 'temp/')

TEMPLATES_DIR = os.path.join(DIR_BASE, 'templates/')

KEY_ADMIN = "user@pastonomic.solutions"  # Omnipotent user
PWD = "BE.past0"

HEAT_EXCHANGER = True

display_pause = False
lines = 25

WebExit = False

def isnull(v,n):
    if v is None:
        return n
    else:
        return v

def zeroIsNone(v):
    if not v:
        return None
    elif v == 0.0:
        return None
    else:
        return v

def getch():

    ch = None
    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)
    except: #ioctl
        old_settings = None
    try:
        ch = sys.stdin.read(1)
    finally:
        if old_settings:
            termios.tcsetattr(fd,termios.TCSADRAIN,old_settings)
    return ch

def termSize():
    if term and term.getSize():
        return term.getSize()
    else:
        return (25,80)

def tell_message(message):
    
        global display_pause

        prec_disp = display_pause
        display_pause = True
        time.sleep(0.01)
        (lines, columns) = termSize()
        term.pos(lines,1)
        term.writeLine("",term.bgwhite) # scroll the whole display by one line
        term.pos(lines-4,1)
        term.write(message,term.blue,term.bold,term.bgblack)
        term.clearLineFromPos()
        term.pos(lines-3,1)
        term.clearLineFromPos()
        display_pause = prec_disp
        
typeOneWire = 1
typeRMeter = 11

Buzzer = None
RedLED = None
YellowLED = None
GreenLED = None
RedButton = None
YellowButton = None
GreenButton = None
#configuration of output pins
if hardConf.Out_Buzzer:
    Buzzer = LED('buzzer',hardConf.Out_Buzzer)
if hardConf.Out_Red:
    RedLED = LED('red',hardConf.Out_Red) #BCM=24
if hardConf.Out_Yellow:
    YellowLED = LED('yellow',hardConf.Out_Yellow) #BCM=24
if hardConf.Out_Green:
    GreenLED = LED('green',hardConf.Out_Green) #BCM=23

#configuration of input pins
if hardConf.In_Red:
    RedButton = button('red',hardConf.In_Red)
if hardConf.In_Yellow:
    YellowButton = button('yellow',hardConf.In_Yellow)
if hardConf.In_Green:
    GreenButton = button('green',hardConf.In_Green)

##BATH_TUBE = 4.6 # degrees Celsius. Margin between temperature in bath and temperature wished in the tube
FLOOD_TIME = 60.0 # 90 econds of hot water tap flushing (when a pump is in the way. 60 if not)

#temperTank = 20.0 # litres dans le bassin de temperisation
#midTemperTank = 5.3 # litres jusqu'au sommet du serpentin inférieur

# To be parameterized?
CLEAN_TIME = 1800.0
DISINF_TIME = 300.0
RINSE_TIME = 300.0

menus = Menus();
menus.options =  {  'G':['G',ml.T("Gradient°","Gradient°","Gradient°") \
                            ,ml.T("Gradient de température","Temperature Gradient","Gradient van Temperatuur") \
                            ,3.0,3.0,"°C",False,7,0.1], # Gradient de Température
                    'P':['P',ml.T("Pasteurisation°","Pasteurization°","Pasteurisatie°") \
                            ,ml.T("Température de pasteurisation","Pasteurisation Temperature","Pasteurisatie Temperatuur") \
                            ,72.0,72.0,"°C",False,90,0.1], # Température normale de pasteurisation
                    'R':['R',ml.T("Rinçage°","Rinse°","Spoelen°") \
                            ,ml.T("Température de rinçage","Rinse Temperature","Spoelen Temperatuur") \
                            ,45.0,45.0,"°C",False,90,0.1], # Température du Bassin pour le prélavage
                    'r':['r',ml.T("Rinçage\"","Rinse\"","Spoelen\"") \
                            ,ml.T("Durée de rinçage","Rinse Duration","Spoelen Tijd") \
                            ,FLOOD_TIME,FLOOD_TIME,'"',False,9999,1], # Température du Bassin pour le prélavage
                    'N':['N',ml.T("Nettoyage°","Cleaning°","Schoonmaak°") \
                            ,ml.T("Température de nettoyage","Cleaning Temperature","Schoonmaak Temperatuur") \
                            ,70.0,70.0,"°C",False,90,0.1], # Température pour un passage au détergent
                    'n':['n',ml.T("Nettoyage\"","Cleaning\"","Schoonmaak\"") \
                            ,ml.T("Durée de nettoyage","Cleaning Duration","Schoonmaak Tijd") \
                            ,CLEAN_TIME,CLEAN_TIME,'"',False,9999,1], # Température pour un passage au détergent
                    'D':['D',ml.T("Désinfection°""Disinfection°","Desinfectie°") \
                            ,ml.T("Température de désinfection","Disinfection Temperature","Desinfectie Temperatuur") \
                            ,60.0,60.0,"°C",False,90,0.1], # Température pour un traitement à l'acide ou au percarbonate de soude
                    'd':['d',ml.T("Désinfection\"","Disinfection\"","Desinfectie\"") \
                            ,ml.T("Durée de désinfection","Disinfection Duration","Desinfectie Tijd") \
                            ,DISINF_TIME,DISINF_TIME,'"',False,9999,1], # Température pour un traitement à l'acide ou au percarbonate de soude
                    'M':['M',ml.T("Minimum","Minimum","Minimum") \
                            ,ml.T("Durée minimale de pasteurisation","Minimum pasteurization time","Minimale pasteurisatietijd") \
                            ,15.0,15.0,'"',False,199,1], # Durée minimale de pasteurisation
                    # 'T':['T',ml.T("Tempérisation Max°","Tempering Max°","Temperen Max°") \
                            # ,ml.T("Température d'ajout d'eau de refroidissement","Cooling water addition temperature","Koelwatertoevoegings Temperatuur") \
                            # ,0.0,0.0,"°C",True,90.0,0.1], # Température à laquelle on ajoute de l'eau de refroidissement,ZeroIsNone=True
                    # 't':['t',ml.T("Tempérisation Min°","Tempering Min°","Temperen Min°") \
                            # ,ml.T("Réchauffement à la sortie","Output Heating","Opwarmen") \
                            # ,18.0,18.0,"°C",True,90.0,0.1], # Température à laquelle on chauffe la cuve de sortie,ZeroIsNone=True
                    # 'K':['K',ml.T("Quantité Froid","Quantity Cold","Koel Aantal") \
                            # ,ml.T("Quantité d'eau de refroidissement","Cooling Water Quantity","Koelwater Aantal") \
                            # ,midTemperTank,midTemperTank,"L",False,19.9,0.1], # Quantité d'eau froide à mettre dans le bassin de refroidissement
                    'Q':['Q',ml.T("Quantité","Quantity","Aantal") \
                            ,ml.T("Quantité de lait à entrer","Amount of milk to input","Aantal melk voor invoor") \
                            ,0.0,0.0,"L",True,9999.9,0.1], # Quantité de lait à traiter,ZeroIsNone=True
                    'H':['H',ml.T("Démarrage","Start","Start") \
                            ,ml.T("Heure de démarrage","Start Time","Starttijd") \
                            ,0.0,0.0,"hh.m0",True,23.5,0.1], # Hour.minutes (as a floating number, by 10 minutes),ZeroIsNone=True
                    'Z':['Z',ml.T("Défaut","Default","Standaardwaarden") \
                            ,ml.T("Retour aux valeurs par défaut","Back to default values","Terug naar standaardwaarden")] }
menus.sortedOptions = "PMGKQRrNnDdZ" #T
menus.cleanOptions = "PMGQH" #TtK
menus.dirtyOptions = "RGrNnDdH"
#(options['P'][3] + BATH_TUBE) = 75.0  # Température du Bassin de chauffe
##reject = 71.7 # Température minimum de pasteurisation

floodLitersMinute = 3.5 # 4.0 si pas de pompe dans le chemin; 3 sinon
tank = 20.6 # litres dans le bassin de chauffe

kCalWatt = 1.16 # watts per kilo calories
HEAT_POWER = 3000.0 # watts per hour (puissance de la chauffe)
#MITIG_POWER = 1500.0 # watts per hour (puissance du bac de mitigation)
ROOM_TEMP = 21.0 # degrees: should be measured...

PUMP_SLOWDOWN = 1.0 # Slowing factor from speed calculated by temperature difference

# durationDump = Time to open or close the dump valve: look at Valve module...

periodicity = 3 # 3 seconds intervall between cohort data
depth = 100 # 100 x 3 seconds of data kept
cohorts = cohort.Cohort(periodicity,depth)

calibrating = False
temp_ref_calib = []

def manage_cmdline_arguments():
    parser = argparse.ArgumentParser(description='pastOnomic: Pasteurisateur accessible')
    # Est interprété directement par WebPY
    parser.add_argument('port', type=int, help='Port number of the internal \
                                                web server')
    return parser.parse_args()

# restart_program()
args = manage_cmdline_arguments()
_lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

try:
    _lock_socket.bind('\0pastOnomic')
    print('Socket pastOnomic now locked')
except socket.error:
    print('pastOnomic lock exists')
    sys.exit()

if not os.path.samefile(os.getcwd(), DIR_BASE):
    os.chdir(DIR_BASE)

PI = 3.141592 # Yes, we run on a Raspberry !

# mL Volume of a tube based on ID(mm) and length(mm)
def vol_tube(ID,long):
    rad = ID/2.0
    return PI*rad*rad*long/1000.0 # cubic mm to cubic cm (mL)

# mL Volume of a tube based on ID(mm) of outer tube, OD of inner tube and length(mm)
def vol_outer_tube(OD_inner,ID_outer,long):
    return vol_tube(ID_outer,long) - vol_tube(OD_inner,long)

# mL Volume of a coil based on ID(mm) and coil middle diam(mm) and number of spires
def vol_coil(diamT,diamS,nbS):
    long = diamS*PI*nbS
    return vol_tube(diamT,long)

if hardConf.tubing == "horizontal":
    pasteurization_tube = 625 #vol_tube(8,15000) # 15m of expensive pump tube
    up_to_thermistor = 2330.0
    heating_tube = vol_tube(10.5,500)+vol_coil(10.5,220,18)+vol_tube(8,200)+vol_coil(7,250,20)
    initial_tubing = up_to_thermistor-heating_tube
    final_tubing = 3587.0-up_to_thermistor-pasteurization_tube-vol_tube(8,1800)
else:
    exchanger_tube = 2.0*712.6 #mL
    old_exchanger = vol_tube(8,8*1800)
    pasteurization_tube = vol_tube(9.5,8820) # = 625mL aussi
    up_to_thermistor = 2330.0
    heating_tube = vol_tube(10.5,500)+vol_coil(10.5,220,18)+vol_tube(8,200)+vol_coil(7,250,20)
    initial_tubing = up_to_thermistor-heating_tube+exchanger_tube-old_exchanger
    final_tubing = 3587.0-up_to_thermistor-pasteurization_tube-vol_tube(8,1800)+exchanger_tube-old_exchanger

cohorts.sequence = [ # Tubing and Sensor Sequence of the Pasteurizer
                    [initial_tubing,'input'], #input de la chauffe
                    [heating_tube,'warranty'], # Garantie
                    [pasteurization_tube,'output'], # Bassin
                    [final_tubing+vol_tube(8,1800),'extra'] ] # Sortie
START_VOL = 0.0
for curr_cohort in cohorts.sequence:
    START_VOL += curr_cohort[0]
    if curr_cohort[1] == 'warranty':
        break

TOTAL_VOL = 0.0
for curr_cohort in cohorts.sequence:
    TOTAL_VOL += curr_cohort[0]
tell_message("Amorçage=%dmL, Pasteurisation=%dmL : %.1fL/h, Total=%dmL" % (int(START_VOL),int(pasteurization_tube),(pasteurization_tube / 15.0) * 3600.0 / 1000.0,int(TOTAL_VOL)))
#Amorçage=1941mL, Pasteurisation=538mL, Total=3477mL
#Amorçage=2031mL, Pasteurisation=538mL, Total=3676mL
#Amorçage=2034mL, Pasteurisation=325mL, Total=3346mL
#Amorçage=2300mL, Pasteurisation=400mL, Total=3840mL MESURE
#Amorçage=2330mL, Pasteurisation=625mL, Total=3587mL (new config system)
#New exchanger:
#Amorçage=3031mL, Pasteurisation=625mL, Total=4989mL



START_VOL = START_VOL / 1000.0 # 1.9L
TOTAL_VOL = TOTAL_VOL / 1000.0 # 3.5L

DRY_VOLUME = TOTAL_VOL*2.0 # (air) liters to pump to empty the tubes...

#i=input(str(START_VOL*1000.0)+"/"+str(pasteurization_tube)+"/"+str(vol_tube(8,400)+vol_coil(8,250,10)+vol_tube(8,2000)))
SHAKE_QTY = pasteurization_tube / 1000.0 / 4 # liters
SHAKE_TIME = 10.0 # seconds shaking while cleaning, rincing or disinfecting

class ThreadOneWire(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        try:
            self.owproxy = pyownet.protocol.proxy(host="localhost", port=4304)
        except:
            pass

    def sensorParam(self,address,param):
        global cohorts
        if not address in cohorts.catalog:
            cohorts.addSensor(address,sensor.Sensor(typeOneWire,address,param))
            cohorts.readCalibration(DIR_DATA_CSV,address)
        return cohorts.catalog[address]

    def run(self):
        global cohorts
        last = 0
        loop = True
        while loop:
            try:
                time.sleep(0.2)
                now = time.perf_counter()
                if now > (last+2.5):
                    last = now
                    if self.owproxy:
                        try:
                            status = self.owproxy.write("/simultaneous/temperature", b'1')
                        except:
                            traceback.print_exc()
                    if self.owproxy or hardConf.Rmeter:
                        for (address,aSensor) in cohorts.catalog.items():
                            #print (address)
                            if self.owproxy and aSensor.sensorType == typeOneWire and aSensor.param:
                                time.sleep(0.02)
                                try:
                                    value = float(self.owproxy.read("/"+aSensor.param+"/temperature"))
                                    if value != 85.0: # Can be invalid value...
                                        aSensor.set(value)
                                except KeyboardInterrupt:
                                    loop = False
                                    break
                                except:
                                    traceback.print_exc()
                            if hardConf.Rmeter and aSensor.sensorType == typeRMeter:
                                try:
                                    r,v = hardConf.Rmeter.r_meter_get_ohms(0)
                                    if r > 0:
                                        aSensor.set(r)
                                except:
                                    traceback.print_exc()
                                #print(r)
            except KeyboardInterrupt:
                loop = False
                break
            except:
                traceback.print_exc()

# #####################################################################################
# BATT_ADC = 8 # ADC port for battery
# BATT_R1 = 46600.0 # Divider bridge to measure battery (top resistor)
# BATT_R2 =  5510.0 # bottom resistor

##def vari(adc_channel):
##    moy = t[adc_channel] / n[adc_channel]
##    s = (t2[adc_channel] / n[adc_channel]) - (moy * moy)
##    if s < 0.0:
##        s = - s
##    s = s ** 0.5
##    return ", M=%6.0f, s=%6.1f" % (moy,s)

class ThreadThermistor(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def sensorParam(self,address,param):
        global cohorts
        if not address in cohorts.catalog:
            cohorts.addSensor(address,Thermistor(address,param))
            cohorts.readCalibration(DIR_DATA_CSV,address)
        return cohorts.catalog[address]

    def run(self):
        global cohorts
        while True:
            try: 
                time.sleep(1.0)
                for (address, aSensor) in cohorts.catalog.items():
                    if aSensor.sensorType == Thermistor.typeNum:
                        aSensor.get()
                if not hardConf.MICHA_device: # Average of 3 measures needed
                    time.sleep(0.01)
                    for (address, aSensor) in cohorts.catalog.items():
                        if aSensor.sensorType == Thermistor.typeNum:
                            aSensor.get()
                    time.sleep(0.01)
                    for (address, aSensor) in cohorts.catalog.items():
                        if aSensor.sensorType == Thermistor.typeNum:
                            aSensor.get()
                            value = aSensor.avg3()
                            if value is not None:
                                aSensor.set(value)
            except KeyboardInterrupt:
                break
            except:
                traceback.print_exc()

menus.actionName = { 'X':['X',ml.T("eXit","eXit","eXit") \
                       ,ml.T("Ranger le matériel...","Put equipment back in place...","Berg de apparatuur op ..") \
                       ,ml.T("Quitter l'application","Exit the application","Verlaat de applicatie")],
               # 'U':['U',ml.T("pUrge","pUrge","zUiver") \
                       # ,ml.T("","Purge Output Tank...","Ontlucht de uitvoertank...") \
                       # ,ml.T("Purger le tampon de sortie...","Purge Output Tank...","Ontlucht de uitvoertank...")],
               # 'C':['C',ml.T("Complet","full","vol") \
                       # ,ml.T("Entrée à la soupape, Sortie à la vanne bleue.","Inlet at the valve, Outlet at the blue valve.","Inlaat bij de klep, uitlaat bij de blauwe klep.") \
                       # ,ml.T("Cycle complet de nettoyage","Complete cleaning cycle","Volledige reinigingscyclus")],
               'F':['F',ml.T("Flush","Flush","Flush") \
                       ,ml.T("Entrée et Sortie connectés, Vidange...","Inlet and Outlet connected, Drain ...","Inlaat bij de klep, Uitlaat bij de blauwe klep, Afvoer ...") \
                       ,ml.T("Rinçage à l'eau de ville","Rinse with city water","Spoelen met stadswater")],
               # 'K':['K',ml.T("eau froide","Kooling","Kool") \
                       # ,ml.T("Spécifier AVANT la Quantité et la Température dans Options","Specify BEFORE Quantity and Temperature in Options","Specificeer VOOR hoeveelheid en temperatuur in Opties") \
                       # ,ml.T("Ajouter de l'eau froide dans la Tempérisation","Add cold water to Mitigation","Voeg koud water toe aan Mitigation")],
               'V':['V',ml.T("Vider","Purge","Purge") \
                       ,ml.T("Entrée hors de l'eau, Vidange...","Inlet out of water, Drain ...","Inlaat uit het water, Afvoer ...") \
                       ,ml.T("Vidange maximale des tuyaux","Maximum emptying of pipes","Maximale lediging van leidingen")],
               'A':['A',ml.T("Amorc.","initiAte","Aanzet.") \
                       ,ml.T("Entrée et Sortie connectés et dans un seau, Pré-chauffage...","Inlet and Outlet connected and in a bucket, Pre-heating ...","Input en output aangesloten en in een emmer, Voorverwarmen ...") \
                       ,ml.T("Amorçage de la Pasteurisation","Initiating Pasteurization","Pasteurisatie initiëren")],
               'P':['P',ml.T("Pasteur.","Pasteur.","Pasteur.") \
                       ,ml.T("Lait de la traite en entrée; Récipient pasteurisé en sortie. Jeter l'eau","Milking milk at inlet; Pasteurized container at the outlet. Discard water","Melk melken als voorgerecht; Gepasteuriseerde container bij de uitlaat. Gooi water") \
                       ,ml.T("Pasteurisation","Pasteurization","Pasteurisatie")],
               'I':['I',ml.T("reprIse","resume","resume") \
                       ,ml.T("Lait de la traite en entrée et un récipient pasteurisé en sortie","Milking milk at inlet and pasteurized container at outlet","Melk bij binnenkomst en gepasteuriseerde container bij vertrek") \
                       ,ml.T("Reprise d'une pasteurisation interrompue","Resume an interrupted pasteurization","Hervatting van onderbroken pasteurisatie")],
               'E':['E',ml.T("Eau","watEr","watEr") \
                       ,ml.T("Eau en entrée et un récipient pasteurisé en sortie","Water inlet and a pasteurized container outlet","Waterinlaat en een gepasteuriseerde containeruitlaat") \
                       ,ml.T("Pousser le lait qui reste d'une pasteurisation","Push the milk left over from pasteurization","Schuif de melk die overblijft na pasteurisatie")],
               'M':['M',ml.T("Multi","Multi","Multi") \
                       ,ml.T("Nouveau lait entrée et un récipient pasteurisé en sortie","New milk inlet and a pasteurized container outlet","Nieuwe melk bij de inlaat en een gepasteuriseerde container bij de uitlaat") \
                       ,ml.T("Passer à un autre lait","Switch to another milk","Overschakelen naar een andere melk")],
               'R':['R',ml.T("Rinçage (4 Flush)","Rinse (4 Flush)","Spoelen (4 Flush)") \
                       ,ml.T("Entrée et Sortie connectés, Vidange...","Inlet and Outlet connected, Drain ...","Inlaat bij de klep, Uitlaat bij de blauwe klep, Afvoer ...") \
                       ,ml.T("Rincer à fond les tuyaux","Rinse the pipes thoroughly","Spoel de leidingen grondig af")],
               'N':['N',ml.T("Nettoy.","Clean","Schoon") \
                       ,ml.T("Entrée et Sortie connectés et dans un seau, Ajouter le Détergent...","Inlet and Outlet connected and in a bucket, Add Detergent ...","Input en output aangesloten en in een emmer, Wasmiddel toevoegen ...") \
                       ,ml.T("Nettoyer avec un détergent (caustique)","Clean with detergent (caustic)","Reinig met afwasmiddel (bijtend)")],
               'D':['D',ml.T("Désinfct.","Disinfct","Desinfect.") \
                       ,ml.T("Entrée et Sortie connectés et dans un seau, Ajouter le Désinfectant...","Inlet and Outlet connected and in a bucket, Add Disinfectant ...","Input en output aangesloten en in een emmer, Desinfectiemiddel toevoegen ...") \
                       ,ml.T("Désinfecter les tuyaux (acide)","Disinfect pipes (acid)","Desinfecteer leidingen (zuur)")],
               'S':['S',ml.T("pauSe","pauSe","pause") \
                       ,ml.T("s=arrêter / S=redémarrer / V=vidanger / Z=arrêter l'opération en cours","s = stop / S = restart / V = ​​drain / Z = stop the operation in progress","s = stop / S = herstart / V = ​​afvoer / Z = stop de lopende operatie") \
                       ,ml.T("Suspendre ou arrêter l'opération en cours","Suspend or stop the current operation","Onderbreek of stop de huidige bewerking")],
               'O':['O',ml.T("Option","Option","Opties") \
                       ,ml.T("Paramètres TEMPORAIRES de fonctionnement","TEMPORARY operating parameters","TIJDELIJKE bedrijfsparameters") \
                       ,ml.T("Changement temporaire de paramètres","Temporary change of parameters","Tijdelijke wijziging van parameters")],
               'Y':['Y',ml.T("Yaourt","Yogurt","Yoghurt") \
                       ,ml.T("Pasteuriser pour Yaourt","Pasteurize for Yogurt","Pasteuriseren voor yoghurt") \
                       ,ml.T("Température pour Yaourt","Temperature for Yogurt","Temperatuur voor yoghurt")],
               'L':['L',ml.T("Lait","miLk","meLk") \
                       ,ml.T("Pasteuriser du Lait","Pasteurize for Milk","Pasteuriseren voor melk") \
                       ,ml.T("Température pour Lait","Temperature for Milk","Temperatuur voor melk")],
               'T':['T',ml.T("Therm","Therm","Therm") \
                       ,ml.T("Thermiser","Thermize","Thermis.") \
                       ,ml.T("Température pour Thermiser","Temperature for Thermizing","Temperatuur voor thermisering")],
               'Z':['Z',ml.T("STOP","STOP","STOP") \
                       ,ml.T("Pas d'opération en cours.","No operation in progress.","Er wordt geen bewerking uitgevoerd.") \
                       ,ml.T("Arrêt complet de l'opération en cours","Complete stop of the current operation","Volledige stopzetting van de huidige bewerking")],
               '_':['_',ml.T("Redémar.","Restart","Herstart") \
                       ,ml.T("Redémarrage de l'opération en cours.","Restart of the current operation.","Herstart van de huidige bewerking.") \
                       ,ml.T("Redémarrer l'opération en cours","Restart the current operation","Herstart de huidige bewerking")]}
menus.sortedActions1 = "APIMERND" #C
menus.sortedActions2 = "FVOYLTZSX" #K

menus.cleanActions = "LYTAPIMEV" #K
menus.dirtyActions = "RFNDV" #C
menus.sysActions = "ZX"

menus.operName = { 'HEAT':ml.T('chauffer','heating','verwarm') \
                  ,'PUMP':ml.T('pomper','pump','pomp') \
                  ,'EMPT':ml.T('vider','purge','purge') \
                  ,'TRAK':ml.T('débiter','trace','trace') \
                  ,'SHAK':ml.T('brasser','shake','schud') \
                  ,'REVR':ml.T('reculer','pump back','pomp terug') \
                  ,'FLOO':ml.T('eau courante','running water','lopend water') \
                  ,'PAUS':ml.T('attendre','wait','wacht') \
                  ,'MESS':ml.T('signaler','message','bericht') \
                  ,'SUBR':ml.T('processer','process','werkwijze') \
                  ,'SUBS':ml.T('procéder','proceed','doorgan') }

menus.pipeState = { 'R':ml.T('Propre','Clean','Schoon'), \
                    'O':ml.T('Vieux','Old','Oud'), \
                    'A':ml.T('Vidé','Purged','Leeg'), \
                    'B':ml.T('Vidé+Sale','Purged+Dirty','Leeg+Vies'), \
                    'T':ml.T('Sale+Gras','Dirty+Greasy','Vies+Vet'), \
                    'S':ml.T('Sale','Dirty','Vies'), \
                    'N':ml.T('Soude','Soda','Natrium'), \
                    'D':ml.T('Acide','Acid','Zuur'), \
                    'G':ml.T('Produit Gras','Greasy Product','Vet Product'), \
                    'P':ml.T('Produit','Product','Product') }


menus.stateTransitions = { 'R-P' : ['P','G'], 'R-V' : ['A'], \
                           'R-t' : ['O'], 'R-t.2' : ['S'], \
                           'A-t' : ['B'], \
                           'O-F*2' : ['R'], 'O-V' : ['B'], \
                           'B-F*1' : ['S'], \
                           'P-F' : ['E'], 'G-F' : ['H'], \
                           'P-F*2' : ['E'], 'G-F*2' : ['H'], \
                           'H-N' : ['N','N0'], 'T-N' : ['N','N0'], 'S-N' : ['N','N0'], \
                           'E-D' : ['D','D0'], 'S-D' : ['D','D0'], \
                           'N-F*4' : ['R'],  'D-F*4' : ['R'] }
# R + Pasteuriser Gras = G
# R + Pasteuriser Maigre = P
# R + Vider = A
# R + delay = O
# A + delay = B
# O + Flush x 2 = R
# O + Vider = B
# B + Flush = S
# R + longer delay = S
# P + Flush x 2 (P1,P2) = S
# G + Flush x 2 (G1,G2) = T
# T + Nettoyer = N au début, N0 quand complet
# S + Nettoyer = N au début, N0 quand complet
# Nx + Flush x 4 (N1,N2,N3,N4) = R
# S + Acide = D au début, D0 quand complet
# T + Acide INTERDIT
# Dx + Flush x 4 (D1,D2,D3,D4) = R

def menu_confirm(choice,delay=None):
    global display_pause, lines
    prec_disp = display_pause
    display_pause = True
    time.sleep(0.05)
    term.pos(lines-2,1)
    choice = choice.upper()
    term.write(str(menus.actionName[choice][1]), term.bgwhite, term.white, term.bold)
    term.write(": "+str(menus.actionName[choice][3]), term.bgwhite, term.yellow, term.bold)
    term.clearLineFromPos()
    term.writeLine("", term.bgwhite, term.blue)
    term.write(str(menus.actionName[choice][2])+": ", term.bgwhite, term.blue)
    term.write(choice, term.bgwhite, term.red)
    term.write("?", term.bgwhite, term.blue)
    term.clearLineFromPos()
    term.writeLine("", term.bgwhite, term.blue)
    if not delay:
        stopWait = time.time()*2 # a.k.very far in the future!
    else:
        stopWait = time.time() + delay
    while time.time() < stopWait :
        time.sleep(0.05)
        conf = str(getch())
        if conf:
            conf = conf.upper()
            term.pos(lines-1,1)
            term.clearLineFromPos()
            display_pause = prec_disp
            if (conf == choice) or (conf == 'Z') or (conf == 'V'):
                term.write(menus.actionName[choice][1], term.bgwhite, term.green,term.bold)
                term.clearLineFromPos()
                term.writeLine("", term.bgwhite, term.blue)
                return conf
            elif delay:
                return ' '
    term.pos(lines-1,1)
    term.clearLineFromPos()
    display_pause = prec_disp
    return ' '

menu_choice = "?"

def option_confirm(delay=8.0):
    global display_pause,lines
    prec_disp = display_pause
    display_pause = True
    time.sleep(0.05)
    term.pos(lines,1)
    for choice in menus.sortedOptions:
        term.write(choice, term.bgwhite, term.red)
        term.write(": "+str(menus.options[choice][1]), term.bgwhite, term.blue)
        if len(menus.options[choice]) > 3:
            term.write("=", term.bgwhite, term.blue)
            term.write(str(menus.options[choice][3])+(" L" if choice in ['K','Q'] else (" sec." if choice == 'M' else "°C")), term.bgwhite, term.yellow)
        term.write(" "+str(menus.options[choice][2]), term.bgwhite, term.blue)
        if len(menus.options[choice]) > 3:
            term.write(" ("+str(menus.options[choice][4])+")", term.bgwhite, term.blue)
        term.clearLineFromPos()
        term.writeLine("", term.bgwhite, term.blue)
    term.clearLineFromPos()
    term.writeLine("", term.bgwhite, term.blue)
    term.clearLineFromPos()
    term.writeLine("", term.bgwhite, term.blue)
        
    stopWait = time.time() + delay
    while time.time() < stopWait :
        time.sleep(0.05)
        conf = str(getch())
        if conf:
            conf = conf.upper()
            term.pos(lines-1,1)
            term.clearLineFromPos()
            if (conf == 'Z'):
                for choice in menus.options:
                    if len(menus.options[choice]) > 3:
                        menus.options[choice][3] = menus.options[choice][4]
                term.write(menus.options[conf][2], term.bgwhite, term.green,term.bold)
                term.clearLineFromPos()
                term.writeLine("", term.bgwhite, term.blue)
            elif conf in menus.options.keys():
                val = input(term.format(str(menus.options[conf][2])+"? ", term.bgwhite, term.white, term.bold))
                try:
                    val = float(val)
                    menus.options[conf][3] = val
                except:
                    pass
            break
    reloadPasteurizationSpeed()
    display_pause = prec_disp

hotTapSolenoid = None # initialized further below
#coldTapSolenoid = None # initialized further below
taps = {}

# returns clock time formatted as a floating number h.m
def floating_time(some_time):
    return float (some_time.strftime("%H.%M"))

class ThreadDAC(threading.Thread):

    #global coldTapSolenoid

    def __init__(self):
        global cohorts
        threading.Thread.__init__(self)
        self.dacSetting = Solenoid('DAC1',hardConf.DAC1)
        #self.dacSetting = ssr.ssr('DAC1',0)
        cohorts.addSensor(self.dacSetting.address,self.dacSetting)
        #self.dacSetting2 = Solenoid('DAC2',hardConf.DAC2)
        #cohorts.addSensor(self.dacSetting2.address,self.dacSetting2)
        self.running = False
        self.setpoint = None
        #self.setpoint2 = None
        #self.coldpoint = None
        self.T_Pump = None
        self.totalWatts = 0.0
        self.totalWatts2 = 0.0
        self.currLog = None

    def set_temp(self,setpoint=None, setpoint2=None):
        if setpoint:
            self.setpoint = float(setpoint)
        else:
            self.setpoint = None
            self.dacSetting.set(0) # Arrêter net
            
        # if setpoint2:
            # self.setpoint2 = float(setpoint2)
        # else:
            # self.setpoint2 = None
            # self.dacSetting2.set(0) # Arrêter net

    # def set_cold(self,setpoint):
        # if setpoint:
            # self.coldpoint = float(setpoint)
        # else:
            # self.coldpoint = None
            # coldTapSolenoid.set(0) # Arrêter net

    def run(self):
        
        global cohorts, fileName, DIR_DATA_CSV, display_pause,tank,HEAT_POWER,ROOM_TEMP, lines, columns
        
        self.running = True
        lastLoop = time.perf_counter()
        prec_relay = -1
        lastWatt = 0
        # TODO: allow to balance both heating tanks to reduce power demand
        while self.running:
            time.sleep(0.01)
            now = time.perf_counter()
            if now > (lastLoop+cohorts.periodicity):
              delay = now - lastLoop
              lastLoop = now
              cohorts.nextPeriod()
              try:
                wattHour = False
                flooding = False

                # if self.setpoint is not None and (cohorts.catalog['heating'].value <= self.setpoint):
                    # kCal = (self.setpoint-cohorts.catalog['heating'].value)*tank
                    # wattHour = (kCal * kCalWatt) * 60.0
                    # # refroidissement prévu (perte générale par les parois)
                    # wattHour += (self.setpoint-ROOM_TEMP)*240.0/37.0
                    # # injection de lait prévue
                    # if self.T_Pump.pump.speed > 0.0:
                        # wattHour += (self.setpoint-cohorts.catalog['input'].value)*self.T_Pump.pump.liters()*kCalWatt
                    # if wattHour <= 1.0:
                        # wattHour = 0.0
                    # elif wattHour >= HEAT_POWER:
                        # wattHour = HEAT_POWER

                if self.setpoint and cohorts.catalog['heating'].value:
                    currHeat = int(self.dacSetting.value)
                    #print("%d %f / %f" % (currHeat, cohorts.catalog['heating'].value , self.setpoint) )
                    if currHeat > 0: # ON
                        if cohorts.getCalibratedValue('heating') < (self.setpoint+0.2):
                            wattHour = True
                    else: # Off
                        if cohorts.getCalibratedValue('heating') < (self.setpoint-0.2):
                            wattHour = True

                    if wattHour:
                        self.dacSetting.set(1)
                        self.totalWatts += (HEAT_POWER/3600.0 * delay)
                        if not lastWatt:
                            lastWatt = now
                    else:
                        self.dacSetting.set(0)
                        lastWatt = 0
                else:
                    self.dacSetting.set(0)
                    lastWatt = 0
                #self.dacSetting.set(wattHour)
                #self.totalWatts += (wattHour/3600.0 * delay)
                    
                # batt = adc.read_adc_voltage(BATT_ADC,0)
                # time.sleep(0.05)
                # batt += adc.read_adc_voltage(BATT_ADC,0)
                # batt = batt/2.0
                # batt = batt *(BATT_R1+BATT_R2) / BATT_R2
                # - - - - - - - - - - 
                # temperValue = cohorts.getCalibratedValue('temper')
                # wattHour2 = False
                # if self.setpoint2 and temperValue and temperValue > 0.0:
                    # currHeat = int(self.dacSetting2.value)
                    # #print("%d %f / %f" % (currHeat, cohorts.catalog['heating'].value , self.setpoint) )
                    # if currHeat > 0: # ON
                        # if temperValue < (self.setpoint2+0.2):
                            # wattHour2 = True
                    # else: # Off
                        # if temperValue < (self.setpoint2-0.2):
                            # wattHour2 = True

                    # if wattHour2:
                        # self.dacSetting2.set(1)
                        # self.totalWatts2 += (MITIG_POWER/3600.0 * delay)
                    # else:
                        # self.dacSetting2.set(0)
                # else:
                    # self.dacSetting2.set(0)
                # if self.coldpoint and temperValue and (temperValue < 65.0):
                    # currCold = int(coldTapSolenoid.value)
                    # #print("%d %f / %f" % (currHeat, cohorts.catalog['heating'].value , self.setpoint) )
                    # if currCold > 0: # ON
                        # if temperValue > (self.coldpoint-0.2):
                            # flooding = True
                    # else: # Off
                        # if temperValue > (self.coldpoint+0.2):
                            # flooding = True

                    # if flooding:
                        # coldTapSolenoid.set(1 if (now % 60.0) <= 12 else 0) # Flooding no more than 1/6 of the time to not overfill the mitigation tank
                    # else:
                        # coldTapSolenoid.set(0)
                # else:
                    # if self.T_Pump.currOperation and self.T_Pump.currOperation.tap == coldTapSolenoid:
                        # pass # Tap already controlled elsewhere to fill the tank...
                    # else:
                        # coldTapSolenoid.set(0)

                nowT = time.time()
                durationRemaining = self.T_Pump.durationRemaining()
                quantityRemaining = self.T_Pump.quantityRemaining()
                try:
                    data_file = open(DIR_DATA_CSV + fileName+".csv", "a")
                    data_file.write("%d\t%s\t%s\t%d\t%.3f\t%.2f\t%.2f\t%.2f\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"
                                    % (int(nowT), \
                                       self.T_Pump.currAction, \
                                       self.T_Pump.currOperation.acronym if self.T_Pump.currOperation else "", \
                                       durationRemaining, \
                                       quantityRemaining, \
                                       self.totalWatts, \
                                       self.T_Pump.pump.volume(), \
                                       self.T_Pump.pump.liters(), \
                                       1 if self.T_Pump.paused else 0, \
                                       cohorts.val('extra'), \
                                       cohorts.val('input'), \
                                       cohorts.val('warranty'), \
                                       cohorts.val('output'), \
                                       cohorts.catalog['DAC1'].val(), \
                                       cohorts.val('heating'), \
                                       cohorts.val('rmeter') ) )
                                       #self.totalWatts2, \
                                       #cohorts.val('temper'),
                                       #cohorts.catalog['DAC2'].val(), \
                                       #cohorts.catalog['sp9b'].value
                                       #cohorts.catalog['output'].value, batt
                    data_file.close()
                except:
                    traceback.print_exc()
                    pass

                if not display_pause:
                    time.sleep(0.01)
                    (lines, columns) = termSize()
                    term.pos(lines,1)
                    term.writeLine("",term.bgwhite) # scroll the whole display by one line
                    term.pos(lines-4,1)
                    term.write("%2d" % (int(nowT)%60), term.white, term.bold, term.bgwhite)
                    term.write(self.T_Pump.currOperation.acronym[3:4] if self.T_Pump.currOperation else " ",term.blue,term.bgwhite)
                    cohorts.catalog[self.T_Pump.pump.address].display() # Pompe
                    cohorts.display(term,'extra',format=" %5.1f° ") #Echgeur
                    cohorts.display(term,'input',format=" %5.1f° ") # Entrée de la Chauffe
                    cohorts.display(term,'warranty',format=" %5.1f° ") # Garant
                    cohorts.display(term,'output',format=" %5.1f° ") # Garant
                    term.write(' %1d ' % int(isnull(cohorts.catalog['DAC1'].value,0)),term.black,term.bgwhite) # Watts #+isnull(cohorts.catalog['DAC2'].value,0)
                    cohorts.display(term,'heating',format=" %5.1f° ") # Bassin
                    #cohorts.display(term,'temper',format=" %5.1f° ") # Bassin de tempérisation
                    #cohorts.catalog['sp9b'].display() # Garant
                    #cohorts.catalog['output'].display() # Sortie
                    term.write(' %4d"  ' % durationRemaining if durationRemaining > 0 else \
                                '%5dmL ' % int(quantityRemaining*1000) if quantityRemaining != 0.0 else "      ", \
                               term.white, term.bold, term.bgwhite)
                    term.writeLine("",term.bgwhite)

                    term.pos(lines-3,1)
                    term.clearLineFromPos()
                    term.writeLine("     Pompe   Extra   Entrée  Garant. FinCh. Chau Bassin  Encore ",term.blue,term.bgwhite) # scroll the whole display by one line

                    term.pos(1,1) # rewrite the top line (which changes all the time anyway)
                    term.write(menus.actionName[self.T_Pump.currAction][1],term.blue,term.bgwhite)
                    if self.T_Pump.currOperation:
                        term.write(" "+self.T_Pump.currOperation.acronym,term.blue,term.bgwhite)
                    term.write(" %dmL " % (self.T_Pump.pump.volume()*1000.0),term.bold,term.bgwhite, term.red if self.T_Pump.paused else term.yellow)
                    term.write(datetime.fromtimestamp(nowT).strftime("%Y-%m-%d %H:%M:%S"),term.black,term.bgwhite)
                    term.write(" %dWh" % (self.totalWatts+self.totalWatts2),term.red,term.bgwhite)
                    if self.setpoint:
                        term.write(" %0.1f°C" % self.setpoint,term.black,term.bgwhite)
                    if self.setpoint2:
                        term.write("*",term.red,term.bgwhite)
                        
                    #term.write(" %0.1fV" % batt,term.blue,term.bgwhite)
                    term.clearLineFromPos()
                    term.writeLine(" %dLh " % self.T_Pump.pump.liters(),term.bold,term.bgwhite, term.red if self.T_Pump.paused else term.yellow)
                    term.pos(lines-2,1)
                    for letter in menus.sortedActions1:
                        names = menus.actionName[letter]
                        term.write(letter, term.bgwhite, term.red)
                        term.write((":"+str(names[1])+" "),term.black,term.bgwhite)
                    term.clearLineFromPos()
                    term.writeLine("?", term.black,term.bgwhite)
                    term.pos(lines-1,1)
                    for letter in menus.sortedActions2:
                        names = menus.actionName[letter]
                        term.write(letter, term.bgwhite, term.red)
                        term.write((":"+str(names[1])+" "),term.black,term.bgwhite)
                    term.clearLineFromPos()
                    term.write("?", term.black,term.bgwhite)
              except:
                traceback.print_exc()

    def close(self):
        self.set_temp(None,None)
        #self.set_cold(None)
        self.running = False
        time.sleep(0.1)
        self.join()
        self.dacSetting.close()
        #self.dacSetting2.close()
        
# Pump speed types
NUL_SPEED = 0
OPT_SPEED = -1
HALF_SPEED = -2
MAX_SPEED = -3

class Operation(object):

    global menus,lines,columns, taps, optimal_speed

    def __init__(self, acronym, typeOp, sensor1=None, sensor2=None, ref=None, ref2=None, base_speed=None, min_speed=None, qty=None, shake_qty=None, duration=None, subSequence = None, dump=False, inject=None, message=None, tap=None, cooling=False, programmable=False):
        self.acronym = acronym
        self.typeOp = typeOp
        self.sensor1 = sensor1
        self.sensor2 = sensor2
        self.ref = ref
        self.ref2 = ref2
        self.base_speed = base_speed
        self.min_speed = min_speed
        if not self.min_speed and self.base_speed:
            self.min_speed = -self.desired_speed()
        self.qty = qty
        self.shake_qty = shake_qty
        self.duration = duration
        self.subSequence = subSequence
        self.dump = dump
        self.inject = inject
        self.message = message
        if not tap:
            self.tap = 'H'
        else:
            self.tap = tap
        self.cooling = cooling # if cooling of output is permitted. Auto-Pause (option Q) is then also taken into account
        self.programmable = programmable
    
    def tempRef(self): # Current heating temperature along what is set in options
        if not self.ref: # do not heat !
            return 0.0
        return menus.options[self.ref][3]
        
    # def tempRef2(self): # Current heating temperature along what is set in options
        # if not self.ref2: # do not heat !
            # return None
        # return menus.options[self.ref2][3]
        
    def desired_speed(self): # current speed even if options have changed
        if not self.base_speed or self.base_speed == NUL_SPEED:
            return 0.0
        if self.base_speed == OPT_SPEED:
            return optimal_speed
        if self.base_speed == HALF_SPEED:
            return pumpy.maximal_liters / 2.0
        if self.base_speed == MAX_SPEED:
            return pumpy.maximal_liters
        return self.base_speed # If positive, absolute value

    # Initialize current operation and starts it if it is not the pump...
    def start(self,T_Pump):

        global menus, taps

        time.sleep(0.01)
        dumpValve.set(1.0 if self.dump else 0.0)
        T_Pump.currOpContext = OperationContext(self,T_Pump.pump)
        if not self.programmable or not menus.options['H'][3] or floating_time(datetime.now()) >= float(menus.options['H'][3]):
            T_Pump.T_DAC.set_temp(self.tempRef()+menus.options['G'][3]) #, self.tempRef2())
        else:
            T_Pump.T_DAC.set_temp(None) #,None) # Delayed start
        # if self.cooling:
            # T_Pump.T_DAC.set_cold(menus.options['T'][3])
        # else:
            # T_Pump.T_DAC.set_cold(None)
        if self.typeOp == 'FLOO':
            taps[self.tap].set(1)
            if self.tap == 'H': # Run the head pump with the flood...
                T_Pump.pump.stop()
                # if HEAT_EXCHANGER:
                    # T_Pump.pump.pump1.run(-T_Pump.pump.pump1.maxSpeed) # Attention NE TIENT PAS COMPTE DE inverse1 !
        elif self.typeOp == 'REVR':
            T_Pump.pump.reset_pump()
        elif self.typeOp == 'PAUS':
            Buzzer.on()
            T_Pump.setPause(True)
            tell_message(self.message)
        elif self.typeOp == 'SUBR': # 1st Call a subroutine and loop...
            i = 0
            for op in opSequences[self.subSequence]:
                T_Pump.currSequence.insert(i,op)
                i += 1
            # prepare Subsequent execution of a subroutine
            #print ("SUBR %f.3 sec." % self.duration)
            #time.sleep(3.0)
            copOp = Operation(self.acronym,'SUBS',duration=self.duration,subSequence=self.subSequence)
            T_Pump.currSequence.insert(i,copOp)
            T_Pump.pushContext(T_Pump.currOpContext)
        elif self.typeOp == 'SUBS': # Subsequent Call of a subroutine and loop...
            T_Pump.currOpContext = T_Pump.popContext()
            requiredTime = self.duration() if self.duration else None
            if requiredTime and (T_Pump.currOpContext.duration() >= requiredTime):
                pass
            else: # insérer la sous-séquence
                i = 0
                for op in opSequences[self.subSequence]:
                    T_Pump.currSequence.insert(i,op)
                    i += 1
                T_Pump.currSequence.insert(i,self)
                T_Pump.pushContext(T_Pump.currOpContext)
            # passer à l'instruction suivante le plus vite possible...
        time.sleep(0.01)

    # Checks if current operation is finished
    def isFinished(self):

        global confirmation, cohorts

        time.sleep(0.01)
        dumpValve.set(1.0 if self.dump else 0.0) # Will stop command if open/close duration is done

        requiredTime = self.duration() if self.duration else None
        if requiredTime and T_Pump.currOpContext and (T_Pump.currOpContext.duration() >= requiredTime):
            return True
        if self.typeOp == 'HEAT':
            if float(cohorts.getCalibratedValue('heating')) >= float(self.tempRef()+menus.options['G'][3]-0.2):
                return True
        elif self.typeOp in ['PUMP','FLOO','TRAK','EMPT','REVR']:
            if self.qty and T_Pump.currOpContext:
                if self.qty > 0.0 and (T_Pump.currOpContext.volume() >= self.qty):
                    return True
                if self.qty < 0.0:
                    volnow = T_Pump.currOpContext.volume()
                    if (volnow <= self.qty):
                        return True
                    elif volnow > 0.2: # on part dans le mauvais sens !
                        T_Pump.pump.reset_pump()
                        return True
            return False # not finished
        elif self.typeOp == 'SHAK':
##            if self.sensor1 and self.value1 \
##               and T_Pump.pump.speed > 0.0 \
##               and (float(cohorts.catalog[self.sensor1].value) >= float(self.value1)):
##                return True
            return False
        elif self.typeOp == 'PAUS': # Switch to next operation
            return not T_Pump.paused
        elif self.typeOp in ['SUBR','SUBS','MESS']: # Switch to next operation
            return True
        time.sleep(0.01)

    # Keep going in the current operation
    def execute(self,now,T_Pump):

        global menus, taps

        time.sleep(0.01)
        dumpValve.set(1.0 if self.dump else 0.0) # Will stop command if open/close duration is done
        if not self.programmable or not menus.options['H'][3] or floating_time(datetime.now()) >= float(menus.options['H'][3]):
            T_Pump.T_DAC.set_temp(self.tempRef()+menus.options['G'][3]) #,self.tempRef2()) # In case of a manual change
        else:
            T_Pump.T_DAC.set_temp(None) #, None) # Delayed start
        # if self.cooling:
            # T_Pump.T_DAC.set_cold(menus.options['T'][3])
            # if zeroIsNone(menus.options['Q'][3]):
                # if T_Pump.pump.volume() > menus.options['Q'][3]:
                    # T_Pump.setPause(True)
                    # menus.options['Q'][3] = 0.0 # reset the option...
        # else:
            # T_Pump.T_DAC.set_cold(None)
        speed = T_Pump.pump.liters()
        if self.typeOp in ['HEAT','PAUS']:
            speed = 0.0
        elif self.typeOp in ['PUMP','EMPT','REVR']:
            speed = self.desired_speed()
            if self.typeOp == 'REVR':
                speed = -speed
        elif self.typeOp == 'FLOO':
            speed = -self.desired_speed()
            taps[self.tap].set(1)
            # if HEAT_EXCHANGER:
                # if self.tap == 'H': # Run the head pump with the flood...
                    # if T_Pump.pump.pump1.speed != T_Pump.pump.pump1.maxSpeed:
                        # T_Pump.pump.stop()
                        # T_Pump.pump.pump1.run( -T_Pump.pump.pump1.maxSpeed) # Attention NE TIENT PAS COMPTE DE inverse1 !
        elif self.typeOp == 'SHAK':
            #print ("S=%f\r" % speed)
            if speed == 0.0:
                speed = self.min_speed
            elif speed > 0.0:
                if self.shake_qty and T_Pump.pump.current_liters(now) >= self.shake_qty:
                    speed = self.min_speed
                else:
                    speed = self.desired_speed()
            else: #speed < 0.0
                if self.shake_qty and T_Pump.pump.current_liters(now) <= (-self.shake_qty):
                    speed = self.desired_speed()
                else:
                    speed = self.min_speed
            #print ("s=%f\r" % speed)
        elif self.typeOp == 'TRAK':
            valSensor1 = cohorts.getCalibratedValue(self.sensor1)
            if float(valSensor1) < float(self.tempRef()): # Shake
                if self.min_speed >= 0.0:
                    speed = self.min_speed
                elif speed == 0.0:
                    speed = self.min_speed
                elif speed > 0.0:
                    if self.shake_qty and T_Pump.pump.current_liters(now) >= self.shake_qty:
                        speed = self.min_speed
                    else:
                        speed = -self.min_speed
                else:
                    if self.shake_qty and T_Pump.pump.current_liters(now) <= (-self.shake_qty):
                        speed = -self.min_speed
                    else:
                        speed = self.min_speed
                #print("SHAK="+str(speed)+"\r")
            else:
                totalVol,totalTime,beginTemp,endTemp = cohorts.evolution(self.sensor2,self.sensor1)
                #print("EVOL="+str(totalVol)+"L/"+str(totalTime)+"s "+str(beginTemp)+"°C<"+str(endTemp)+"°C\r")
                if not totalVol or (totalVol <= 0.0) or (endTemp <= beginTemp) or (self.tempRef() <= beginTemp): # no data
                    speed = self.desired_speed()
                    #print("NUL="+str(speed)+"\r")
                else:
                    speed0 = T_Pump.pump.liters()
                    try:
                        speed = ((endTemp-beginTemp) / (self.tempRef()-beginTemp)) * (totalVol/(PUMP_SLOWDOWN*totalTime/3600.0))
                        if speed0 > 0.0:
                            if speed > (speed0*1.5): # dampen accelerations
                                speed = speed0*1.5
                        #print("CAL="+str(speed)+"\r")
                    except:
                        #traceback.print_exc()
                        if speed0 > 0.0:
                            speed = speed0
                        else:
                            speed = 0.0
                        #print("BAD="+str(speed)+"\r")
            if T_Pump.pump.speed > 0.0:
                diff = speed - T_Pump.pump.liters()
                if diff < 0.0:
                    diff = (-diff)
                #print("DIFF="+str(diff)+"\r")
                if diff < (T_Pump.pump.liters() / 25.0):
                    speed = T_Pump.pump.liters()
            if speed > self.desired_speed():
                speed = self.desired_speed()
            elif speed == 0.0:
                speed = self.desired_speed()
        if speed >= 0.0:
            if speed > T_Pump.pump.maximal_liters:
                speed = T_Pump.pump.maximal_liters
        else:
            if speed < -T_Pump.pump.maximal_liters:
                speed = -T_Pump.pump.maximal_liters
        #print("RUN speed="+str(speed)+"\r")
        return speed

    # Close anything needed with current operation to end gracefully
    def close(self,T_Pump):
        
        global menus, taps
        
        if self.programmable and menus.options['H'][3] and menus.options['H'][3] != 0.0 and floating_time(datetime.now()) >= float(menus.options['H'][3]):
            menus.options['H'][3] = 0.0
        #T_Pump.T_DAC.set_cold(None)
        if self.typeOp == 'FLOO':
            T_Pump.pump.stop()
            taps[self.tap].set(0)
        elif self.typeOp in ['REVR']:
            T_Pump.pump.reset_pump()
        elif self.typeOp in ['PUMP','SHAK','TRAK','EMPT']:
            T_Pump.pump.stop()
        if self.message:
            if self.typeOp != 'PAUS':
                tell_message(self.message)
        T_Pump.T_DAC.set_temp(None, None)
        dumpValve.setWait(1.0 if self.dump else 0.0)

# Tracks volumes based on speed and time
# if HEAT_EXCHANGER:
    # pumpy = pump.double_pump(addr0=0,addr1=1,inverse1=True)
# else:
    # pumpy = pump.pump()
pumpy = pump_pwm.pump_PWM()
cohorts.pumpAddress = pumpy.address
cohorts.addSensor(pumpy.address,pumpy)

class OperationContext(object):

    def __init__(self, operation,pump):
        self.operation = operation
        self.startTime = time.perf_counter()
        self.startVolume = pump.volume()
        self.pump = pump

    def duration(self):
        return time.perf_counter() - self.startTime

    def extend_duration(self,extension):
        self.startTime += extension

    def volume(self):
        return self.pump.volume()-self.startVolume

optimal_speed = 0.0

opSequences = {
    # 'L': [Operation('PAUS','MESS',message="Lait = 72°C!")],
    # 'Y': [Operation('PAUS','MESS',message="Yaourt = 85°C!")],
    # 'T': [Operation('PAUS','MESS',message="Thermisation = 65°C!")],
    # 'S': [Operation('PAUS','MESS',message="Pause!")],
    # '_': [Operation('PAUS','MESS',message="Redémarrer!")],
    # 'X': [Operation('STOP','MESS',message="Au revoir!")],
    # 'Z': [Operation('STOP','MESS',message="Arrêt de l'opération en cours")],
    'A': # Amorçage, pré chauffage...
        [ Operation('AmoT','HEAT',ref='P', ref2='P', dump=True,programmable=True),
          Operation('AmoI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='P', ref2='P', dump=False),
          Operation('AmoJ','HEAT',ref='P', ref2='P', dump=False),
          Operation('Amoi','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='P',ref2='P',dump=False),
          Operation('Amoo','SUBR',duration=lambda:menus.options['r'][3],subSequence='a',dump=False),
          Operation('AmoP','PUMP',ref='P',ref2='P', base_speed=MAX_SPEED, qty=1.0,dump=False),
          Operation('CLOS','MESS',message=ml.T("Déconnecter le tuyau d'entrée, P pour pasteuriser!","Disconnect input pipe, P to pasteurize!","Ontkoppel de invoerleiding, P om te pasteuriseren!"),dump=True)
          ],
          
    'a': # Étape répétée du nettoyage
        [ Operation('Amop','PUMP',ref='P',ref2='P', base_speed=MAX_SPEED, qty=2.0,dump=False),
          Operation('AmoS','REVR',ref='P',ref2='P', base_speed=MAX_SPEED, qty=-0.4,dump=False)
          ],
          
    # 'C': # Enchainement complet
        # [ Operation('PreT','HEAT',ref='R',ref2='R',dump=True,programmable=True),
          # Operation('PreI','FLOO',duration=lambda:menus.options['r'][3]*2.0,ref='R',ref2='R',dump=True),
          # Operation('PreW','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,ref='R',ref2='R',dump=True),
          # Operation('RinI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='R',ref2='R',dump=False),
          # Operation('Rinc','SUBR',duration=lambda:menus.options['r'][3],subSequence='r',dump=False),
          # Operation('RinV','FLOO',duration=lambda:menus.options['r'][3]/2.0,ref='R',ref2='R',dump=True),
          # Operation('RinW','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,ref='N',ref2='N',dump=True),
          # Operation('NetT','HEAT',ref='N',ref2='N',dump=True),
          # Operation('NetI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='N',ref2='N',dump=False),
          # Operation('NETY','PAUS',message=ml.T("Mettre le Nettoyant dans le seau puis Redémarrer!","Put the Cleaner in the bucket then press Restart!","Zet de Cleaner in de emmer en druk op Herstart!"),ref='N',ref2='N',dump=False),
          # Operation('Neti','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='N',ref2='N',dump=False),
          # Operation('Neto','SUBR',duration=lambda:menus.options['n'][3],subSequence='n',dump=False),
          # Operation('NetF','FLOO',duration=lambda:menus.options['r'][3],ref='N',ref2='N',dump=True),
          # Operation('NetV','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,ref='N',ref2='N',dump=True),
          # Operation('MidT','HEAT',ref='R',ref2='R',dump=True),
          # Operation('MidI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='R',ref2='R',dump=False),
          # Operation('Midc','SUBR',duration=lambda:menus.options['r'][3],subSequence='r',dump=False),
          # Operation('MidW','EMPT',base_speed=MAX_SPEED, qty=DRY_VOLUME,ref='R',ref2='R',dump=True),
          # Operation('MidZ','PAUS',message=ml.T("Faire Arrêt pour éviter la désinfection, sinon cliquez Redémarrer!","Press STOP to avoid Disinfection. Else click Restart!","Druk op STOP om desinfectie te voorkomen. Anders klikt u op Herstart!"),ref='D',ref2='D',dump=False),
          # Operation('DesT','HEAT',ref='D',ref2='D',dump=True),
          # Operation('DesI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='D',ref2='D',dump=False),
          # Operation('DESN','PAUS',message=ml.T("Mettre le Désinfectant dans le seau puis Redémarrer!","Put the Disinfectant in the bucket then Restart!","Doe het desinfectiemiddel in de emmer en druk op een toets!"),ref='D',ref2='D',dump=False),
          # Operation('Desi','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='D',ref2='D',dump=False),
          # Operation('Desf','SUBR',duration=lambda:menus.options['d'][3],subSequence='d',dump=False),
          # Operation('DesV','EMPT',base_speed=MAX_SPEED, qty=DRY_VOLUME,dump=True),
          # #Operation('DesR','EMPT',base_speed=-pumpy.maximal_liters, qty=-DRY_VOLUME,dump=True),
          # Operation('CLOS','MESS',message=ml.T("Cycle COMPLET terminé!","FULL cycle completed!","VOLLEDIGE cyclus voltooid!"),dump=True)
          # ],

    'F': # Pré-rinçage (Flush)
        [ Operation('PreT','HEAT',ref='R', ref2='t',dump=True,programmable=True),
          Operation('PreI','FLOO',duration=lambda:menus.options['r'][3],ref='R',ref2='R',dump=True),  # 
          Operation('PreR','FLOO',duration=lambda:13,ref='R',ref2='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('CLOS','MESS',message=ml.T("Recommencer au besoin!","Repeat if needed!","Herhaal indien nodig!"),dump=True)
          ],
    'R': # Pré-rinçage 4 fois
        [ Operation('Pr1T','HEAT',ref='R', ref2='t',dump=True,programmable=True),
          Operation('Pr1I','FLOO',duration=lambda:menus.options['r'][3],ref='R',ref2='R',dump=True),  # 
          Operation('Pr1R','FLOO',duration=lambda:13,ref='R',ref2='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('Pr2T','HEAT',ref='R', ref2='t',dump=True,programmable=True),
          Operation('Pr2I','FLOO',duration=lambda:menus.options['r'][3],ref='R',ref2='R',dump=True),  # 
          Operation('Pr2R','FLOO',duration=lambda:13,ref='R',ref2='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('Pr3T','HEAT',ref='R', ref2='t',dump=True,programmable=True),
          Operation('Pr3I','FLOO',duration=lambda:menus.options['r'][3],ref='R',ref2='R',dump=True),  # 
          Operation('Pr3R','FLOO',duration=lambda:13,ref='R',ref2='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('Pr4T','HEAT',ref='R', ref2='t',dump=True,programmable=True),
          Operation('Pr4I','FLOO',duration=lambda:menus.options['r'][3],ref='R',ref2='R',dump=True),  # 
          Operation('Pr4R','FLOO',duration=lambda:13,ref='R',ref2='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('CLOS','MESS',message=ml.T("4 rinçages effectués!","4 flushes done!","4 keer doorspoelen!"),dump=True)
          ],
    'V': # Vider le réservoir (aux égouts la plupart du temps)
        [  Operation('VidV','EMPT',base_speed=MAX_SPEED, qty=DRY_VOLUME,dump=True),
           Operation('CLOS','MESS',message=ml.T("Tuyaux vidés autant que possible.","Pipes emptied as much as possible.","Leidingen zoveel mogelijk geleegd."),dump=True)
        ],
    'D': # Désinfectant
        [ Operation('DesT','HEAT',ref='D',ref2='D',dump=False,programmable=True),
          Operation('DesI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='D',ref2='D',dump=False),
          Operation('DESN','PAUS',message=ml.T("Mettre le Désinfectant dans le seau puis une touche!","Put the Disinfectant in the bucket then press a key!","Doe het desinfectiemiddel in de emmer en druk op een toets!"),ref='D',ref2='D',dump=False),
          Operation('Desi','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='D',ref2='D',dump=False),
          Operation('Desf','SUBR',duration=lambda:menus.options['d'][3],subSequence='d',dump=False),
          #Operation('DesV','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,dump=True),
          Operation('CLOS','MESS',message=ml.T("Faites V pour vider puis rincer!","Press V to empty and then rinse!","Druk op V om te legen en spoel daarna af!"),dump=True)
        ],
    'd': # Étape répétée de la désinfection
        [ Operation('DesS','PUMP',ref='D',ref2='D', base_speed=MAX_SPEED, qty=4.0,dump=False),
          Operation('DesP','REVR',ref='D',ref2='D', base_speed=MAX_SPEED, qty=-2.0,dump=False)
        ],
    'N': # Détergent
        [ Operation('NetT','HEAT',ref='N',ref2='N',dump=False,programmable=True),
          Operation('NetI','FLOO',duration=lambda:menus.options['r'][3]*1.5,ref='N',ref2='N',dump=False),
          Operation('NETY','PAUS',message=ml.T("Mettre le Nettoyant dans le seau puis une touche!","Put the Cleaner in the bucket then press a key!","Zet de Cleaner in de emmer en druk op een toets!"),ref='N',ref2='N',dump=False),
          Operation('Neti','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='N',ref2='N',dump=False),
          Operation('Neto','SUBR',duration=lambda:menus.options['n'][3],subSequence='n',dump=False),
          #Operation('NetV','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,dump=True),
          Operation('CLOS','MESS',message=ml.T("Faites V pour vider puis rincer!","Press V to empty and then rinse!","Druk op V om te legen en spoel daarna af!"),dump=True)
        ],
    'n': # Étape répétée du nettoyage
        [ Operation('NetS','PUMP',ref='N',ref2='N', base_speed=MAX_SPEED, qty=4.0,dump=False),
          Operation('NetP','REVR',ref='N',ref2='N', base_speed=MAX_SPEED, qty=-2.0,dump=False)
          ],
    'P': # Pasteurisation
        [ Operation('PasT','HEAT',ref='P',ref2='t', dump=True,programmable=True),
          Operation('PasI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=START_VOL,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('Pasi','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=TOTAL_VOL-START_VOL,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('PasE','PAUS',message=ml.T("Secouer/Vider le tampon puis une touche pour embouteiller","Shake / Empty the buffer tank then press a key to start bottling","Schud / leeg de buffertank en druk op een toets om het bottelen te starten"),ref='P',ref2='t', dump=True),
          Operation('PasP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P',ref2='t', shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ],
    'I': # Reprise d'une Pasteurisation
        [ Operation('PasT','HEAT',ref='P',ref2='t', dump=True,programmable=True),
          Operation('PasP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P',ref2='t', shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ],
    'E': # Eau pour finir une Pasteurisation en poussant juste ce qu'il faut le lait encore dans les tuyaux
        [ Operation('EauT','HEAT',ref='P',ref2='t', dump=True,programmable=True),
          Operation('EauI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=SHAKE_QTY,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('EauP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=START_VOL-SHAKE_QTY,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('EauV','PUMP', base_speed=MAX_SPEED, ref='P',ref2='t', qty=(TOTAL_VOL*0.96)-START_VOL,dump=True,cooling=True),
          Operation('CLOS','MESS',message=ml.T("Faites C quand vous voulez nettoyer!","Press C when you want to clean!","Druk op C als u wilt reinigen!"),dump=True)
          ],
    'M': # Passer à un lait d'un autre provenance en chassant celui de la pasteurisation précédente
        [ Operation('Mult','HEAT',ref='P',ref2='t', dump=True,programmable=True),
          Operation('Muli','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=SHAKE_QTY,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('Mulp','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=START_VOL-SHAKE_QTY,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('MulC','PAUS',message=ml.T("Consigne nouveau lait puis une touche pour finir de chasser le 1er lait","Setpoint for New milk then press a key to finish bottling 1st","Instelpunt voor nieuwe melk en druk vervolgens op een toets om het bottelen eerst te beëindigen"),ref='P',ref2='t', dump=True),
          Operation('MulT','HEAT',ref='P',ref2='t', dump=True),
          Operation('MulP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters*1.5, ref='P',ref2='t', qty=(TOTAL_VOL*0.96)-START_VOL,shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('MulE','PAYS',message=ml.T("Contenant pour le nouveau lait!","New Milk container!","Houder voor nieuwe melk!"),ref='P',ref2='t', dump=True),
          Operation('MulH','HEAT',ref='P',ref2='t', dump=True),
          Operation('MulI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P',ref2='t', shake_qty=SHAKE_QTY,dump=True,cooling=True),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ]
    }

def reloadPasteurizationSpeed():

  global menus,pumpy,pasteurization_tube,optimal_speed
  
  if menus.options['M'][3] < 15.0: # Minimum légal = 15 secondes de pasteurisation
      menus.options['M'][3] = 15.0
  optimal_speed = (pasteurization_tube / menus.options['M'][3]) * 3600.0 / 1000.0 # duree minimale de pasteurisation (sec) --> vitesse de la pompe en L/heure
  if optimal_speed > pumpy.maximal_liters: # trop lent est sans doute dangereux
      optimal_speed = pumpy.maximal_liters
  elif optimal_speed < pumpy.minimal_liters: # trop lent est sans doute dangereux
      optimal_speed = pumpy.minimal_liters
  # i=input(str(max_liters))

class ThreadPump(threading.Thread):

    def __init__(self, pumpy, T_DAC):
        threading.Thread.__init__(self)
        self.running = False
        self.pump = pumpy
        self.T_DAC = T_DAC
        self.currAction = 'Z'
        self.currSequence = None
        self.currOperation = None
        self.currOpContext = None
        self.operationContextStack = []
        self.paused = False
        self.startPause = 0
        self.pumpLastChange = 0 # Time of last change in pump running
        self.pumpLastVolume = 0
        self.pumpLastHeating = 0

    def pushContext(self,opContext):
        if opContext:
            self.operationContextStack.append(opContext)

    def popContext(self):
        lgStack = len(self.operationContextStack)
        if not lgStack:
            return None
        opContext = self.operationContextStack.pop()
        return opContext

    def topContext(self):
        lgStack = len(self.operationContextStack)
        if not lgStack:
            return None
        return self.operationContextStack[-1]

    def startOperation(self,op):
        self.currOperation = op
        op.start(self)

    def nextOperation(self):
        if self.currOperation:
            self.currOperation.close(self)
            self.currOperation = None
        if self.currSequence and len(self.currSequence):
            self.currOperation = self.currSequence[0]
            self.currSequence = self.currSequence[1:]
            self.startOperation(self.currOperation)

    def closeSequence(self): # Executer la dernière opération si elle sert à cloturer une sequence
        if self.currOperation and self.currOperation.acronym != 'CLOS':
            self.currOperation.close(self)
            self.currOperation = None
        if self.currSequence and len(self.currSequence):
            lastOp = self.currSequence[len(self.currSequence)-1]
            self.currSequence = None
            if lastOp.acronym == 'CLOS':
                self.startOperation(lastOp)
        else:
            self.currSequence = None

    def stopAction(self):
        # do whatever is needed
        self.closeSequence()
        time.sleep(0.01)
        self.pump.reset_pump() # to be sure that no situation ends with a running pump...
        time.sleep(0.01)
        self.currAction = 'Z' # Should stop operations...

    def setAction(self,action):
        global opSequences
        action = action.upper()
        if action in opSequences:
            self.stopAction()
            self.currAction = action
            self.startAction = time.perf_counter()
            self.pump.reset_volume()
            self.setPause(False);
            self.currSequence = []
            for op in opSequences[action]:
                self.currSequence.append(op)
            self.nextOperation()
            return True
        return False

    def setPause(self,paused):
        if self.paused and not paused:
            if self.currOpContext:
                self.currOpContext.extend_duration(time.perf_counter()-self.startPause)
        self.pumpLastChange = time.perf_counter()
        self.pumpLastVolume = self.pump.volume()
        self.pumpLastHeating = self.T_DAC.totalWatts
        if not self.paused and paused:
            self.startPause = self.pumpLastChange
        if paused:
            T_Pump.pump.reset_pump()
        self.paused = paused
        
    def durationRemaining(self):
        if not self.currOperation:
            return 0
        if not self.currOperation.duration:
            if self.currOperation.typeOp == 'HEAT':
                heating = cohorts.getCalibratedValue('heating')
                diffTemp = float(self.currOperation.tempRef()+menus.options['G'][3]-0.2)-float(heating)
                if diffTemp <= 0.0:
                    return 0
                else:
                    return int(diffTemp * tank * kCalWatt / HEAT_POWER * 3600)
            else:
                subr = self.topContext()
                if subr and subr.operation and subr.operation.duration:
                    return subr.operation.duration()- subr.duration()
                return 0
        else:
            return self.currOperation.duration() - self.currOpContext.duration()

    def quantityRemaining(self):
        if not self.currOperation:
            return 0.0
        if not self.currOperation.qty:
            subr = self.topContext()
            if subr and subr.operation and subr.operation.qty:
                vol = subr.volume()
                if subr.operation.qty > 0.0 and (vol < subr.operation.qty):
                    return subr.operation.qty - vol
                if subr.operation.qty < 0.0 and (vol > subr.operation.qty):
                    return vol - subr.operation.qty
            return 0.0
        vol = T_Pump.currOpContext.volume()
        if self.currOperation.qty > 0.0 and (vol < self.currOperation.qty):
            return self.currOperation.qty - vol
        if self.currOperation.qty < 0.0 and (vol > self.currOperation.qty):
            return vol - self.currOperation.qty
        return 0.0

    def run(self):

        global display_pause, WebExit

        if GreenLED:
            GreenLED.off()
        if YellowLED:
            YellowLED.off()
        if RedLED:
            RedLED.off()

        self.running = True
        while self.running:
            try:
                time.sleep(0.3)
                now = time.perf_counter()
                if RedButton.get() == 1:
                    if not self.currAction in ['X','Z',' ']:
                        self.stopAction()
                        if RedLED:
                            RedLED.blink(2)
                        time.sleep(2.0) # Press long!
                    else:
                        self.currAction = 'X'
                        os.kill(os.getpid(),signal.SIGINT)
                        WebExit = True # SHUTDOWN !
                if YellowButton.get() == 1:
                    if not self.paused:
                        self.setPause(True)  # Will make the pump stops !
                if GreenButton.get() == 1:
                    if self.paused:
                        self.setPause(False)
                Buzzer.off()
                if RedLED:
                    if not self.currAction in ['X','Z',' ']:
                        RedLED.on ()
                    else:
                        RedLED.blink (2)
                if self.paused:
                    speed = 0.0
                    if YellowLED:
                        if not self.currAction in ['X','Z',' ']:
                            YellowLED.on()
                        else:
                            YellowLED.off()
                    if GreenLED:
                        GreenLED.blink(2) # blink twice per second
                else:
                    if GreenLED:
                        GreenLED.off()
                    if YellowLED:
                        YellowLED.on();
                    if not self.currOperation:
                        if not self.currSequence or not len(self.currSequence):
                            speed = 0.0
                            T_DAC.set_temp(None, None)
                            #T_DAC.set_cold(None)
                        else:
                            self.nextOperation()
                    while self.currOperation and self.currOperation.isFinished(): # Is it finished?
                        self.nextOperation()
                    if self.currOperation:
                        speed = self.currOperation.execute(now,self)
                    else:
                        speed = 0.0
                prec_speed = self.pump.liters()
                if speed != prec_speed:
                    time.sleep(0.01)
                    if speed == 0.0:
                        self.pump.stop()
                    else:
                        # if (speed > 0.0) == (prec_speed > 0.0):
                            # if prec_speed != 0.0:
                                # self.pump.stop()
                                # time.sleep(0.1)
                        self.pump.run_liters(speed)
                    time.sleep(0.01)
                    if not DEBUG:
                        prec_disp = display_pause
                        display_pause = True
                        (lines,cols) = termSize()
                        term.pos(1,cols-10)
                        term.write("%5.2d" % speed, term.bold, term.yellow if speed > 0.0 else term.red, term.bgwhite)
                        display_pause = prec_disp
            except:
                traceback.print_exc()
                self.pump.stop()
                prec_speed = 0.0
                prec = time.perf_counter()
        time.sleep(0.01)
        self.pump.stop()

    def close(self):
        self.running = False
        time.sleep(0.1)
        self.pump.close()
        time.sleep(0.1)
        if RedLED:
            RedLED.off()
        try:
            self.join()
        except:
            traceback.print_exc()

term.setTitle("pastOnomic, pasteurisation accessible")
(lines, columns) = termSize()
term.pos(lines,1)
for i in range(1,lines):
    term.writeLine(" ",term.black, term.bgwhite)

# Solenoids:
hotTapSolenoid = Solenoid('TAP',hardConf.TAP)
#coldTapSolenoid = Solenoid('CLD',hardConf.CLD)
taps['H'] = hotTapSolenoid
#taps['C'] = coldTapSolenoid

reloadPasteurizationSpeed()

T_OneWire = None

if hardConf.Rmeter:
    cohorts.addSensor("rmeter",sensor.Sensor(typeRMeter,"rmeter",hardConf.Rmeter))

if hardConf.OW_extra or hardConf.OW_heating:
    T_OneWire = ThreadOneWire()
    T_OneWire.daemon = True

    if hardConf.OW_extra:
        T_OneWire.sensorParam("extra",hardConf.OW_extra)  # Extra: typiquement sortie du refroidissement rapide
    #T_OneWire.sensorParam("temper",hardConf.OW_temper)  # Bain de tempérisation (sortie) régulé en refroidissement
    if hardConf.OW_heating:
        T_OneWire.sensorParam("heating",hardConf.OW_heating)  # Bain de chauffe

    T_OneWire.start()

T_Thermistor = ThreadThermistor()
T_Thermistor.daemon = True
T_Thermistor.sensorParam("input",hardConf.T_input) # Entrée
T_Thermistor.sensorParam("output",hardConf.T_output) # Sortie
T_Thermistor.sensorParam("warranty", hardConf.T_warranty) # Garantie sortie serpentin long
#T_Thermistor.sensorParam("temper",hardConf.T_sp9b) # Garantie entrée serpentin court
if hardConf.T_heating:
    T_Thermistor.sensorParam("heating",hardConf.T_heating)


if not pumpy.open():
    term.writeLine("Pompe inaccessible ???", term.red, term.bold, term.bgwhite)
pumpy.stop() # in case it was running wild!

# manage pump and keep track of volume pumped
T_PumpReading = None
if not hardConf.MICHA_device:
    T_PumpReading = pump_pwm.ReadPump_PWM(pumpy)
    T_PumpReading.daemon = True
    T_PumpReading.start()

# Keeps heating bath at temperature following Setpoint
T_DAC = ThreadDAC()
# Manage pump at a higher level and execute operations for a given Action sequence
T_Pump = ThreadPump(pumpy,T_DAC)

# Ball Valve:
dumpValve = Valve('DMP',hardConf.DMP_open,hardConf.DMP_close) # using default duration set in Valve.py...
dumpValve.set(1.0) # Open by default

defFile = datetime.now().strftime("%Y_%m%d_%H%M")
# term.write("Code de production ["+defFile+"] :", term.bgwhite, term.blue)
# term.write(" ",term.red, term.bold, term.bgwhite)
# try:
    # fileName = input("")
# except:
    # fileName = ""
#if not fileName:
fileName = defFile
data_file = open(DIR_DATA_CSV + fileName+".csv", "w")
data_file.write("epoch_sec\taction\toper\tstill\tqrem\twatt\tvolume\tpump\tpause\textra\tinput\twarant\toutput\theat\theatbath\trmeter\n") #\twatt2\ttemper\theat
term.write("Données stockées dans ",term.blue, term.bgwhite)
term.writeLine(os.path.realpath(data_file.name),term.red,term.bold, term.bgwhite)
data_file.close()

##x=""
##T_DAC.set_temp((options['P'][3] + BATH_TUBE))
##cohorts.dump()
##while x != "y":
##    display_pause = True
##    time.sleep(0.2)
##    x = str(getch()).lower()
##    if x:
##        if x=="d":
##            cohorts.last_travel("sp9")
##        elif x=="y":
##            break
##        else:
##            x=input("Start?")
##            x = float(x)
##            pumpy.run_liters(x)
##display_pause = False

##for x in cohorts.sequence:
##    print(x[0],x[1])
##a=input("next")

T_Thermistor.start()
T_DAC.T_Pump = T_Pump
T_DAC.start()
T_Pump.start()

APPLICATION_COOKIE = "pastOnomic"

### Web Server section
def ensureLogin(mail, password):
    if mail == KEY_ADMIN and password == PWD:
        infoCookie = mail + ',' + PWD
        web.setcookie(APPLICATION_COOKIE, infoCookie, expires=9000, samesite="Strict")
        return True
    return False

def init_access():
    
    global ml

    data = web.input(nifile={})
    if data and ('lang' in data) and data['lang']:
        ml.setLang(data['lang'])
    mail = None
    password = None
    redir = path = web.ctx.env.get('PATH_INFO')
    if data and ('mail' in data) and ('password' in data):
        mail = data['mail']
        password = data['password']
    else:
        infoCookie = web.cookies().get(APPLICATION_COOKIE)
        if infoCookie is not None:
            infoCookie = infoCookie.split(',')
            if len(infoCookie) > 1:  # and not isOtherDomain():
                mail = infoCookie[0].lower()
                password = infoCookie[1]
    connected = False
    if mail and password:
        connected = ensureLogin(mail, password)

    return data, connected, mail, password

def notfound():
    return web.notfound(render.notfound())

class WebIndex:
    def __init(self):
        self.name = u"WebIndex"

    def GET(self):
        data, connected, mail, password = init_access()
        return render.index(connected, mail, False, None)

    def POST(self):
        return self.GET()

class WebOption:
    def __init(self):
        self.name = u"WebOption"

    def GET(self,page):
        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')

        if data: # Process saved options from options editing forms
            if ('reset' in data and data['reset'].lower() == 'on'):
                for choice in (menus.cleanOptions if page == '1' else menus.dirtyOptions):
                    if len(menus.options[choice]) > 3:
                        menus.options[choice][3] = menus.options[choice][4]
            else:
                for keys in menus.options.keys():
                  if 'opt_'+keys in data:
                    val = data['opt_'+keys]
                    if not val:
                        menus.options[keys][3] = menus.options[keys][4]
                    else:
                        try:
                            val = float(val)
                            menus.options[keys][3] = val
                        except:
                            pass
            reloadPasteurizationSpeed()

        render_page = getattr(render, 'option'+page)
        return render_page(connected, mail)

    def POST(self,page):
        return self.GET(page)

class WebLogTable:
    def __init(self):
        self.name = u"WebLogTable"

    def GET(self):
        data, connected, mail, password = init_access()
        return render.index(connected,mail, True, None)

    def POST(self):
        return self.GET()

class WebExplain:

    def __init(self):
        self.name = u"WebExplain"

    def GET(self, letter):

        data, connected, mail, password = init_access()
        return render.index(connected,mail, False, letter)

class WebApiAction:

    def __init(self):
        self.name = u"WebApiAction"

    def GET(self, letter):

        global menus, WebExit

        data, connected, mail, password = init_access()
        web.header('Content-type', 'application/json; charset=utf-8')
        if not connected:
            result = {'message':'RECHARGER CETTE PAGE'}
        else:
            message = ""
            if letter == 'Y':  # Yaourt
                menus.options['P'][3] = 82.0
                menus.options['M'][3] = 30.0
                #menus.options['T'][3] = 45.0
                message = "82°C"
                reloadPasteurizationSpeed()
            elif letter == 'L':  # Lait
                menus.options['P'][3] = 72.0
                menus.options['M'][3] = 15.0
                #menus.options['T'][3] = 22.0
                message = "72°C"
                reloadPasteurizationSpeed()
            elif letter == 'T':  # Thermiser
                menus.options['P'][3] = 65.0
                menus.options['M'][3] = 30.0
                #menus.options['T'][3] = 35.0
                message = "65°C"
                reloadPasteurizationSpeed()
            elif letter == "S":  # Pause
                if not T_Pump.paused:
                   T_Pump.setPause(True)  # Will make the pump stops !
                   message = str(ml.T("Pause","Pause","Pauze"))
                else:
                   message = str(ml.T("Déjà en Pause","Already Paused","Al gepauzeerd"))
                time.sleep(0.01)
            elif letter == "_":  # Restart
                   if not T_Pump.paused:
                       message = str(ml.T("Pas en Pause","Not Paused","Niet gepauzeerd"))
                   else:
                       T_Pump.setPause(False)
                       message = str(ml.T("Redémarrage","Restart","Herstart"))
                   time.sleep(0.01)
                   if T_Pump.currOperation and (not T_Pump.currOperation.dump) and dumpValve.value != 0.0:
                       dumpValve.setWait(0.0)
                   time.sleep(0.01)
            elif letter == "U":  # Purge
                   dumpValve.setWait(1.0)
                   message = str(ml.T("Purge en cours","Purge bagan","Zuivering..."))
                   time.sleep(0.01)
            elif letter in ['X','Z']:
                T_Pump.stopAction()
                if letter == 'X':
                    T_Pump.currAction = 'X'
                    os.kill(os.getpid(),signal.SIGINT)
                    WebExit = True # SHUTDOWN !
            else:
                if not T_Pump.setAction(letter):
                    message = str(ml.T("Invalide","Invalid","Ongeldig"))
            result = {  'date':str(datetime.fromtimestamp(int(time.time()))),
                        'actionletter':letter,
                        'action':str(menus.actionName[letter][1]),
                        'actiontitle':str(menus.actionName[letter][3]),
                        'accro': T_Pump.currOperation.acronym if T_Pump.currOperation else "", \
                        'message':str(menus.actionName[letter][2])+': '+message,
                        'output': (3 if T_Pump.currOperation and (not T_Pump.currOperation.dump) else 2) if dumpValve.value == 1.0 else (0 if letter in ['P','E','I'] else 1), \
                        'pause': 1 if T_Pump.paused else 0 }
        return json.dumps(result)

    def POST(self,letter):
        return self.GET(letter)

def calib_digest(sensor):
    
    global temp_ref_calib
    
    means = {}
    for x in temp_ref_calib:
        app = x[sensor]
        if app:
            tru = x['reft']
            reducted = int(app/5.0)*5.0
            if not reducted in means:
                means[reducted] = [0, 0.0, 0.0]
            means[reducted] = [means[reducted][0]+1, means[reducted][1]+app, means[reducted][2]+tru]
    for key, val in means.items():
        q = val[0]
        val[1] = val[1]/q
        val[2] = val[2]/q
    return means

def calib_remove(sensor, temp_class):
    
    global temp_ref_calib
    
    for x in temp_ref_calib:
        app = x[sensor]
        if app and app >= temp_class and app < (temp_class+5.0):
            x[sensor] = None

class WebCalibrate:

    def __init(self):
        self.name = u"WebCalibrate"

    def GET(self, sensor=None):
        
        global calibrating, temp_ref_calib
        
        data, connected, mail, password = init_access()
        means = {}
        if not connected:
            raise web.seeother('/')
        elif sensor:
            to_be_saved = False
            if sensor[0] == '!':
                to_be_saved = True
                sensor = sensor[1:]
            elif sensor[0] == '*':
                sensor = sensor[1:]
                if 'class' in data and data['class']:
                    calib_remove(sensor,float(data['class']))
            if sensor == "reset":
                temp_ref_calib = []
                calibrating = True
            elif sensor == "merge": # not yet implemented...
                temp_ref_calib = cohorts.mergeCalibration(temp_ref_calib)
            elif sensor == "on":
                calibrating = True
            elif sensor == "off":
                calibrating = False
            elif len(temp_ref_calib) > 0 and sensor in temp_ref_calib[0]:
                means = calib_digest(sensor)
                if to_be_saved:
                    meansort = sorted(means.items())
                    cohorts.saveCalibration(DIR_DATA_CSV,sensor,meansort)
        return render.calibrate(sensor, calibrating, temp_ref_calib, means)
        
    def POST(self,sensor=None):
        return self.GET(sensor)

class WebApiPut:

    def __init(self):
        self.name = u"WebApiPut"

    def GET(self, sensor):
        
        global calibrating, temp_ref_calib, cohorts
        
        if sensor == "!s_REFT": # Reference sensor
            data = web.input(nifile={})
            if data and ('value' in data) and data['value']:
                ref_val = float(data['value'])
                if ref_val > -4.0 and ref_val < 120.0:
                    cohorts.reft.set(ref_val)
                    if calibrating:
                        now = time.time()
                        temp_ref_calib.append({'time':now,'reft':ref_val, \
                                    'extra': cohorts.catalog['extra'].value, \
                                    'input': cohorts.catalog['input'].value, \
                                    'output': cohorts.catalog['output'].value, \
                                    'warranty': cohorts.catalog['warranty'].value, \
                                    'heating': cohorts.catalog['heating'].value })
        return "" # Status 200 is enough !

    def POST(self,sensor):
        return self.GET(sensor)

class WebDisconnect:
    def __init(self):
        self.name = u"WebDisconnect"

    def GET(self):
        web.setcookie(APPLICATION_COOKIE, "", expires=-1)
        raise web.seeother('/')

    def POST(self):
        return self.GET()

class WebApiLog:
    def __init(self):
        self.name = u"WebApiLog"

    def GET(self):

        global T_DAC, T_Pump, menus, optimal_speed, cohorts

        data, connected, mail, password = init_access()
        web.header('Content-type', 'application/json; charset=utf-8')
        if False: #not connected and not guest:
            currLog = {'message':str(ml.T('RECHARGER CETTE PAGE',"RELOAD THIS PAGE","HERLAAD DEZE PAGINA"))}
        else:
            nowT = time.time()
            durationRemaining = T_Pump.durationRemaining()
            quantityRemaining = T_Pump.quantityRemaining()
            #temper = menus.options['T'][3]
            opt_temp = menus.options['P'][3]
            actif = False
            if T_Pump.currAction and T_Pump.currAction != 'Z':
                message = str(menus.actionName[T_Pump.currAction][2])
                if T_Pump.currOperation:
                    actif = True
                    opt_temp = T_Pump.currOperation.tempRef()
                    if opt_temp == 0.0:
                        opt_temp = menus.options['P'][3]
                    if T_Pump.currOperation.message:
                        message = str(T_Pump.currOperation.message)
                    else:
                        message = str(menus.operName[T_Pump.currOperation.typeOp])
                else:
                    message = str(ml.T("Opération terminée.","Operation completed.","Operatie voltooid."))
            else:
                message = str(ml.T("Choisir une action dans le menu...","Choose an action in the menu ...","Kies een actie in het menu ..."))
            pumping_time = time.perf_counter() - T_Pump.pumpLastChange
            pumping_volume = T_Pump.pump.volume() - T_Pump.pumpLastVolume
            heating_volume = T_DAC.totalWatts - T_Pump.pumpLastHeating
            currLog = {     'date': str(datetime.fromtimestamp(int(nowT))), \
                            'actif': 1 if actif else 0, \
                            'actionletter': T_Pump.currAction, \
                            'action': str(menus.actionName[T_Pump.currAction][1]), \
                            'actiontitle': str(menus.actionName[T_Pump.currAction][3]), \
                            'accro': T_Pump.currOperation.acronym if T_Pump.currOperation else "", \
                            'delay': durationRemaining, \
                            'remain': quantityRemaining, \
                            'totalwatts': T_DAC.totalWatts, \
                            #'totalwatts2': T_DAC.totalWatts2, \
                            'volume': T_Pump.pump.volume(), \
                            'speed': T_Pump.pump.liters() if not T_Pump.paused else 0, \
                            'extra': isnull(cohorts.getCalibratedValue('extra'), ''), \
                            'input': isnull(cohorts.getCalibratedValue('input'), ''), \
                            'output': isnull(cohorts.getCalibratedValue('output'), ''), \
                            'watts': isnull(cohorts.catalog['DAC1'].value*HEAT_POWER, ''), \
                            #'watts2': isnull(cohorts.catalog['DAC2'].value*MITIG_POWER, ''), \
                            'warranty': isnull(cohorts.getCalibratedValue('warranty'), ''), \
                            'heating': isnull(cohorts.getCalibratedValue('heating'), ''), \
                            #'temper': isnull(cohorts.getCalibratedValue('temper'), ''), \
                            'rmeter': isnull(cohorts.val('rmeter'), ''), \
                            'reft': isnull(cohorts.reft.value, ''), \
                            'message': message, \
                            #'opt_T': temper if temper <  99.0 else '', \
                            'opt_M': menus.options['M'][3], \
                            'opt_temp': opt_temp, \
                            'purge': (3 if T_Pump.currOperation and (not T_Pump.currOperation.dump) else 2) if dumpValve.value == 1.0 else (0 if T_Pump.currAction in ['P','E','I'] else 1), \
                            'pause': 1 if T_Pump.paused else 0, \
                            'pumpopt': optimal_speed, \
                            'pumpeff': (100.0*pumping_volume/(pumping_time/3600))/optimal_speed if pumping_time else 0, \
                            'heateff': (100.0*heating_volume/(pumping_time/3600))/HEAT_POWER if pumping_time else 0 \
                       }
        return json.dumps(currLog)

    def POST(self):
        return self.GET()

class getCSS:
    def GET(self, filename):
        web.header('Content-type', 'text/css')
        with open( os.path.join(DIR_STATIC,'css/') + filename) as f:
            try:
                return f.read()
            except IOError:
                web.notfound()

class getJS:
    def GET(self, filename):
        web.header('Content-type', 'application/javascript')
        with open( os.path.join(DIR_STATIC,'js/') + filename) as f:
            try:
                return f.read()
            except IOError:
                web.notfound()

class getCSV:
    def GET(self):

        global fileName

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        else:
            web.header('Content-type', 'text/csv')
            with open(DIR_DATA_CSV + fileName + ".csv") as f:
                try:
                    return f.read()
                except IOError:
                    web.notfound()

def restart_program():
    """Restarts the current program, with file objects and descriptors
       cleanup
    """
    _lock_socket.close()
    python = sys.executable
    args = sys.argv
    args[0] = os.path.join(DIR_BASE, os.path.basename(sys.argv[0]))
    os.execl(python, python, *args)

class WebLog(object):
    # format log on screen with some legibility...
    def write(self,data):
        data = data.split('\n')
        for line in data:
            if line:
                print (line+'\r')

    def flush(self):
        pass

class ThreadWebServer(threading.Thread):

    def __init__(self,app):
        threading.Thread.__init__(self,target=app.run)
        self.app = app

#    def run(self):
#        self.app.run()


    def stop(self):
        self.app.stop()
        self.join()

def freshHref(url):
    pieces = url.split('#')
    if len(pieces) < 2:
        pieces.append('')
    if pieces[0] == web.ctx.fullpath:
        return ' onclick="location.reload();" href="#'+pieces[1]+'"'
    else:
        return ' href="'+url+'" onclick="closeMenu()"'

#web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)
try:
    web.config.debug = False # NE JAMAIS METTRE A TRUE, CETTE APPLICATION NE SE "RELOADE" PAS !!!
    # Configuration Singleton ELSA
    web.template.Template.globals['str'] = str
    web.template.Template.globals['sorted'] = sorted
    web.template.Template.globals['round'] = round
    web.template.Template.globals['subprocess'] = subprocess
    web.template.Template.globals['menus'] = menus
    web.template.Template.globals['ml'] = ml
    web.template.Template.globals['web'] = web
    web.template.Template.globals['isnull'] = isnull
    web.template.Template.globals['zeroIsNone'] = zeroIsNone
    web.template.Template.globals['datetime'] = datetime
    web.template.Template.globals['freshHref'] = freshHref
    layout = web.template.frender(TEMPLATES_DIR + '/layout.html')
    render = web.template.render(TEMPLATES_DIR, base=layout)
    web.httpserver.sys.stderr = WebLog()
    urls = (
        '/', 'WebIndex',
        '/index.html', 'WebIndex',
        '/index', 'WebIndex',
        '/action/(.)', 'WebApiAction',
        '/explain/(.)', 'WebExplain',
        '/logtable', 'WebLogTable',
        '/option(.)', 'WebOption',
        '/calibrate/(.+)', 'WebCalibrate',
        '/calibrate', 'WebCalibrate',
        '/api/log', 'WebApiLog',
        '/api/put/(.+)', 'WebApiPut',
        '/favicon.(.+)', 'getFavicon',
        '/static/js/(.+)', 'getJS',
        '/static/css/(.+)', 'getCSS',
        '/js/(.+)', 'getJS',
        '/css/(.+)', 'getCSS',
        '/csv', 'getCSV',
        '/disconnect', 'WebDisconnect',
        #'/restarting', 'WebRestarting',
    )
    app = web.application(urls, globals())
    app.notfound = notfound
    webServerThread = ThreadWebServer(app)
    webServerThread.daemon = True
    webServerThread.start()
#    app.run()
except:
    traceback.print_exc()

### Console running in parallel with Web Server
display_pause = True
while T_Pump.currAction != 'X':
    try:
        time.sleep(0.2)
        now = time.time()
        menu_choice = str(getch()).upper()
        if menu_choice == ' ':
            display_pause = False
        elif menu_choice in ['X','Z','R','V','F','A','P','I','E','M','D','N']: # 'C','K'
            menu_choice = menu_confirm(menu_choice,8.0)
            if menu_choice == 'X':
                T_Pump.stopAction()
                break
            if menu_choice == 'Z':
                T_Pump.stopAction()
            elif menu_choice in ['R','V','F','A','P','I','E','M','D','N']: # 'C','K'
                T_Pump.setAction(menu_choice)
        elif menu_choice == "Y": # Yaourt
            menus.options['P'][3] = 82.0
            menus.options['M'][3] = 30.0
            #menus.options['T'][3] = 45.0
            option_confirm(0.0)
        elif menu_choice == "L": # Lait
            menus.options['P'][3] = 72.0
            menus.options['M'][3] = 15.0
            #menus.options['T'][3] = 22.0
            option_confirm(0.0)
        elif menu_choice == "T": # Thermiser
            menus.options['P'][3] = 65.0
            menus.options['M'][3] = 30.0
            #menus.options['T'][3] = 35.0
            option_confirm(0.0)
        elif menu_choice == "S": # Pause / Restart
            if not T_Pump.paused:
                T_Pump.setPause(True) # Will make the pump stops !
            menu_choice = menu_confirm(menu_choice)
            if menu_choice == "S":
                T_Pump.setPause(False)
            elif menu_choice == "V":
                T_Pump.setPause(False)
                T_Pump.setAction(menu_choice)
            elif menu_choice == 'Z':
                T_Pump.setPause(False)
                T_Pump.stopAction()
        elif menu_choice == "O": # Options...
            option_confirm()
        elif menu_choice:
            prec_pause = display_pause
            display_pause = True
            time.sleep(0.05)
            term.pos(lines,1)
            for choice in (menus.sortedActions1+menus.sortedActions2):
                term.write(choice, term.bgwhite, term.red)
                term.write((": "+str(menus.actionName[choice][1])+"       ")[:11], term.bgwhite, term.white, term.bold)
                term.write(" "+str(menus.actionName[choice][3]), term.bgwhite, term.blue)
                term.clearLineFromPos()
                term.writeLine("", term.bgwhite, term.blue)
            term.clearLineFromPos()
            term.writeLine("", term.bgwhite, term.blue)
            term.clearLineFromPos()
            term.writeLine("", term.bgwhite, term.blue)
            term.clearLineFromPos()
            term.writeLine("", term.bgwhite, term.blue)
            display_pause = prec_pause
    except KeyboardInterrupt:
        T_Pump.stopAction()
        break
    except:
        traceback.print_exc()
        time.sleep(5)
## End of main loop.

# Stops Web Server...
webServerThread.stop()
time.sleep(0.1)

# Close equipments...
change = dumpValve.setWait(1.0)  # better to keep dumping valve open
term.write ("Vanne ", term.blue, term.bgwhite)
term.writeLine ("OUVERTE vers l'égout.", term.green, term.bold, term.bgwhite)
T_DAC.close()
term.write ("Chauffe ", term.blue, term.bgwhite)
term.writeLine ("éteinte.", term.green, term.bold, term.bgwhite)
time.sleep(0.1)

if T_PumpReading:
    T_PumpReading.close()
    time.sleep(0.1)
T_Pump.close()
term.write ("Pompe ", term.blue, term.bgwhite)
term.writeLine ("éteinte.", term.green, term.bold, term.bgwhite)

hotTapSolenoid.close()
#coldTapSolenoid.close()

hardConf.close()

with open(DIR_DATA_CSV + fileName+".csv", "r") as data_file:
    term.write("Données stockées dans ",term.blue, term.bgwhite)
    term.writeLine(os.path.realpath(data_file.name),term.red,term.bold, term.bgwhite)
    data_file.close()

if WebExit: # Exit asked from web: shutdown the computer
    #To make the following call possible, please configure in /etc/sudoer file:
    #    username ALL = NOPASSWD: /sbin/shutdown
    #    %admin  ALL = NOPASSWD: /sbin/shutdown
    print ("shutdown...")
    subprocess.call(['/sbin/shutdown', '-h', 'now'])
    print ("Done!")
    #os.system('systemctl poweroff')  demande aussi une authentication...

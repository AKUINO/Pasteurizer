#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
#TODO:
le compteur de remplissage des seaux d’entrée/sortie n’est pas juste: lors d’un flush, le décompte du seau de sortie diminue lorsque la pompe tourne à l’envers hors il devrait continuer à augmenter car de l’eau arrive toujours en provenance de la conduite.

lors du cyclage d’un nettoyage, le schéma montre comme si le seau se vidait et se remplissait alors que les tuyaux d’entrée/sortie sont dans le même seau
dans le seau d’entrée, à la place d’indiquer la formule complète, par exemple 19,8-5,3=14,5L, indiquer juste ce qui est enlever du seau, -5,3L.

si on lance par exemple un pasteurisation et qu’on l’arrête directement car fausse manipulation, le pasteurisateur croit quand même que l’action a été faite
- Seau de désinfectant: 15L noir (couvercle)
- Seau de détergent: 15L bleu (couvercle)
- Seau de récup "A": 20L blanc
- Seau de récup "B": 15L blanc

- Rinçages: suivre le nombre et permettre de choisir une configuration de réutilisation de seaux
    Désinfection:
        Si pas d'utilisation pendant plus qu'un jour, SIMPLE FLUSH:
             Entrée+Sortie=seau de recup "A" -- remplir la machine d'eau du robinet (5L), faire un flush d'eau potable (5L) (FLUSH doit-il faire 10L si le circuit est vide?)
        Entrée+Sortie=seau de désinfectant -- lancer la désinfection qui va au besoin remplir la machine (5L)
           puis faire un flush (5L) pour pouvoir diluer le désinfectant.
           Cyclage, délai d'action de 15 minutes (paramètre?),
               flush d'évacuation (5L) donc 10L dans le seau de désinfectant
        DOUBLE FLUSH:
            Entrée+Sortie=seau de recup "A" -- faire deux flush (10L)  (donc total 10 à 15L dans le seau de recup "A")
    Pasteurisation: CHAUFFE (le circuit doit être rempli d'eau)
        Entrée=lait cru
        Sortie=seau de recup "B" = 5L d'eau qui sorte au début corrompue par du lait  (donc total 10L dans le seau de recup "B")
        Sortie = lait pasteurisé
        Entrée = seau de recup "B", faire la pousse à l'eau (rajouter un ou deux litres d'eau dans le seau B au besoin)
        ASPI DOUBLE+DOUBLE FLUSH:
            Entrée = au dessus de l'égout (rejet), Sortie(aspirée!)=seau de recup "A" -- faire deux flush "récupérant" INVERSE, jeter la fin du seau "A" (rincer des seaux sales)
                 Puis deux flush d'eau potable (10L) + VIDER donc 10L restent récupérables dans le seau "A"
    Nettoyage caustique:
        Entrée+Sortie = seau de caustique -- lancer le nettoyage qui va remplir (5L) puis faire un flush (5L) pour pouvoir diluer le détergent.
           Cyclage avec chauffe, plateau de 15 minutes
               flush d'évacuation (5L) donc 10L dans le seau de détergent
        ASPI DOUBLE+DOUBLE FLUSH:
            Sortie = seau de recup "A", faire deux flush INVERSE (donc Entrée au dessus de l'égout), jeter la fin du seau "A" (rincer des seaux sales)
                 Puis deux flush d'eau potable (10L) + VIDER donc 10L restent récupérables dans le seau "A"
- Prendre la durée de pasteurisation à la température de pasteurisation pour calculer un ratio supplémentaire de réduction de la souche bactérienne retenue à cette température là.
    Utiliser ce ratio pour toutes les souches. A TESTER !
- Ne jamais accélérer (décélérer) quand on n'est pas en pasteurisation (quand ce n'est pas une régulation sur la courbe de survie d'un microbe)
- Arrêter de chauffer quand la pompe tourne déjà bien vite
- Ne pas aller trop vite quand on pousse l'eau ou qu'on pousse à l'eau.
- Intégrer les Mélanges de produits laitiers congelés, lait de poule :
    soumettre à une température de 80°C pendant 25 secondes ou à une température de 83°C pendant 15 secondes
- Vider le tuyau avant ou après un rinçage pour rendre le suivant plus efficace
- Démarrer lentement une pasteurisation.
- Pousse-à-l'eau : vérifier le paramétrage en relation avec la nouvelle régulation
- Lavage: assurer un minimum de 50 en entrée et non de "cuve - 13".   Pour celà, la chauffe de la cuve pourrait être OK pour "bouger" dès 50°C et pour arrêter de chauffer 20°C (paramétrable?) plus haut (gradient nettoyage).
      Pour une pasteurisation, ce pourrait être idem avec un gradient de 3°C (paramétré)
   ATTENTION: CHANGEMENT a moitié fait.
"""
import socket
import sys
import os
import signal
import argparse
import json
import time
import web # pip install web.py
from datetime import datetime
from enum import Enum

import tty
import termios
import subprocess
import traceback

import ml  # Not unused !!!
import datafiles

import pyownet
import term  # pip install py-term
import threading

import hardConf
import report
import sensor
#import pump
import pump_pwm
import cohort
import Heating_Profile
import Dt_line

from thermistor import Thermistor
from pressure import Pressure
from solenoid import Solenoid
from LED import LED
from button import button, ThreadButtons
from sensor import Sensor
from valve import Valve
from menus import Menus
from state import State
from report import Report

from TimeTrigger import TimeTrigger

global render, _lock_socket

DEBUG = True

KEY_ADMIN = "user@akuino.net"  # Omnipotent user
PWD = "past0.NET"

HEAT_EXCHANGER = True

display_pause = False
lines = 25

WebExit = False


def isnull(v, n):
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
    except:
        traceback.print_exc()
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

    global display_pause,lines,columns

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
RedConfirmationDelay = 4.5 # secondes pour confirmer un arrêt ou un shutdown

YellowLED = None
GreenLED = None
RedButton = None
YellowButton = None
GreenButton = None
EmergencyButton = None

#configuration of output pins
if hardConf.Out_Buzzer:
    Buzzer = LED('buzzer',hardConf.Out_Buzzer)
    Buzzer.on()
if hardConf.Out_Red:
    RedLED = LED('red',hardConf.Out_Red) #BCM=24
if hardConf.Out_Yellow:
    YellowLED = LED('yellow',hardConf.Out_Yellow) #BCM=24
if hardConf.Out_Green:
    GreenLED = LED('green',hardConf.Out_Green) #BCM=23

#configuration of input pins
if hardConf.In_Red:
    RedButton = button('red',hardConf.In_Red, RedLED)
if hardConf.In_Yellow:
    YellowButton = button('yellow',hardConf.In_Yellow, YellowLED)
if hardConf.In_Green:
    GreenButton = button('green',hardConf.In_Green, GreenLED)
if hardConf.In_Emergency:
    EmergencyButton = button('emergency',hardConf.In_Emergency)

#BATH_TUBE = 4.6 # degrees Celsius. Margin between temperature in bath and temperature wished in the tube

CLEAN_TIME = 900.0 #seconds= 15 minutes. Was 1800 but now we wait for input heating before beginning
ACID_TIME = 600.0 #seconds= 10 minutes. Was 900 but now we wait for input heating before beginning
DISINF_PAUSE_TIME = 900.0 #seconds= 15 minutes, pause to leave disinfectant to act
STAY_CLEAN_TIME = 2*3600 #seconds = 2 hours

DEFAULT_FORCING_TIME = 30 #seconds. Each time the user forces pumping forward, normal operation resumes after this delay

HYSTERESIS = 0.2 # degrees below / over setpoint to open / close heating

#FLOOD_TIME = 60.0 # 90 seconds of hot water tap flushing (when a pump is in the way. 60 if not) to FILL an EMPTY machine
#floodLitersMinute = 3.5 # 4.0 si pas de pompe dans le chemin; 3 sinon    DEPEND DE LA PRESSION, PAS UTILISABLE
FLOOD_PER_MINUTE = 4.0 # liters in a one minute flood from the tap (also used with water coming from a bucket)

TANK_NOT_FILLED = 1.5 # If heating time remaining is decreasing more than expected (ratio above 1.3 and not 3), the tank may not be filled correctly...

TANK_EMPTY_LIMIT = 60 #seconds. If heating time has not diminished in this delay, the heating tank may be empty...

PUMP_LOOP_DELAY = 0.2

menus = Menus.singleton
menus.options =  {'G':['G',ml.T("Gradient°","Gradient°","Gradient°") \
                            ,ml.T("Gradient de température","Temperature Gradient","Gradient van Temperatuur") \
                            ,3.0,3.0,"°C",False,7,0.1,"number"],  # Gradient de Température
                  #'g':['g',ml.T("Produit Gras","Fatty Product","Vet Product") \
                  #    ,ml.T("Nécessite de la soude(1) Pas toujours(0)","Needs Soda Cleaning(1) Not always(0)","Soda-reiniging nodig(1) Niet altijd(0)") \
                  #    ,1,1,"-",False,1,1,'range'], # Faux=0, 1=Vrai
                  # 'F':['F',ml.T("Profil Bact.","Profile Bact.","Profiel Bact.") \
                  #     ,ml.T("Courbe de réduction des bactéries","Bacteria reduction curve","Bacterie reductiecurve") \
                  #     ,'L','L',"",True,None,None,"text"], # Gradient de Température
                  'P':['P',ml.T("Pasteurisation°","Pasteurization°","Pasteurisatie°") \
                            ,ml.T("Température de pasteurisation","Pasteurisation Temperature","Pasteurisatie Temperatuur") \
                            ,72.0,72.0,"°C",False,90,0.1,"number"],  # Température normale de pasteurisation
                  'w':['w',ml.T("Pause maximale","Max Pause","Max Pauze") \
                         ,ml.T("Temps d'arrêt maximum autorisé","Maximum process stop duration","Maximaal toegestane uitvaltijd") \
                         ,STAY_CLEAN_TIME,STAY_CLEAN_TIME,"hh:mm",False,3600*2,600,"time"],  # Durée où un tuyau propre le reste sans rinçage (le double avant de tout re-nettoyer)
                  'R':['R',ml.T("Rinçage°","Rinse°","Spoelen°") \
                            ,ml.T("Température de rinçage","Rinse Temperature","Spoelen Temperatuur") \
                            ,25.0,25.0,"°C",False,90,0.1,"number"],  # Température du Bassin pour le prélavage
                  'r':['r',ml.T("Rinçage\"","Rinse\"","Spoelen\"") \
                            ,ml.T("Durée du dernier Rinçage","Last Rinse duration","Laatste spoelduur") \
                            ,0.0,60.0,'\"',False,300,1,"number",60],  # Volume du dernier flush pour calcul du Temps d'admission de l'eau courante (TOTAL_VOL à mettre par défaut)
                  'u':['u',ml.T("Rinçage(L)","Rinse(L)","Spoelen(L)") \
                            ,ml.T("Volume du dernier Rinçage","Last Rinse Volume","Laatste spoelvolume") \
                            ,0.0,0.0,'L',False,20,0.01,"number",4.0],  # Volume du dernier flush pour calcul du Temps d'admission de l'eau courante (TOTAL_VOL à mettre par défaut)
                  's':['s',ml.T("Seau pour l'Eau","Bucket for Water","Emmer voor water\"") \
                         ,ml.T("Eau courante(0) ou amenée dans un seau(1)","Running water(0) or brought in a bucket(1)","Stromend water(0) of gebracht in een emmer(1)") \
                         ,0,1,"-",False,1,1,'range'],  # Faux=0, 1=Vrai
                  'C':['C',ml.T("net.Caustique°","Caustic cleaning°","Bijtende schoonmaak°") \
                            ,ml.T("Température de nettoyage","Cleaning Temperature","Schoonmaak Temperatuur") \
                            ,50.0,50.0,"°C",False,60,0.1,"number"],  # Température pour un passage au détergent
                  'c':['c',ml.T("net.Caustique\"","Caustic cleaning\"","Bijtende schoonmaak\"") \
                            ,ml.T("Durée de nettoyage","Cleaning Duration","Schoonmaak Tijd") \
                            ,CLEAN_TIME,CLEAN_TIME,"hh:mm",False,3600*2,60,"time"],
                  'D': ['D', ml.T("Désinfection°""Disinfection°", "Desinfectie°") \
                          , ml.T("Température de désinfection", "Disinfection Temperature", "Desinfectie Temperatuur") \
                          , 25.0, 25.0, "°C", False, 30, 0.1, "number"],  # Température normale de désinfection vinaigre + peroxyde
                    'd': ['d', ml.T("Désinfection \"", "Disinfection \"", "Desinfectie \"") \
                          , ml.T("Durée de désinfection", "Disinfection Duration", "Desinfectie Tijd") \
                          , DISINF_PAUSE_TIME, DISINF_PAUSE_TIME, "hh:mm", False, 3600, 60, "time"],  # Temps d'action pour un traitement à l'acide ou au percarbonate de soude
                    'A':['A',ml.T("net.Acide°""Acidic cleaning°","Zuur schoonmaak°") \
                            ,ml.T("Température de nettoyage acide","Acidic cleaning Temperature","Zuur schoomaak Temperatuur") \
                            ,40.0,40.0,"°C",False,60,0.1,"number"],  # Température pour un traitement à l'acide ou au percarbonate de soude
                    'a':['a', ml.T("net.Acide\"","Acidic cleaning\"","Zuur schoonmaak\"") \
                            , ml.T("Durée de nettoyage acide","Acidic cleaning Duration","Zuur schoomaak Tijd") \
                            , ACID_TIME, ACID_TIME, "hh:mm", False, 3600 * 2, 60, "time"],  # Température pour un traitement à l'acide ou au percarbonate de soude
                    'M':['M',ml.T("Minimum","Minimum","Minimum") \
                            ,ml.T("Durée minimale de pasteurisation","Minimum pasteurization time","Minimale pasteurisatietijd") \
                            ,12.0,12.0,'"',False,120,1,"number"],  # Durée minimale de pasteurisation
                  # 'T':['T',ml.T("Tempérisation Max°","Tempering Max°","Temperen Max°") \
                  # ,ml.T("Température d'ajout d'eau de refroidissement","Cooling water addition temperature","Koelwatertoevoegings Temperatuur") \
                  # ,0.0,0.0,"°C",True,90.0,0.1], # Température à laquelle on ajoute de l'eau de refroidissement,ZeroIsNone=True
                  # 't':['t',ml.T("Tempérisation Min°","Tempering Min°","Temperen Min°") \
                  # ,ml.T("Réchauffement à la sortie","Output Heating","Opwarmen") \
                  # ,18.0,18.0,"°C",True,90.0,0.1], # Température à laquelle on chauffe la cuve de sortie,ZeroIsNone=True
                  # 'K':['K',ml.T("Quantité Froid","Quantity Cold","Koel Aantal") \
                  # ,ml.T("Quantité d'eau de refroidissement","Cooling Water Quantity","Koelwater Aantal") \
                  # ,midTemperTank,midTemperTank,"L",False,19.9,0.1], # Quantité d'eau froide à mettre dans le bassin de refroidissement
                  # 'Q':['Q',ml.T("Quantité","Quantity","Aantal") \
                  # ,ml.T("Quantité de lait à entrer","Amount of milk to input","Aantal melk voor invoor") \
                  #  ,0.0,0.0,"L",True,9999.9,0.1,"number"], # Quantité de lait à traiter,ZeroIsNone=True
                  'H':['H',ml.T("Démarrage","Start","Start") \
                            ,ml.T("Heure de démarrage","Start Time","Starttijd") \
                            ,0.0,0.0,"hh:mm",True,84000,600,"time"],  # Hour.minutes (as a floating number, by 10 minutes),ZeroIsNone=True
                  'E':['E',ml.T("Amont(mL)","Upstream(mL)","StroomOPwaarts(mL)") \
                         ,ml.T("Volume des tuyaux en amont(cm*0,7854*d²)","Upstream Pipes Volume(cm*0,7854*d²)","StroomOPwaarts leidingvolume(cm*0,7854*d²)") \
                         ,0.0,0.0,'mL',False,2000,1,"number"],  # Volume des tuyaux en entrée du pasteurisateur
                  'S':['S',ml.T("Aval(mL)","Downstream(mL)","StroomAFwaarts(mL)") \
                         ,ml.T("Volume des tuyaux en aval(cm*0,7854*d²)","Downstream Pipes Volume(cm*0,7854*d²)","StroomAFwaarts leidingvolume(cm*0,7854*d²)") \
                         ,0.0,0.0,'mL',False,15000,1,"number"],  # Volume des tuyaux en sortie du pasteurisateur
                  'z':['z',ml.T("Pré-configuration","Pre-configuration","Pre-configuratie") \
                         ,ml.T("Code de pré-configuration","Pre-configuration code","Pre-configuratiecode") \
                         ,'L','L',"hh:mm",True,None,None,"text"]}
                    # 'Z':['Z',ml.T("Défaut","Default","Standaardwaarden") \
                    #         ,ml.T("Retour aux valeurs par défaut","Back to default values","Terug naar standaardwaarden")] }
menus.sortedOptions = "FPMGwDdHRrusCcAaZES" #T
menus.cleanOptions = "PMGH" #TtK
menus.dirtyOptions = "RrusCcAawDdHES" #Cc

menus.loadCurrent()

reportPasteur = Report(menus) # Initialized when initializing the pump...

trigger_w = TimeTrigger('w',menus)
#(options['P'][3] + BATH_TUBE) = 75.0  # Température du Bassin de chauffe
##reject = 71.7 # Température minimum de pasteurisation

kCalWatt = 1.16 # watts per kilo calories

WATT_LOSS = 10 # watts lost per 1°C difference with room temperature
# MITIG_POWER = 1500.0 # watts per hour (puissance du bac de mitigation)
ROOM_TEMP = 20.0 # degrees: should be measured...

PUMP_SLOWDOWN = 1.0 # Slowing factor from speed calculated by temperature difference

# durationDump = Time to open or close the dump valve: look at Valve module...

periodicity = 3 # 3 seconds intervall between cohort data
depth = 100 # 100 x 3 seconds of data kept
cohorts = cohort.Cohort(periodicity,depth)

calibrating = False
temp_ref_calib = []

def manage_cmdline_arguments():
    parser = argparse.ArgumentParser(description='AKUINO: Pasteurisateur accessible')
    # Est interprété directement par WebPY
    parser.add_argument('port', type=int, help='Port number of the internal \
                                                web server')
    return parser.parse_args()

# restart_program()
args = manage_cmdline_arguments()

if hardConf.operatingSystem == 'Linux':
    _lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) # pour Linux
    try:
        _lock_socket.bind('\0AKUINOpast')
        print('Socket AKUINOpast now locked')
    except socket.error:
        print('AKUINOpast lock exists')
        sys.exit()
else: # Other operating systems like MAC
    import socklocks
    try:
        _lock_socket = socklocks.SocketLock('AKUINOpast')
        print('Socket AKUINOpast now locked for '+hardConf.operatingSystem)
    except socket.error:
        print('AKUINOpast lock exists for '+hardConf.operatingSystem)
        sys.exit()

datafiles.goto_application_root()

PI = 3.141592 # Yes, we run on a Raspberry !

# mL Volume of a tube based on ID(mm) and length(mm)
def vol_tube(internal_diameter,long): # retourne le volume d'un cylindre sur base de son diamètre et de sa longeur en mm, en cm3 (=mL)
    rad = internal_diameter/2.0
    return PI*rad*rad*long/1000.0 # cubic mm to cubic cm (mL)

# mL Volume of a tube based on ID(mm) of outer tube, OD of inner tube and length(mm)
def vol_outer_tube(OD_inner,ID_outer,long): # retourne le volume d'un cylindre creux(pour volume du tube externe de l'échangeur)
    return vol_tube(ID_outer,long) - vol_tube(OD_inner,long)

# mL Volume of a coil based on ID(mm) and coil middle diam(mm) and number of spires
def vol_coil(diamT,diamS,nbS):
    long = diamS*PI*nbS
    return vol_tube(diamT,long)

def mL_L(mL): # milli Liters to Liters...
    return mL / 1000.0

def L_mL(L): #Liters to milli Liters...
    return L * 1000.0

tank = mL_L(hardConf.vol_heating)

start_volume = 0.0
total_volume = 0.0
safe_total_volume = 0.0
dry_volume = 0.0

def init_volumes():

    global menus, cohorts, start_volume, total_volume, safe_total_volume, dry_volume
    # Volumes for the different parts of the pasteurizer circuit
    #hardConf.holding_volume = vol_tube(9.5,hardConf.holding_length) # = 625mL = 15 seconds for 150L / hour. Should be 833mL for 200L 11757

    if hardConf.tubing == "horizontal":
        #Amorçage=2330mL, Pasteurisation=625mL, Total=3587mL (new config system)
        #exchanger_tube = vol_tube(8,8*1800)
        up_to_solenoid = vol_tube(8, 1800) + vol_tube(8, 600)
        heating_tube = vol_tube(10.5,500)+vol_coil(10.5,220,18)+vol_tube(8,200)+vol_coil(7,250,20)
        up_to_thermistor = 2330.0
        total_tubing = 3587.0
    else:
        #Amorçage=3031mL, Pasteurisation=625mL, Total=4989mL
        #exchanger_tube = 2.0*712.6 #mL
        up_to_solenoid = vol_tube(8, 2000) + vol_tube(9.5, 577) # Calculated: 317
        heating_tube = vol_tube(9.5,500)+5127-3860 #1302   1444-336=1108  Calculated: 1407
        up_to_thermistor = 3031.0 # Calculated: 2706
        total_tubing = 4989.0 # Calculated: 5215
    up_to_heating_tank = up_to_thermistor - heating_tube # Calculated: 1259

    if hardConf.vol_intake:
        up_to_solenoid = hardConf.vol_intake
    if hardConf.vol_input:
        up_to_heating_tank = hardConf.vol_input
    if hardConf.vol_warranty:
        up_to_thermistor = hardConf.vol_warranty
    if hardConf.vol_total:
        total_tubing = hardConf.vol_total

    up_to_extra = total_tubing
    if hardConf.vol_extra:
        up_to_extra = hardConf.vol_extra

    up_to_solenoid = up_to_solenoid - 100 + menus.val('E')
    up_to_heating_tank = up_to_heating_tank - 100 + menus.val('E')
    up_to_thermistor = up_to_thermistor - 100 + menus.val('E')
    up_to_extra = up_to_extra - 200 + menus.val('E') + menus.val('S')
    total_tubing = total_tubing - 200 + menus.val('E') + menus.val('S')

    cohorts.sequence = [ # Tubing and Sensor Sequence of the Pasteurizer
                        [up_to_solenoid, 'intake'], # apres la pompe
                        [up_to_heating_tank - up_to_solenoid,'input'], #input de la chauffe
                        [up_to_thermistor - up_to_heating_tank, 'warranty'], # Garantie
                        [up_to_extra - up_to_thermistor, 'extra'] ]
    #                    ,[total_tubing - up_to_extra, 'total']] # Sortie TO BE IMPLEMENTED WHEN EXTRA THERMISTOR WILL BE AVAILABLE
    tell_message("Entrée=%dmL, avant Cuve=%dmL, Garantie=%dmL, Sortie=%dmL" % (cohorts.mL('intake'), cohorts.mL('input'), cohorts.mL('warranty'), cohorts.mL('extra')))
    # Parameterized volumes are in Liters and not milliliters...
    start_volume = mL_L(up_to_thermistor) # 1.9L
    total_volume = mL_L(total_tubing) # 3.5L
    safe_total_volume = total_volume - 0.1 #100ml is about the content of the output pipe
    menus.options['u'][Menus.INI] = total_volume # Flush quantity

    dry_volume = total_volume * 1.5 # (air) liters to pump to empty the tubes...

    tell_message("Amorçage=%dmL, Pasteurisation=%dmL : %.1fL/h, Total=%dmL" % (int(up_to_thermistor), int(hardConf.holding_volume), (mL_L(hardConf.holding_volume) / 15.0) * 3600.0, int(total_tubing)))

init_volumes()

#Amorçage=1941mL, Pasteurisation=538mL, Total=3477mL
#Amorçage=2031mL, Pasteurisation=538mL, Total=3676mL
#Amorçage=2034mL, Pasteurisation=325mL, Total=3346mL
#Amorçage=2300mL, Pasteurisation=400mL, Total=3840mL MESURE
#Amorçage=2330mL, Pasteurisation=625mL, Total=3587mL (new config system)
#New exchanger:
#Amorçage=3031mL, Pasteurisation=625mL, Total=4989mL

KICKBACK = 13 # Haw many seconds the pump turns toward input after a flush in order to rinse the input pipe

DILUTE_VOL = 2.0 #L added in the bucket to dilute the cleaning products

#i=input(str(START_VOL*1000.0)+"/"+str(hardConf.holding_volume)+"/"+str(vol_tube(8,400)+vol_coil(8,250,10)+vol_tube(8,2000)))
SHAKE_QTY = mL_L(hardConf.holding_volume) / 4 # liters
SHAKE_TIME = 10.0 # seconds shaking while cleaning, rincing or disinfecting

GRADIENT_FOR_INTAKE = 20.0  # How many degrees do we heat the tank more than the desired temperature just after the pump

class ThreadOneWire(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        try:
            self.owproxy = pyownet.protocol.proxy(host="localhost", port=4304)
        except:
            traceback.print_exc()

    def sensorParam(self,address,param):
        global cohorts
        if address not in cohorts.catalog:
            cohorts.addSensor(address,sensor.Sensor(typeOneWire,address,param))
            cohorts.readCalibration(address)
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

#def vari(adc_channel):
#    moy = t[adc_channel] / n[adc_channel]
#    s = (t2[adc_channel] / n[adc_channel]) - (moy * moy)
#    if s < 0.0:
#        s = - s
#    s = s ** 0.5
#    return ", M=%6.0f, s=%6.1f" % (moy,s)

class ThreadThermistor(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def sensorParam(self,address,param,beta,ohm25, A, B, C):
        global cohorts
        if param and address not in cohorts.catalog:
            new_sensor = Thermistor(address,param)
            if beta:
                new_sensor.bResistance = beta
            if ohm25:
                new_sensor.t25Resistance = ohm25
            if A:
                new_sensor.A = A
            if B:
                new_sensor.B = B
            if C:
                new_sensor.C = C
            cohorts.addSensor(address, new_sensor)
            cohorts.readCalibration(address)
        return cohorts.catalog[address]

    def pressureSensorParam(self,address,param, flag):
        global cohorts
        if param and flag and address not in cohorts.catalog:
            cohorts.addSensor(address,Pressure(address,param,flag))
            cohorts.readCalibration(address)
        return cohorts.catalog[address]

    def run(self):
        global cohorts
        while True:
            try:
                time.sleep(1.0)
                for (address, aSensor) in cohorts.catalog.items():
                    if aSensor.sensorType == Pressure.typeNum:
                        aSensor.get()
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
                       ,ml.T("Entrée et Sortie dans un seau. Récupération?","Inlet and Outlet in the same bucket. Recycling?","Inlaat en uitlaat in dezelfde emmer. Recyclen?") \
                       ,ml.T("Rinçage à l'eau de ville","Rinse with city water","Spoelen met stadswater")], \
               'H':['H',ml.T("Eau pasteurisée","Pasteurized Water","Flush") \
                       ,ml.T("Sortie là où rincer","Outlet where to rince","Uitlaat waar spoelen") \
                       ,ml.T("Pasteuriser de l'eau de ville","Pasteurize city water","Pasteur stadswater")], \
               # 'K':['K',ml.T("eau froide","Kooling","Kool") \
                       # ,ml.T("Spécifier AVANT la Quantité et la Température dans Options","Specify BEFORE Quantity and Temperature in Options","Specificeer VOOR hoeveelheid en temperatuur in Opties") \
                       # ,ml.T("Ajouter de l'eau froide dans la Tempérisation","Add cold water to Mitigation","Voeg koud water toe aan Mitigation")],
               'V':['V',ml.T("Vider","Purge","Purge") \
                       ,ml.T("Entrée hors de l'eau, Vidange...","Inlet out of water, Drain ...","Inlaat uit het water, Afvoer ...") \
                       ,ml.T("Vidange maximale des tuyaux","Maximum emptying of pipes","Maximale lediging van leidingen")],
               #'A':['A',ml.T("Amorc.","initiAte","Aanzet.") \
               #        ,ml.T("Entrée et Sortie connectés et dans un seau, Pré-chauffage...","Inlet and Outlet connected and in a bucket, Pre-heating ...","Input en output aangesloten en in een emmer, Voorverwarmen ...") \
               #        ,ml.T("Amorçage de la Pasteurisation","Initiating Pasteurization","Pasteurisatie initiëren")],
               'B':['B',ml.T("caliB.","caliB.","caliB.") \
                       ,ml.T("Seau d'eau en entrée+sortie","Water Bucket","Water Emmer") \
                       ,ml.T("Calibration","Calibration","Calibratie")],
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
               'R':['R',ml.T("Rinçage avec Réemploi","Rinse with Reuse","Spoelen met Hergebruik") \
                       ,ml.T("Entrée dans le seau de Récupération. Sortie à l'égout","Inlet in the recycling bucket. Outlet over sewer","Inlaat in het opvangemmer. Uitlaat naar riool") \
                       ,ml.T("Rincer à fond le circuit","Rinse the circuit thoroughly","Spoel de leidingen grondig af")],
               'C':['C',ml.T("net.Caustique","Caustic clean","Bijtend Schoon") \
                       ,ml.T("Entrée et Sortie dans un même seau, Ajouter le Détergent...","Inlet and Outlet in a bucket, Add Detergent ...","Inlaat en uitlaat in dezelfde emmer. Wasmiddel toevoegen ...") \
                       ,ml.T("Nettoyer avec un détergent (caustique)","Clean with detergent (caustic)","Reinig met afwasmiddel (bijtend)")],
               'D':['D',ml.T("Désinfection","Disinfct","Desinfect.") \
                       ,ml.T("Entrée et Sortie dans un même seau","Inlet and Outlet in a bucket","Inlaat en uitlaat in dezelfde emmer.") \
                       ,ml.T("Désinfecter avec le produit approprié","Disinfect with sanitizer","Desinfecteren met ontsmettingsmiddel")], \
               'A':['A',ml.T("net.Acide","Acidic clean","Zuur") \
                       ,ml.T("Entrée et Sortie dans un même seau, Ajouter le nettoyant acide...","Inlet and Outlet in the same bucket, Add Acidic cleaner...","Inlaat en uitlaat in dezelfde emmer. Zuur wasmiddel toevoegen ...") \
                       ,ml.T("Désinfecter les tuyaux (acide)","Disinfect pipes (acid)","Desinfecteer leidingen (zuur)")], \
               'S':['S',ml.T("pauSe","pauSe","pause") \
                       ,ml.T("Pause: bouton vert pour redémarrer","Pause: Green button to restart","Groene knop om opnieuw te starten") \
                       ,ml.T("Suspendre ou arrêter l'opération en cours","Suspend or stop the current operation","Onderbreek of stop de huidige bewerking")],
               'O':['O',ml.T("Options","Options","Opties") \
                       ,ml.T("Paramètres de fonctionnement","Operating parameters","Bedrijfsparameters") \
                       ,ml.T("Changement de paramètres","Change of parameters","Wijziging van parameters")],
               'N':['N',ml.T("net.Options","Clng Options","Schoon.Opties") \
                    ,ml.T("Paramètres de Nettoyage","Cleaning parameters","Schoon Bedrijfsparameters") \
                    ,ml.T("Changement de paramètres","Change of parameters","Wijziging van parameters")],
               'Y':['Y',ml.T("Yaourt","Yogurt","Yoghurt") \
                       ,ml.T("Pasteuriser pour Yaourt","Pasteurize for Yogurt","Pasteuriseren voor yoghurt") \
                       ,ml.T("Température pour Yaourt","Temperature for Yogurt","Temperatuur voor yoghurt")],
               'J':['J',ml.T("Jus/Crème","Juice/Cream","Saap/Room") \
                       ,ml.T("Pasteuriser du Jus ou de la Crème","Pasteurize for Juice or cream","Pasteuriseren voor saap of room") \
                       ,ml.T("Température pour Jus ou Crème","Temperature for Juice or cream","Temperatuur voor saap of room")],
               'K':['K',ml.T("Décongelé","Thawed","Ontdooid") \
                       ,ml.T("Pasteuriser prod.décongelés","Pasteurize thawed products","Pasteuriseren ontdooid produc.") \
                       ,ml.T("Température pour décongelés","Temperature for Thawed prod.","Temperatuur voor ontdooid produc.")],
               'L':['L',ml.T("Lait","miLk","meLk") \
                       ,ml.T("Pasteuriser du Lait","Pasteurize for Milk","Pasteuriseren voor melk") \
                       ,ml.T("Température pour Lait","Temperature for Milk","Temperatuur voor melk")],
               'T':['T',ml.T("Therm","Therm","Therm") \
                       ,ml.T("Thermiser","Thermize","Thermis.") \
                       ,ml.T("Température pour Thermiser","Temperature for Thermizing","Temperatuur voor thermisering")],
               'Z':['Z',ml.T("STOP","STOP","STOP") \
                       ,ml.T("Pas d'opération en cours.","No operation in progress.","Er wordt geen bewerking uitgevoerd.") \
                       ,ml.T("Arrêt complet de l'opération en cours","Complete stop of the current operation","Volledige stopzetting van de huidige bewerking")],
               '!':['!',ml.T("Seau fourni","Bucket provided","Emmer voorzien") \
                    ,ml.T("Seau pour fournir l'eau ou le mélange.","Bucket providing water or mix.","Emmer om water of mengsel aan te voeren.") \
                    ,ml.T("Prenez soin d'avoir au moins 7 litres.","You need at least 7 liters.","Zorg dat je minstens 7 liter hebt.")],
               '+':['+',ml.T("Ajouté","Added","Toegevoegd") \
                    ,ml.T("Produit chimique ajouté.","Chemical product added.","Chemisch product toegevoegd.") \
                    ,ml.T("L'opération en cours ne doit plus s'interrompre","Current operation does not have to stop.","Huidige bewerking hoeft niet te stoppen.")],
               '>':['>',ml.T("Forcer>","Force>","Kracht>") \
                    ,ml.T("Avancer","Advance","Vooruit") \
                    #,ml.T("Surmonter une bulle d'air / Augmenter l'eau de lavage","Overcome an air bubble / Increase wash water","Overwin een luchtbel / verhoog het waswater")],
                    ,ml.T("Surmonter une bulle d'air","Overcome an air bubble","Overwin een luchtbel")],
               '_':['_',ml.T("Redémar.","Restart","Herstart") \
                       ,ml.T("Redémarrage de l'opération en cours.","Restart of the current operation.","Herstart van de huidige bewerking.") \
                       ,ml.T("Redémarrer l'opération en cours","Restart the current operation","Herstart de huidige bewerking")]}
menus.sortedActions1 = "PIMERDCAH"
menus.sortedActions2 = "FVOLYJKTZSXB" #K

menus.cleanActions = "LYJKTPIMEHV" #K
menus.dirtyActions = "RFDCAV"
menus.sysActions = "ZX"

menus.operName = { 'HEAT':ml.T('chauffer','heating','verwarm') \
                   ,'PUMP':ml.T('pomper','pump','pomp') \
                   ,'EMPT':ml.T('vider','purge','purge') \
                   ,'TRAK':ml.T('débiter','trace','trace') \
                   ,'SHAK':ml.T('brasser','shake','schud') \
                   ,'REVR':ml.T('reculer','pump back','pomp terug') \
                   ,'FILL':ml.T('remplir','fill','vullen') \
                   ,'FLOO':ml.T('eau courante','running water','lopend water') \
                   ,'RFLO':ml.T('rincer entrée','input rince','invoer rins') \
                   ,'HOTW':ml.T('eau pasteurisée','pasteurized water','gepasteurde water') \
                   ,'PAUS':ml.T('attendre','wait','wacht') \
                   ,'SEAU':ml.T('seau','bucket','emmer') \
                   ,'MESS':ml.T('signaler','message','bericht') \
                   ,'SUBR':ml.T('processer','process','werkwijze') \
                   ,'SUBS':ml.T('procéder','proceed','doorgan') }

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

StateLessActions = "JYLT" # TO BE DUPLICATED in index.js !

# Empty sub state is managed by underlying operations
# Greasy sub state must be set
State('r',ml.T('Propre','Clean','Schoon'),'aqua', \
      [ ('A',['r',['a',None,False]]),('P','p'),('D',['','d','d']),('H',''),('F',''),('V',''),('B',''),('w','o') ] )

State('o',ml.T('Eau','Water','Waser'),'navy', \
      [ ('A',['o',['a',None,False]]),('F',''),('V',''),('B',''),('D',['','d','d']),('H',['','r']),('w','v') ] )

State('v',ml.T('Eau vieille','Old Water','Oude Waser'),'darkcyan', \
      [ ('A',['v',['a',None,False]]),('C',['v',['c',None,False]]),('F',''),('V',''),('B',''),('D',['','d','d']),('w','') ] )

State('c',ml.T('Soude','Soda','Natrium'),'blue', \
      [ ('R',['','r']),('F',['','r']),('V',''),('w','') ] )

State('a',ml.T('Acide','Acid','Zuur'),'red', \
      [ ('R',['','r']),('F',['','r']),('V',''),('w','') ] )

State('d',ml.T('Désinfectant','Sanitizer','ontsmettingsmiddel'),'fuchsia', \
      [ ('F',['','r']),('V',''),('w','') ] )

#State('p',ml.T('Produit Gras','Greasy Product','Vet Product'), \
#    [ ('I',[['',None,True]]),('M',[['',None,True]]),('E','e'),     ('C',['e','e',['c',None,False]]),('F','e'),('V','') ]
#    , [False,True],[True] )
State('p',ml.T('Produit','Product','Product'),'orange', \
      [ ('I',''),('M',''),('E',''),('R',['','e']),('F',['','e']),('V','') ] )

#State('e',ml.T('Eau+Produit Gras','Water+Greasy Product','Water+Vet Product'), \
#      [                                 ('C',['e','e',['c',None,False]]),('P','p'),('F',''),('V',''),('w','s') ]
#      , [False,True],[True] )
State('e',ml.T('Eau+Produit','Water+Product','Water+Product'),'darkorange', \
      [ ('C',['e',['c',None,False]]),('P','p'),('R',''),('F',''),('V',''),('B',''),('w','s') ] )

#State('s',ml.T('Sale+Gras','Dirty+Greasy','Vies+Vet'), \
#    [ ('C',['s','s',['c',None,False]]), ('F',''),('V',''),('w','') ]
#    , [False,True],[True])
State('s',ml.T('Sale','Dirty','Vies'),'brown', \
      [ ('C',['s','s',['c',None,False]]), ('R',''),('F',''),('V',''),('B',''),('w','') ] )

State('?','...','black', \
      [ ('A',['a']),('C',['c']),('D',['d']), ('H','o'),('R','o'),('F','o'),('V','v'),('w','v'),('M','p'),('E','e'),('P','p'),('I','p'),['Z',''],('B','o'), ] )


def menu_confirm(choice,delay=None):
    global display_pause, lines
    prec_disp = display_pause
    display_pause = True
    time.sleep(0.05)
    term.pos(lines-2,1)
    choice = choice.upper()
    term.write(str(menus.actionName[choice][1]), term.bgwhite, term.white, term.bold)
    term.write(": "+str(menus.actionName[choice][Menus.VAL]), term.bgwhite, term.yellow, term.bold)
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
hotTapSolenoid = None # initialized further below

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
            term.write(str(menus.val(choice))+(" L" if choice in ['K','Q'] else (" sec." if choice == 'M' else "°C")), term.bgwhite, term.yellow)
        term.write(" "+str(menus.options[choice][2]), term.bgwhite, term.blue)
        if len(menus.options[choice]) > 3:
            term.write(" ("+str(menus.ini(choice))+")", term.bgwhite, term.blue)
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
            if conf == 'Z':
                for choice in menus.options:
                    if len(menus.options[choice]) > 3:
                        menus.options[choice][Menus.VAL] = menus.options[choice][Menus.INI]
                term.write(menus.options[conf][2], term.bgwhite, term.green,term.bold)
                term.clearLineFromPos()
                term.writeLine("", term.bgwhite, term.blue)
                menus.save()
            elif conf in menus.options.keys():
                val = input(term.format(str(menus.options[conf][2])+"? ", term.bgwhite, term.white, term.bold))
                try:
                    val = float(val)
                    menus.store(conf,val)
                    menus.save()
                except:
                    pass
            break
    reloadPasteurizationSpeed()
    display_pause = prec_disp

# returns clock time formatted as a floating number h.m
def floating_time(some_time):
    return float(some_time.strftime("%H.%M"))

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
        self.refpoint = None
        #self.setpoint2 = None
        #self.coldpoint = None
        self.T_Pump = None
        self.totalWatts = 0.0
        self.totalWatts2 = 0.0
        self.currLog = None
        self.empty_tank = False

    def set_temp(self,setpoint=None, refpoint=None):
        if refpoint:
            self.refpoint = float(refpoint)
        else:
            self.refpoint = None
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

        global cohorts, display_pause,tank,ROOM_TEMP, lines, columns

        self.running = True
        lastLoop = time.perf_counter()
        lastWatt = 0
        prec_heating = None
        some_heating = False
        has_heated = False
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
                    # elif wattHour >= hardConf.power_heating:
                        # wattHour = hardConf.power_heating

                if self.setpoint and cohorts.catalog['heating'].value:
                    currHeat = int(self.dacSetting.value)
                    #print("%d %f / %f" % (currHeat, cohorts.catalog['heating'].value , self.setpoint) )
                    heating = cohorts.getCalibratedValue('heating')
                    if currHeat > 0: # ON
                        if self.T_Pump.pasteurizationOverSpeed:
                            wattHour = heating < (self.refpoint+HYSTERESIS)
                        elif heating < (self.setpoint+HYSTERESIS):
                            wattHour = True
                    else: # Off
                        if self.T_Pump.pasteurizationOverSpeed:
                            wattHour = heating < (self.refpoint-HYSTERESIS)
                        elif heating < (self.setpoint-HYSTERESIS):
                            wattHour = True

                    if wattHour and not self.empty_tank:
                        self.dacSetting.set(1)
                        self.totalWatts += (hardConf.power_heating/3600.0 * delay)
                        if not lastWatt or self.T_Pump.pump.speed != 0.0:
                            lastWatt = now
                            prec_heating = heating
                            some_heating = False
                        else:
                            if heating > (prec_heating + 0.3):
                                has_heated = True
                            if heating > (prec_heating + 0.1):
                                some_heating = True
                            if (now - lastWatt) > TANK_EMPTY_LIMIT:
                                if not has_heated and some_heating:
                                    self.empty_tank = True
                                    print("EMPTY TANK, stop heating!")
                                    self.dacSetting.set(0)
                                else:
                                    lastWatt = now
                                    prec_heating = heating
                                    some_heating = False
                    else:
                        self.dacSetting.set(0)
                        lastWatt = 0
                        prec_heating = None
                        some_heating = False
                else:
                    self.dacSetting.set(0)
                    lastWatt = 0
                    prec_heating = None
                    some_heating = False
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
                (durationRemaining, warning) = self.T_Pump.durationRemaining(nowT)
                quantityRemaining = self.T_Pump.quantityRemaining()
                try:
                    with open(datafiles.csvfile(datafiles.logfile), "a") as log_file:
                        log_file.write("%d\t%s%s%s\t%s\t%s\t%d\t%.3f\t%.2f\t%.2f\t%.2f\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"
                                    % (int(nowT), \
                                       State.current.letter if State.current else '', \
                                       'V' if State.empty else 'W', \
                                       'G' if State.greasy else 'J', \
                                       self.T_Pump.currAction, \
                                       self.T_Pump.currOperation.acronym if self.T_Pump.currOperation else "", \
                                       durationRemaining, \
                                       quantityRemaining, \
                                       self.totalWatts, \
                                       self.T_Pump.pump.volume(), \
                                       self.T_Pump.pump.liters(), \
                                       1 if self.T_Pump.paused else 0, \
                                       #cohorts.val('extra'), \
                                       cohorts.val('input'), \
                                       cohorts.val('warranty'), \
                                       cohorts.val('intake'), \
                                       cohorts.catalog['DAC1'].val(default='0'), \
                                       cohorts.val('heating'), \
                                       cohorts.val('press' if hardConf.inputPressure else 'rmeter') , \
                                       self.T_Pump.level1, \
                                       self.T_Pump.level2 ) )
                                       #self.totalWatts2, \
                                       #cohorts.val('temper'),
                                       #cohorts.catalog['DAC2'].val(), \
                                       #cohorts.catalog['sp9b'].value
                                       #cohorts.catalog['intake'].value, batt
                except:
                    traceback.print_exc()

                if not display_pause:
                    time.sleep(0.01)
                    (lines, columns) = termSize()
                    term.pos(lines,1)
                    term.writeLine("",term.bgwhite) # scroll the whole display by one line
                    term.pos(lines-4,1)
                    term.write("%2d" % (int(nowT) % 60), term.white, term.bold, term.bgwhite)
                    term.write(self.T_Pump.currOperation.acronym[3:4] if self.T_Pump.currOperation else " ",term.blue,term.bgwhite)
                    cohorts.catalog[self.T_Pump.pump.address].display() # Pompe
                    #cohorts.display(term,'extra',format=" %5.1f° ") #Echgeur
                    cohorts.display(term,'input', format_param=" %5.1f° ") # Entrée de la Chauffe
                    cohorts.display(term,'warranty', format_param=" %5.1f° ") # Garant
                    cohorts.display(term,'intake', format_param=" %5.1f° ") # Garant
                    term.write(' %1d ' % int(isnull(cohorts.catalog['DAC1'].value,0)),term.black,term.bgwhite) # Watts #+isnull(cohorts.catalog['DAC2'].value,0)
                    cohorts.display(term,'heating', format_param=" %5.1f° ") # Bassin
                    #cohorts.display(term,'temper',format=" %5.1f° ") # Bassin de tempérisation
                    #cohorts.catalog['sp9b'].display() # Garant
                    #cohorts.catalog['intake'].display() # Sortie
                    term.write(' %4d"  ' % durationRemaining if durationRemaining > 0 else \
                                '%5dmL ' % int(L_mL(quantityRemaining)) if quantityRemaining != 0.0 else "      ", \
                               term.white, term.bold, term.bgwhite)
                    term.writeLine("!" if warning else "",term.bgwhite)

                    term.pos(lines-3,1)
                    term.clearLineFromPos()
                    term.writeLine("     Pompe   Entrée  Garant. FinCh. Chau Bassin  Encore ",term.blue,term.bgwhite) # scroll the whole display by one line

                    term.pos(1,1) # rewrite the top line (which changes all the time anyway)
                    term.write(menus.actionName[self.T_Pump.currAction][1],term.blue,term.bgwhite)
                    if self.T_Pump.currOperation:
                        term.write(" "+self.T_Pump.currOperation.acronym,term.blue,term.bgwhite)
                    term.write(" %dmL " % (L_mL(self.T_Pump.pump.volume())),term.bold,term.bgwhite, term.red if self.T_Pump.paused else term.yellow)
                    term.write(datetime.fromtimestamp(nowT).strftime("%Y-%m-%d %H:%M:%S"),term.black,term.bgwhite)
                    term.write(" %dWh" % (self.totalWatts+self.totalWatts2),term.red,term.bgwhite)
                    if self.setpoint:
                        term.write(f" {self.setpoint:0.1f}°C", term.black, term.bgwhite)
                    #if self.setpoint2:
                    #    term.write("*",term.red,term.bgwhite)

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
        self.dacSetting.close()
        time.sleep(0.1)
        #self.dacSetting2.close()

def format_time(seconds):
    if seconds == 0:
        return ""
    else:
        return '%02d:%02d:%02d' % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)

# Pump speed types
NUL_SPEED = 0
MIN_SPEED = -1
OPT_SPEED = -2
HALF_SPEED = -3
MAX_SPEED = -4

class Operation(object):

    global menus,lines,columns, hotTapSolenoid, optimal_speed

    def __init__(self, acronym, typeOp, sensor1=None, sensor2=None, ref=None, ref2=None, base_speed=None, min_speed=None, qty=None, shake_qty=None, \
                 duration=None, subSequence = None, dump=False, inject=None, message=None, pasteurizing=0, programmable=False, waitAdd=False, \
                 bin = None, bout = None, kbin = None, kbout = None, qbin=None, qbout=None):
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
        self.waitAdd = waitAdd
        self.pasteurizing = pasteurizing # signals we are pasteurizing. 2=new product (starts new pasteurisation report)
        self.programmable = programmable
        self.bin = bin
        self.bout = bout
        self.kbin = kbin
        self.kbout = kbout
        self.qbin = qbin
        self.qbout = qbout

    def tempRef(self): # Current heating temperature along what is set in options
        if not self.ref: # do not heat !
            return 0.0
        if isinstance(self.ref,str):
            return menus.val(self.ref)
        else:
            return self.ref

    def tempWithGradient(self): # Current heating temperature along what is set in options
        if not self.ref: # do not heat !
            return 0.0
        if isinstance(self.ref,str):
            return menus.val(self.ref) + ( menus.val('G') if self.sensor1 == 'warranty' else GRADIENT_FOR_INTAKE if self.sensor1 == 'intake' else 0.0 )
        else:
            return self.ref

    # def tempRef2(self): # Current heating temperature along what is set in options
        # if not self.ref2: # do not heat !
            # return None
        # return menus.options[self.ref2][3]

    def desired_speed(self): # current speed even if options have changed
        if not self.base_speed or self.base_speed == NUL_SPEED:
            return 0.0
        if self.base_speed == MIN_SPEED:
            return pumpy.minimal_liters
        if self.base_speed == OPT_SPEED:
            return optimal_speed
        if self.base_speed == HALF_SPEED:
            return pumpy.maximal_liters / 2.0
        if self.base_speed == MAX_SPEED:
            return pumpy.maximal_liters
        return self.base_speed # If positive, absolute value

    # Initialize current operation and starts it if it is not the pump...
    def start(self):

        global T_Pump, menus, hotTapSolenoid

        time.sleep(0.01)
        dumpValve.set(1.0 if self.dump else 0.0)
        T_Pump.currOpContext = OperationContext(self,T_Pump.pump)
        T_Pump.forcible = False # unless TRAK...
        #print("%d >= %d" % ( (int(datetime.now().timestamp()) % (24*60*60)), int(menus.val('H'))) )
        if not self.programmable or not menus.val('H') or (int(time.time()) % (24*60*60)) >= int(menus.val('H')):
            T_Pump.T_DAC.set_temp(self.tempWithGradient(), self.tempRef())
        else:
            T_Pump.T_DAC.set_temp(None,None) # Delayed start
        # if self.cooling:
            # T_Pump.T_DAC.set_cold(menus.options['T'][3])
        # else:
            # T_Pump.T_DAC.set_cold(None)

        if self.waitAdd:
            T_Pump.waitingAdd = True
        if self.typeOp == 'FILL' :
            if State.empty :
                State.popDelayed()
                if menus.val('s') < 1.0:
                    hotTapSolenoid.set(1)
                else: # Eau dans un seau..
                    pass #TOOD:FLOOD with water in bucket + x seconds pumping; RFLO: do nothing
        elif self.typeOp == 'RFLO':
            State.popDelayed()
            if menus.val('s') < 1.0:
                hotTapSolenoid.set(1)
            else: # Eau dans un seau..
                pass #TOOD:FLOOD with water in bucket + x seconds pumping; RFLO: do nothing
        elif self.typeOp == 'FLOO':
            State.popDelayed()
            if menus.val('s') < 1.0:
                hotTapSolenoid.set(1)
                menus.options['u'][Menus.REF] = float(int((self.quantity()*10.0)+0.5))/10.0
                menus.options['r'][Menus.REF] = int(self.duration())
                #print("Set REF u="+str(self.duration)+", r="+str(self.quantity()))
            else: # Eau dans un seau..
                pass #TOOD:FLOOD with water in bucket + x seconds pumping; RFLO: do nothing
        elif self.typeOp == 'HOTW':
            State.popDelayed()
            if menus.val('s') < 1.0:
                valSensor1 = cohorts.getCalibratedValue(self.sensor1)
                if float(valSensor1) < float(self.tempRef()): # Shake
                    hotTapSolenoid.set(0)
                else:
                    hotTapSolenoid.set(1)
            else: # Eau dans un seau..
                pass #TOOD:FLOOD with water in bucket + x seconds pumping; RFLO: do nothing
        elif self.typeOp == 'REVR':
            T_Pump.pump.reset_pump()
        elif self.typeOp in ['PUMP', 'TRAK']:
            #T_Pump.forcible = True
            if self.pasteurizing > 0:
                if self.pasteurizing == 2:
                    reportPasteur.start(menus,'p')
                elif not reportPasteur.state:
                    reportPasteur.start(menus,'p')
                reportPasteur.save()
            elif reportPasteur.state:
                reportPasteur.save()
                reportPasteur.state = None
        elif self.typeOp == 'PAUS':
            if not T_Pump.added:
                if Buzzer:
                    Buzzer.on()
                T_Pump.setPause(True)
                T_Pump.setMessage(self.message)
            T_Pump.added = False
            T_Pump.waitingAdd = False
            State.transitCurrent(State.ACTION_RESUME, T_Pump.currAction)
        elif self.typeOp == 'SEAU':
            if menus.val('s') >= 1.0:
                if Buzzer:
                    Buzzer.on()
                T_Pump.setPause(True)
                T_Pump.setMessage(self.message)
        elif self.typeOp == 'SUBR': # 1st Call a subroutine and loop...
            ix = 0
            for op in opSequences[self.subSequence]:
                T_Pump.currSequence.insert(ix,op)
                ix += 1
            # prepare Subsequent execution of a subroutine
            #print ("SUBR %f.3 sec." % self.duration)
            #time.sleep(3.0)
            copOp = Operation(self.acronym,'SUBS',duration=self.duration,subSequence=self.subSequence)
            T_Pump.currSequence.insert(ix,copOp)
            T_Pump.pushContext(T_Pump.currOpContext)
        elif self.typeOp == 'SUBS': # Subsequent Call of a subroutine and loop...
            T_Pump.currOpContext = T_Pump.popContext()
            requiredTime = self.duration() if self.duration else None
            if requiredTime and (T_Pump.currOpContext.duration() >= requiredTime):
                pass
            else: # insérer la sous-séquence
                ix = 0
                for op in opSequences[self.subSequence]:
                    T_Pump.currSequence.insert(ix,op)
                    ix += 1
                T_Pump.currSequence.insert(ix,self)
                T_Pump.pushContext(T_Pump.currOpContext)
            # passer à l'instruction suivante le plus vite possible...
        time.sleep(0.01)

    # Checks if current operation is finished
    def isFinished(self):

        global cohorts

        time.sleep(0.01)
        dumpValve.set(1.0 if self.dump else 0.0) # Will stop command if open/close duration is done

        requiredTime = self.duration() if self.duration else None
        if requiredTime and T_Pump.currOpContext:
            try:
                currDuration = T_Pump.currOpContext.duration()
                #print ('Waited=%d vs Required=%d, Op=%s' % (currDuration, requiredTime,self.typeOp) )
                if currDuration >= requiredTime:
                    if self.typeOp == 'PAUS':
                        T_Pump.setPause(False)
                        time.sleep(0.01)
                    return True
            except:
                print ('Op=%s vs Required=%d' % (self.typeOp, requiredTime) )
                traceback.print_exc()
        currqty = self.quantity()
        if self.typeOp == 'HEAT':
            #if float(cohorts.getCalibratedValue('heating')) >= float(self.tempWithGradient()-HYSTERESIS):
            if float(cohorts.getCalibratedValue('heating')) >= float(self.tempRef()):
                return True
        elif self.typeOp == 'FILL' :
            if State.empty :
                time.sleep(0.01)
                return False # not finished
            else:
                return True # finished
        elif self.typeOp in ['FLOO','RFLO','HOTW']:
            if menus.val('s') < 1.0:
                if self.typeOp != 'RFLO':
                    time.sleep(0.01)
                    return False
            else: # Seau
                if self.typeOp == 'RFLO':
                    return True #Immediately finished because "reverse kick" of bucket water is not needed
            if currqty and T_Pump.currOpContext:
                if currqty > 0.0 and (T_Pump.currOpContext.volume() >= currqty):
                    return True
                if currqty < 0.0:
                    volnow = T_Pump.currOpContext.volume()
                    if volnow <= currqty:
                        return True
                    elif volnow > 0.2: # on part dans le mauvais sens !
                        T_Pump.pump.reset_pump()
                        return True
            time.sleep(0.01)
            return False # not finished
        elif self.typeOp in ['PUMP','TRAK','EMPT','REVR']:
            # if self.typeOp == 'TRAK' and self.sensor1 == 'warranty' and reportPasteur.state and T_Pump.currOpContext: # Pasteurizing and not cleaning
            #     if zeroIsNone(menus.val('Q')):
            #         if (reportPasteur.volume + T_Pump.currOpContext.volume()) > menus.val('Q'):
            #             menus.store('Q',None) # reset the option...
            #             return True
            if currqty and T_Pump.currOpContext:
                if currqty > 0.0 and (T_Pump.currOpContext.volume() >= currqty):
                    return True
                if currqty < 0.0:
                    volnow = T_Pump.currOpContext.volume()
                    if volnow <= currqty:
                        return True
                    elif volnow > 0.2: # on part dans le mauvais sens !
                        T_Pump.pump.reset_pump()
                        return True
            time.sleep(0.01)
            return False # not finished
        elif self.typeOp == 'SHAK':
##            if self.sensor1 and self.value1 \
##               and T_Pump.pump.speed > 0.0 \
##               and (float(cohorts.catalog[self.sensor1].value) >= float(self.value1)):
##                return True
            time.sleep(0.01)
            return False
        elif self.typeOp in ['PAUS','SEAU']: # Switch to next operation
            time.sleep(0.01)
            return not T_Pump.paused
        elif self.typeOp in ['SUBR','SUBS','MESS']: # Switch to next operation
            return True
        time.sleep(0.01)
        return False

    def quantity(self):
        if self.qty:
            if callable(self.qty):
                return self.qty()
            else:
                return self.qty
        else:
            return None

    # Keep going in the current operation
    def execute(self,now):

        global T_Pump, menus, hotTapSolenoid, reportPasteur

        time.sleep(0.01)
        Dt_line.set_ref_temp(self.tempRef(),menus.val('z'))
        dumpValve.set(1.0 if self.dump else 0.0) # Will stop command if open/close duration is done
        #print("%d >= %d" % ( (int(datetime.now().timestamp()) % (24*60*60)), int(menus.val('H'))) )
        if not self.programmable or not menus.val('H') or (int(datetime.now().timestamp()) % (24*60*60)) >= int(menus.val('H')):
            T_Pump.T_DAC.set_temp(self.tempWithGradient(),self.tempRef()) # In case of a manual change
        else:
            T_Pump.T_DAC.set_temp(None,None) #, None) # Delayed start
        # if self.cooling:
            # T_Pump.T_DAC.set_cold(menus.options['T'][3])
            # if zeroIsNone(menus.options['Q'][3]):
                # if T_Pump.pump.volume() > menus.options['Q'][3]:
                    # T_Pump.setPause(True)
                    # menus.options['Q'][3] = 0.0 # reset the option...
        # else:
            # T_Pump.T_DAC.set_cold(None)
        speed = T_Pump.pump.liters()
        typeOpToDo = self.typeOp
        if typeOpToDo == 'HOTW':
            if menus.val('s') >= 1.0:
                typeOpToDo = 'TRAK'
        if typeOpToDo in ['HEAT','PAUS','SEAU']:
            speed = 0.0
        elif typeOpToDo in ['PUMP','EMPT','REVR']:
            speed = self.desired_speed()
            if typeOpToDo == 'REVR':
                speed = -speed
        elif typeOpToDo == 'FILL' :
            if T_Pump.paused:
                hotTapSolenoid.set(0)
            elif State.empty:
                if menus.val('s') < 1.0:
                    hotTapSolenoid.set(1)
                else: # Water by bucket, what  must be done
                    speed = self.desired_speed()
        elif typeOpToDo in ['FLOO', 'RFLO', 'HOTW']:
            if T_Pump.paused:
                hotTapSolenoid.set(0)
            elif menus.val('s') < 1.0:
                if typeOpToDo == 'RFLO':
                    speed = -self.desired_speed()
                    hotTapSolenoid.set(1)
                elif typeOpToDo == 'HOTW':
                    valSensor1 = cohorts.getCalibratedValue(self.sensor1)
                    if float(valSensor1) < float(self.tempRef()): # Shake
                        hotTapSolenoid.set(0)
                    else:
                        hotTapSolenoid.set(1)
                else:
                    hotTapSolenoid.set(1)
            else: # Water by bucket, what  must be done
                speed = self.desired_speed()
        elif typeOpToDo == 'SHAK':
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
        elif typeOpToDo == 'TRAK':
            valSensor1 = cohorts.getCalibratedValue(self.sensor1)
            if hardConf.dynamicRegulation and self.sensor1 == 'warranty': # Pasteurizing and not cleaning
                #time_for_temp = Dt_line.legal_safe_time_to_kill(valSensor1)
                bacteria_of_concern, time_for_temp = Dt_line.scaled_time_to_kill(valSensor1,menus.val('z'))
                if not time_for_temp:
                    time_for_temp = 9999.9 # no dynamic regulation
            else:
                time_for_temp = 9999.9 # no dynamic regulation

            if T_Pump.time2speedL(time_for_temp) >= T_Pump.pump.minimal_liters:
                speed = T_Pump.dynamicRegulation(time_for_temp)
                T_Pump.pasteurizationOverSpeed = speed >= T_Pump.pump.maximal_liters
                if reportPasteur.startRegulating:
                    reportPasteur.regulations.append((time.perf_counter() - reportPasteur.startRegulating, (cohorts.mL('warranty')) / 1000.0))
                    reportPasteur.startRegulating = 0
                T_Pump.forcible = False
            else:  # More than 90 seconds to traverse pasteurization tube = too slow
                T_Pump.pasteurizationOverSpeed = False
                if float(valSensor1) < float(self.tempRef()): # Shake
                    T_Pump.forcible = True
                    pressed = GreenButton.poll() if GreenButton else False # Pressing the GreenButton forces slow speed forward...
                    if pressed and pressed > 0.0:
                        speed = abs(self.min_speed)
                    elif T_Pump.forcing > 0:
                        speed = abs(self.min_speed)
                    elif self.min_speed >= 0.0:
                        speed = self.min_speed
                    # self.min_speed < 0
                    elif speed == 0.0:
                        speed = self.min_speed # negative !
                    elif speed > 0.0:
                        if self.shake_qty and T_Pump.pump.current_liters(now) >= self.shake_qty:
                            # begin a regulation control cycle: start reversal
                            if not reportPasteur.startRegulating and self.sensor1 == 'warranty':
                                reportPasteur.startRegulating = time.perf_counter()
                            speed = self.min_speed # negative !
                        else:
                            speed = -self.min_speed # positive !
                    else: # speed negative !
                        if self.shake_qty and T_Pump.pump.current_liters(now) <= (-self.shake_qty):
                            # ends a regulation control cycle: resume forward
                            speed = -self.min_speed # positive !
                        else:
                            speed = self.min_speed # negative !
                    #print("SHAK="+str(speed)+"\r")
                else: # No more "shake"
                    if reportPasteur.startRegulating:
                        reportPasteur.regulations.append((time.perf_counter() - reportPasteur.startRegulating, cohorts.mL('warranty') / 1000.0))
                        reportPasteur.startRegulating = 0
                    T_Pump.forcible = False
                    #if menus.val('g') and self.sensor1 == 'warranty':
                    #    State.greasy = True
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
            if not hardConf.dynamicRegulation:
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
    def close(self):

        global T_Pump, menus, hotTapSolenoid

        if self.programmable and menus.val('H') and menus.val('H') != 0.0 and (int(datetime.now().timestamp()) % (24*60*60)) >= int(menus.val('H')):
            menus.store('H', 0.0)
        #T_Pump.T_DAC.set_cold(None)
        if self.typeOp in ['FILL','FLOO','RFLO','HOTW']:
            T_Pump.pump.stop()
            if menus.val('s') < 1.0:
                hotTapSolenoid.set(0)
                if (self.typeOp != 'RFLO') and (self.typeOp != 'FILL' or State.empty):
                    T_Pump.fbout += self.quantity() # add the quantity equivalent to the fill duration
            State.empty = False
        elif self.typeOp == 'REVR':
            T_Pump.pump.reset_pump()
        elif self.typeOp in ['PUMP','TRAK']:
            T_Pump.forcible = False
            T_Pump.pump.stop()
            if self.pasteurizing > 0 and reportPasteur.state:
                reportPasteur.volume = reportPasteur.volume + T_Pump.currOpContext.volume()
                reportPasteur.duration = reportPasteur.duration + T_Pump.currOpContext.duration()
                reportPasteur.save()
        elif self.typeOp in ['SHAK','EMPT']:
            T_Pump.forcible = False
            T_Pump.pump.stop()
            State.empty = (self.typeOp == 'EMPT')
        if self.message:
            if self.typeOp not in ['PAUS','SEAU']:
                T_Pump.setMessage(self.message)
        T_Pump.T_DAC.set_temp(None, None)
        dumpValve.setWait(1.0 if self.dump else 0.0)

# Tracks volumes based on speed and time
# if HEAT_EXCHANGER:
    # pumpy = pump.double_pump(addr0=0,addr1=1,inverse1=True)
# else:
    # pumpy = pump.pump()
pumpy = pump_pwm.pump_PWM()
Dt_line.set_pump(pumpy)
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

optimal_speed = 0.0 # regularly calculated by function reloadPasteurizationSpeed

def flood_liters_to_seconds(liters):
    # recent flood volume
    vol = menus.val('u')
    tim = menus.val('r')
    if vol <= 0.1 or tim < 20: # invalid parameters, return a default value
        return liters * 60 / FLOOD_PER_MINUTE
    return liters/vol*tim

menus.CITY_WATER_ACTIONS = "FRACDH"
DILUTION_ACTIONS = "ACD"

class buck(Enum):
    WPOT = 1
    DESI = 2
    RECUP = 3
    PAST = 4
    ACID = 5
    SEWR = 6
    AIR = 7
    CAUS = 8
    RAW = 9
    PAST2 = 10
    RAW2 = 11

in_FR = {None: "---", buck.WPOT: "Eau potable", buck.DESI: "Seau désinf.", buck.RECUP: "Seau récup.", buck.PAST : "Pastrsé", buck.ACID : "Seau acide", buck.CAUS : "Seau caust.", buck.AIR: "Air", buck.RAW: "Prod.crû", buck.SEWR: "Rejet", buck.PAST2:"Pastrsé2", buck.RAW2: "Prod.crû2"  }
in_EN = {None: "---", buck.WPOT: "Drink water", buck.DESI: "Sanit.Buckt", buck.RECUP: "Recov.Buckt", buck.PAST : "Pastrzed", buck.ACID : "Acid.Buckt", buck.CAUS : "Caustic.Buckt", buck.AIR: "Air", buck.RAW: "Raw Prod.", buck.SEWR: "Reject", buck.PAST2:"Pastrzed2", buck.RAW2: "Raw Prod.2" }
in_NL = {None: "---", buck.WPOT: "Drinkwater", buck.DESI: "OntsmtngsEmmr", buck.RECUP: "TerugwngsEmmr", buck.PAST: "Gepastrsrd", buck.ACID: "ZuurEmmr", buck.CAUS: "BijtndEmmer", buck.AIR: "Lucht", buck.RAW: "Ruw prod.", buck.SEWR: "Afgekeurd", buck.PAST2: "Gepastrsrd2", buck.RAW2: "Ruw prod.2"  }

opSequences = {
    # 'J': [Operation('PAUS','MESS',message="Jus = 75°C!")],
    # 'L': [Operation('PAUS','MESS',message="Lait = 72°C!")],
    # 'Y': [Operation('PAUS','MESS',message="Yaourt = 85°C!")],
    # 'T': [Operation('PAUS','MESS',message="Thermisation = 65°C!")],
    # 'S': [Operation('PAUS','MESS',message="Pause!")],
    # '_': [Operation('PAUS','MESS',message="Redémarrer!")],
    # 'X': [Operation('STOP','MESS',message="Au revoir!")],
    # 'Z': [Operation('STOP','MESS',message="Arrêt de l'opération en cours")],

    # 'A': # Amorçage, pré chauffage...
    #     [ Operation('AmoT','HEAT',ref='P', dump=True,programmable=True),
    #       Operation('AmoF','FILL',duration=lambda:menus.val('r'),base_speed=MAX_SPEED,qty=TOTAL_VOL, ref='P',dump=False),
    #       Operation('AmoI','FLOO',duration=lambda:menus.val('r')*1.5, base_speed=MAX_SPEED,qty=TOTAL_VOL*1.5, ref='P', dump=False),
    #       Operation('AmoJ','HEAT',ref='P', dump=False),
    #       Operation('Amoi','PUMP',base_speed=MAX_SPEED,qty=START_VOL,ref='P',dump=False),
    #       Operation('Amoo','SUBR',duration=lambda:menus.val('r'),subSequence='a',dump=False),
    #       Operation('AmoP','PUMP',ref='P',base_speed=MAX_SPEED, qty=1.0,dump=False),
    #       Operation('CLOS','MESS',message=ml.T("Déconnecter le tuyau d'entrée, P pour pasteuriser!","Disconnect input pipe, P to pasteurize!","Ontkoppel de invoerleiding, P om te pasteuriseren!"),dump=True)
    #       ],
    #
    # 'a': # Étape répétée du nettoyage
    #     [ Operation('Amop','PUMP',ref='P',base_speed=MAX_SPEED, qty=2.0,dump=False),
    #       Operation('AmoS','REVR',ref='P',base_speed=MAX_SPEED, qty=-0.4,dump=False)
    #       ],

    'F': # Pré-rinçage (Flush)
        [Operation('PreT','HEAT', ref='R', dump=True, programmable=True, bin=[buck.RECUP,buck.WPOT], bout=buck.RECUP, kbin=lambda:2*total_volume),
         Operation('PreS','SEAU',message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"),ref='R', dump=True),
         #Operation('PreF','FILL', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='R', dump=True),
         Operation('PreI','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='R', dump=True),  #
         Operation('PreR','RFLO',duration=lambda:KICKBACK,ref='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
         Operation('PreN','PAUS',message=ml.T("Une deuxième fois?","A second time?","Een tweede keer?"),ref='R'),
         Operation('Prei','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='R', dump=True),  #
         Operation('Prer','RFLO',duration=lambda:KICKBACK,ref='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
         Operation('Prem','MESS',message=ml.T("Rinçage terminé!","Rince finished!","Spoelen voltooid!"),dump=True)
         ],
    'H': # Distribution d'eau pasteurisée: GROSSIERE ERREUR: ne fonctionne que sur un circuit vide !!!
        [ Operation('HotT','HEAT', ref='P', dump=True, programmable=True, bin=buck.WPOT, bout=buck.SEWR, kbin=lambda:total_volume, kbout=lambda:start_volume),
          Operation('HotS','SEAU',message=ml.T("Eau propre en entrée!","Clean water as input!","Schoon water als input!"),dump=True),
          Operation('HotI','HOTW','warranty','input', duration=lambda:flood_liters_to_seconds(start_volume), base_speed=OPT_SPEED, min_speed=pumpy.minimal_liters, ref='P', qty=lambda:start_volume, shake_qty=SHAKE_QTY, dump=True),
          Operation('Hoti','HOTW','warranty','input', duration=lambda:flood_liters_to_seconds(safe_total_volume - start_volume), base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', qty=lambda:(safe_total_volume - start_volume), shake_qty=SHAKE_QTY, dump=True),
          Operation('HotE','PAUS',message=ml.T("Secouer/Vider le tampon puis une touche pour embouteiller","Shake / Empty the buffer tank then press a key to start bottling","Schud / leeg de buffertank en druk op een toets om het bottelen te starten"),ref='P',dump=True,bin=buck.RAW,bout=buck.PAST,kbin=0.0,qbout=True),
          Operation('HotW','HOTW','warranty','input',base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref='P',shake_qty=SHAKE_QTY,dump=True)
          ],
    'R': # Pré-rinçage 4 fois
        [ Operation('Pr1T','HEAT', ref='R', dump=True, programmable=True, bin=buck.RECUP, bout=buck.SEWR, kbout=lambda: 2 * total_volume, kbin=0.0),
          Operation('Pr1S','PAUS',message=ml.T("Eau recyclée en entrée!","Recycled water as Input!","Gerecycled water als input!"),dump=True),
          Operation('Pr1R','PUMP', base_speed=MAX_SPEED, qty=lambda:2*total_volume, ref='R', dump=True),
          Operation('End2','MESS',message=ml.T("double pré-rinçage effectué!","double pre-rince done!","2 keer doorspoelen!"),dump=True),
          Operation('PreT','HEAT', ref='R', dump=True, programmable=True, bin=[buck.WPOT, buck.WPOT], bout=buck.RECUP, kbout=lambda: 2 * total_volume),
          Operation('Pr3I','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='R', dump=True),  #
          Operation('Pr3R','RFLO',duration=lambda:KICKBACK,ref='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('PreS','PAUS',message=ml.T("Eau à recycler en entrée+sortie!","Water for future re-use as input+output!","Water voor toekomstig hergebruik als input+output!"),ref='R', dump=True),
          Operation('Pr4i','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='R', dump=True),  #
          Operation('Pr4r','RFLO',duration=lambda:KICKBACK,ref='R',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('Pr4m','MESS',message=ml.T("4 rinçages effectués!","4 flushes done!","4 keer doorspoelen!"),dump=True,)
          ],
    'V': # Vider le réservoir (aux égouts la plupart du temps)
        [  Operation('VidV','EMPT', base_speed=MAX_SPEED, qty=lambda:dry_volume, dump=True, bin=buck.AIR, bout=buck.RECUP, kbin=lambda:dry_volume, kbout=lambda:total_volume),
           Operation('Vidm','MESS',message=ml.T("Tuyaux vidés autant que possible.","Pipes emptied as much as possible.","Leidingen zoveel mogelijk geleegd."),dump=True)
        ],
    'A': # Désinfectant acide
        [ Operation('DesT','HEAT','intake','input', ref='R', dump=False, programmable=True, waitAdd=True, bin=[buck.ACID,buck.WPOT], bout=buck.ACID, kbin=lambda: (total_volume if State.empty else 0.0) + DILUTE_VOL),
          Operation('DesS','SEAU','intake','input',ref='R',message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"),dump=False),
          Operation('DesF','FILL','intake','input', ref='R', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, dump=False),
          Operation('DesI','FLOO','intake','input',ref='R',duration=lambda:flood_liters_to_seconds(DILUTE_VOL),base_speed=MAX_SPEED,qty=DILUTE_VOL, dump=False),
          Operation('DesN','PAUS','intake','input',ref='A',message=ml.T("Mettre dans le seau l'acide et les 2 tuyaux, puis redémarrer!","Put in the bucket the acid and the 2 pipes, then restart!","Doe het zuur en de 2 pijpen in de emmer, en herstart!"),dump=False,bin=buck.ACID,bout=buck.ACID,kbin=0.0,qbout=True),
          Operation('Desi','PUMP','intake','input', ref='A', base_speed=MAX_SPEED, qty=lambda:start_volume, dump=False),
          Operation('Desh','TRAK','intake','input', ref='A', base_speed=MAX_SPEED, min_speed=-pumpy.maximal_liters, qty=lambda:total_volume * 2.0, shake_qty=total_volume, dump=False),
          Operation('Desf','SUBR',duration=lambda:menus.val('a'),subSequence='a',dump=False),
          Operation('Dess','SEAU', message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"), dump=False, bin=[buck.ACID,buck.RECUP], bout=buck.ACID, kbin=lambda:total_volume, qbin=True, qbout=True),
          Operation('Desf','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='A', dump=False),
          Operation('Desm','MESS',message=ml.T("Seau d'Acide réutilisable en sortie... Bien rincer!","Reusable Acid Bucket in output... Rinse well!","Herbruikbaar zuur emmer in output... Goed uitspoelen!!"),dump=True)
        ],
    'a': # Étape répétée de la désinfection acide
        [ Operation('DesA','PUMP',ref='A', base_speed=MAX_SPEED, qty=4.0,dump=False,bin=buck.ACID,bout=buck.ACID),
          Operation('DesP','REVR',ref='A', base_speed=MAX_SPEED, qty=-2.0,dump=False)
        ],

    'D': # Désinfection (fut thermique)
        # [ Operation('Dett','HEAT','intake',ref='R',dump=False,programmable=True),
        #   Operation('DetS','SEAU',message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"),dump=True),
        #   Operation('DetI','FLOO','intake',duration=lambda:flood_liters_to_seconds(TOTAL_VOL), base_speed=MAX_SPEED,qty=TOTAL_VOL, ref='D',dump=True),  #
        #   Operation('Dety','PAUS',message=ml.T("Entrée et Sortie connectés bout à bout","Inlet and Outlet connected end to end","Input en output aangesloten"),ref='D',dump=False),
        #   Operation('Deth','TRAK','intake','input', base_speed=MAX_SPEED, min_speed=-pumpy.maximal_liters, ref='D', qty=TOTAL_VOL, shake_qty=TOTAL_VOL/2.1,dump=False),
        #   Operation('CLOS','MESS',message=ml.T("DANGER: Eau chaude sous pression. Mettre des gants pour séparer les tuyaux!","DANGER: Hot water under pressure. Wear gloves to separate the pipes!","GEVAAR: Heet water onder druk. Draag handschoenen om de leidingen te scheiden!"),dump=True)
        #   ],
        [ Operation('DetT','HEAT', ref='D', dump=False, programmable=True, waitAdd=True, bin=[buck.DESI,buck.WPOT], bout=buck.DESI, kbin=lambda: (total_volume if State.empty else 0.0) + DILUTE_VOL),
          Operation('DetS','SEAU',message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"),ref='D',dump=False),
          Operation('DetF','FILL', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='D', dump=False),
          Operation('DetI','FLOO',duration=lambda:flood_liters_to_seconds(DILUTE_VOL),base_speed=MAX_SPEED,qty=DILUTE_VOL, ref='D',dump=False),
          Operation('DetN','PAUS',message=ml.T("Mettre dans le seau le désinfectant acide et les 2 tuyaux, puis redémarrer!","Put in the bucket the sanitizer and the 2 pipes, then restart!","Doe het ontsmettingsmiddel en de 2 pijpen in de emmer, en herstart!"),ref='R',dump=False,bin=buck.DESI,bout=buck.DESI,kbin=0.0,qbout=True),
          Operation('Deti','PUMP', base_speed=OPT_SPEED, qty=lambda:total_volume, ref='D', dump=False),
          Operation('Detj','PUMP', base_speed=MAX_SPEED, qty=lambda:(total_volume * 2.0), ref='D', dump=False),
          Operation('Detn','PAUS',message=ml.T("Laisser tremper si désiré puis redémarrer!","Let soak for a while if desired then restart!","Laat eventueel weken, en herstart!"),ref='D',duration=lambda:menus.val('d'),dump=False),
          Operation('Dets','SEAU', message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"), ref='D', dump=False, bin=[buck.DESI,buck.WPOT], bout=buck.DESI, kbin=lambda:total_volume, qbin=True, qbout=True),
          Operation('Detf','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='D', dump=False),
          Operation('Detr','PAUS', message=ml.T("Evacuer le seau de désinfectant et lancer un dernier rinçage!","Remove the bucket with sanitizer and restart for a last rinse!","Verwijder de emmer met ontsmettingsmiddel en herstart aan een laatste spoeling!"), ref='D', dump=False, bin=[buck.WPOT,buck.RECUP], bout=buck.RECUP, kbin=lambda:total_volume, qbout=True),
          Operation('DetP','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='D', dump=True),
          Operation('DetR','RFLO',duration=lambda:KICKBACK,ref='D',base_speed=MAX_SPEED, qty=-2.0,dump=True),
          Operation('Desm','MESS',message=ml.T("Prêt à l'emploi!","Ready to use!","Klaar voor gebruik!"),dump=True)
        ],
    'C': # Détergent
        [ Operation('NetT','HEAT','intake','input', ref='R', dump=False, programmable=True, waitAdd=True, bin=[buck.CAUS,buck.WPOT], bout=buck.CAUS, kbin=lambda: (total_volume if State.empty else 0.0) + DILUTE_VOL),
          Operation('NetS','SEAU','intake','input',ref='R',message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"),dump=True),
          Operation('NetF','FILL','intake','input', ref='R', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, dump=False),
          Operation('NetI','FLOO','intake','input',ref='R',duration=lambda:flood_liters_to_seconds(DILUTE_VOL),base_speed=MAX_SPEED,qty=DILUTE_VOL,dump=False),
          Operation('NetY','PAUS','intake','input',ref='C',message=ml.T("Mettre le Nettoyant dans le seau puis une touche!","Put the Cleaner in the bucket then press a key!","Zet de Cleaner in de emmer en druk op een toets!"),dump=False,bin=buck.CAUS,bout=buck.CAUS,kbin=0.0,qbout=True),
          Operation('Neti','PUMP','intake','input', ref='C', base_speed=MAX_SPEED, qty=lambda:start_volume, dump=False),
          Operation('Neth','TRAK','intake','input', ref='C', base_speed=MAX_SPEED, min_speed=-pumpy.maximal_liters, qty=lambda:total_volume * 2.0, shake_qty=total_volume, dump=False),
          Operation('Neto','SUBR',duration=lambda:menus.val('c'),subSequence='c',dump=False),
          #Operation('NetV','EMPT',base_speed=MAX_SPEED, qty=TOTAL_VOL,dump=True),
          Operation('Nets','SEAU', message=ml.T("Eau potable en entrée!","Drinking water as input!","Drinkwater als input!"), dump=True, bin=[buck.CAUS,buck.WPOT], bout=buck.CAUS, kbin=lambda:total_volume, qbin=True, qbout=True),
          Operation('Netf','FLOO', duration=lambda:flood_liters_to_seconds(total_volume), base_speed=MAX_SPEED, qty=lambda:total_volume, ref='A', dump=False),
          Operation('Netm','MESS',message=ml.T("Seau de Soude réutilisable en sortie... Bien rincer!","Reusable Soda Bucket in output... Rinse well!","Herbruikbaar soda emmer in output... Goed uitspoelen!!"),dump=True)
        ],
    'c': # Étape répétée du nettoyage
        [ Operation('NetC','PUMP',ref='C',base_speed=MAX_SPEED, qty=4.0,dump=False,bin=buck.CAUS,bout=buck.CAUS),
          Operation('NetP','REVR',ref='C',base_speed=MAX_SPEED, qty=-2.0,dump=False)
          ],
    'B': # Calibrsation
        [ Operation('CL55','TRAK','heating','input', base_speed=OPT_SPEED, bin=buck.WPOT, bout=buck.WPOT, min_speed=-pumpy.minimal_liters, ref=55, qty=lambda:total_volume, shake_qty=SHAKE_QTY * 4, dump=False),
          Operation('CL66','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=60, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL6A','PUMP','heating','input', base_speed=OPT_SPEED, ref=60, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL65','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=65, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL6B','PUMP','heating','input', base_speed=OPT_SPEED, ref=65, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL77','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=70, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL7C','PUMP','heating','input', base_speed=OPT_SPEED, ref=70, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL75','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=75, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL7D','PUMP','heating','input', base_speed=OPT_SPEED, ref=75, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL88','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=80, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL8E','PUMP','heating','input', base_speed=OPT_SPEED, ref=80, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL85','TRAK','heating','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref=85, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False),
          Operation('CL8F','PUMP','heating','input', base_speed=OPT_SPEED, ref=85, qty=lambda:total_volume, shake_qty=SHAKE_QTY, dump=False)
          ],
    'P': # Pasteurisation
        [ Operation('PasT','HEAT', ref='P', dump=True, programmable=True, bin=buck.RAW, bout=buck.SEWR, kbin=lambda:safe_total_volume),
          Operation('PasI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref='P', qty=lambda:start_volume, shake_qty=SHAKE_QTY, dump=True),
          Operation('Pasi','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', qty=lambda:(safe_total_volume - start_volume), shake_qty=SHAKE_QTY, dump=True),
          Operation('PasE','PAUS',message=ml.T("Secouer/Vider le tampon puis une touche pour embouteiller","Shake / Empty the buffer tank then press a key to start bottling","Schud / leeg de buffertank en druk op een toets om het bottelen te starten"),ref='P',dump=True,bin=buck.RAW,bout=buck.PAST,qbout=True),
          Operation('PasP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', shake_qty=SHAKE_QTY, dump=True, kbin=0.0, pasteurizing=2),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ],
    'I': # Reprise d'une Pasteurisation
        [ Operation('PasT','HEAT',ref='P',dump=True,programmable=True,bin=buck.RAW,bout=buck.PAST,kbin=0.0),
          Operation('PasP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', shake_qty=SHAKE_QTY, dump=True, pasteurizing=1),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ],
    'E': # Eau pour finir une Pasteurisation en poussant juste ce qu'il faut le lait encore dans les tuyaux
        [ Operation('EauT','HEAT', ref='P', dump=True, programmable=True, bin=buck.WPOT, bout=buck.PAST, kbin=lambda:safe_total_volume),
          Operation('EauI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref='P', qty=SHAKE_QTY, shake_qty=SHAKE_QTY, dump=True, \
                    pasteurizing=1, kbin=lambda:safe_total_volume),
          Operation('EauP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', qty=lambda:(start_volume - SHAKE_QTY), shake_qty=SHAKE_QTY, dump=True, pasteurizing=1, kbin=lambda:safe_total_volume),
          Operation('EauV','PUMP', base_speed=OPT_SPEED, ref='P', qty=lambda:(safe_total_volume - start_volume), dump=True, pasteurizing=1),
          Operation('CLOS','MESS',message=ml.T("Maintenant, rincer puis nettoyer...","Now, Rinse and Clean...","Nu, uitspoelen en reinigen..."),dump=True)
          ],
    'M': # Passer à un lait d'un autre provenance en chassant celui de la pasteurisation précédente
        [ Operation('Mult','HEAT', ref='P', dump=True, programmable=True, bin=buck.RAW2, bout=buck.PAST, kbin=lambda:safe_total_volume, kbout=lambda:safe_total_volume),
          Operation('Muli','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed= pumpy.minimal_liters, ref='P', qty=SHAKE_QTY, shake_qty=SHAKE_QTY, dump=True, pasteurizing=1),
          Operation('Mulp','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', qty=lambda:start_volume - SHAKE_QTY, shake_qty=SHAKE_QTY, dump=True, pasteurizing=1),
          Operation('MulC','PAUS',message=ml.T("Consigne nouveau lait puis une touche pour finir de chasser le 1er lait","Setpoint for New milk then press a key to finish bottling 1st","Instelpunt voor nieuwe melk en druk vervolgens op een toets om het bottelen eerst te beëindigen"),ref='P',dump=True),
          Operation('MulT','HEAT',ref='P',dump=True),
          Operation('MulP','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', qty=lambda:(safe_total_volume - start_volume), shake_qty=SHAKE_QTY, dump=True, pasteurizing=1),
          Operation('MulE','PAUS',message=ml.T("Contenant pour le nouveau lait!","New Milk container!","Houder voor nieuwe melk!"),ref='P',dump=True,bin=buck.RAW2,bout=buck.PAST2,kbout=0.0,qbout=True),
          Operation('MulH','HEAT',ref='P',dump=True,kbin=0.0),
          Operation('MulI','TRAK','warranty','input', base_speed=OPT_SPEED, min_speed=-pumpy.minimal_liters, ref='P', shake_qty=SHAKE_QTY, dump=True, pasteurizing=2),
          Operation('CLOS','MESS',message=ml.T("Faites I pour reprise ou E pour chasser le lait!","Press I to resume or E to drive out the milk!","Druk op I om te hervatten of E om de melk te verdrijven!"),dump=True)
          ]
    }

def reloadPasteurizationSpeed():

    global menus,pumpy,optimal_speed

    init_volumes()

    if menus.val('M') < 12.0: # Minimum légal = 15 secondes de pasteurisation
        menus.store('M', 12.0)
    optimal_speed = (mL_L(hardConf.holding_volume) / menus.val('M')) * 3600.0 # duree minimale de pasteurisation (sec) --> vitesse de la pompe en L/heure

    if optimal_speed > pumpy.maximal_liters: # trop lent est sans doute dangereux
        optimal_speed = pumpy.maximal_liters
    elif optimal_speed < pumpy.minimal_liters: # trop lent est sans doute dangereux
        optimal_speed = pumpy.minimal_liters

    Dt_line.set_ref_speed(optimal_speed)
    # i=input(str(max_liters))

class ThreadPump(threading.Thread):

    def __init__(self, pumpy_param, T_DAC_param):

        global trigger_w, reportPasteur

        threading.Thread.__init__(self)
        self.running = False
        self.pump = pumpy_param
        self.T_DAC = T_DAC_param
        self.manAction('Z')
        since, current, empty, greasy = State.loadCurrent()
        trigger_w.base = since
        self.currSequence = None
        self.currOperation = None
        self.currOpContext = None
        self.operationContextStack = []
        self.paused = False
        self.startPause = 0
        self.pumpLastChange = 0 # Time of last change in pump running
        self.pumpLastVolume = 0
        self.pumpLastHeating = 0
        self.pumpLimit = None
        self.lastStop = 0
        self.lastDurationEval = None
        self.lastDurationEvalTime = None
        self.lastQuantityEval = None
        self.level1 = 1
        self.level2 = 0
        self.waitingAdd = False
        self.added = False
        self.forcing = 0
        self.forcible = False
        self.bin = None
        self.bout = None
        self.kbin = None
        self.kbout = None
        self.qbin = None
        self.qbout = None
        self.fbout = 0.0
        self.stopRequest = False
        self.pasteurizationOverSpeed = None
        self.pasteurizationDurations = {}
        self.message = ""
        self.currAction = "Z"
        self.startAction = None
        self.CurrOperation = None
        self.CurrSequence = None

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
        if op.bin is not None:
            self.bin = op.bin
            self.bout = op.bin
        if op.bout is not None:
            self.bout = op.bout
        if op.kbin is not None:
            self.kbin = op.kbin
            self.kbout = self.kbin
        if op.kbout is not None:
            self.kbout = op.kbout() if callable(op.kbout) else op.kbout
        if op.qbin is not None:
            if op.qbin:
                self.qbin = self.pump.volume()
        if op.qbout is not None:
            if op.qbout:
                self.qbout = self.pump.volume()
                self.fbout = 0.0
        self.message = None
        op.start()

    def nextOperation(self):
        if self.currOperation:
            self.currOperation.close()
            self.currOperation = None
            self.message = None
        if self.currSequence and len(self.currSequence):
            self.currOperation = self.currSequence[0]
            self.currSequence = self.currSequence[1:]
            self.startOperation(self.currOperation)
        else:
            State.transitCurrent(State.ACTION_END, self.currAction) # State obtained at the end of the action

    def closeSequence(self): # Executer la dernière opération si elle sert à cloturer une sequence
        if self.currOperation and self.currOperation.acronym != 'CLOS':
            self.currOperation.close()
            self.currOperation = None
            self.message = None
        if self.currSequence and len(self.currSequence):
            lastOp = self.currSequence[len(self.currSequence)-1]
            self.currSequence = None
            if lastOp.acronym == 'CLOS':
                self.startOperation(lastOp)
        else:
            self.currSequence = None

    def stopAction(self):

        global hotTapSolenoid

        # do whatever is needed
        self.closeSequence()
        self.CurrOperation = None
        self.CurrSequence = None
        self.manAction('Z') # Should stop operations...
        self.pump.reset_pump() # to be sure that no situation ends with a running pump...
        hotTapSolenoid.set(0) # and tap are closed !
        #self.setPause(False) COUNTER PRODUCTIVE?
        self.lastStop = time.perf_counter()

    def manAction(self,action):
        global menus

        menus.currAction = action
        self.currAction = action
        self.added = False
        self.waitingAdd = False
        self.startAction = time.perf_counter()
        self.T_DAC.empty_tank = False # Reset a detected empty tank

    def setAction(self,action):
        global opSequences
        action = action.upper()
        if action in opSequences:
            self.stopAction()
            self.manAction(action)
            State.transitDelayed( State.ACTION_BEGIN, action ) # Do not change state but be prepared to change !
            self.pump.reset_volume()
            self.qbin = None # No quantity offset now that pump volume is resetted
            self.qbout = None
            self.fbout = 0.0
            self.setPause(False)
            self.currSequence = []
            for op in opSequences[action]:
                self.currSequence.append(op)
            self.nextOperation()
            return True
        return False

    def setMessage(self,message):
        self.message = str(datetime.fromtimestamp(int(time.time())))[11:]+' : '+str(message)
        tell_message(message)

    def setPause(self,paused):

        global hotTapSolenoid, reportPasteur, YellowLED

        if self.paused and not paused:
            duration = time.perf_counter()-self.startPause
            if reportPasteur.state:
                reportPasteur.pauses.append((duration, cohorts.mL('warranty') / 1000.0))
            if self.currOpContext:
                self.currOpContext.extend_duration(duration)
        self.pumpLastChange = time.perf_counter()
        self.pumpLastVolume = self.pump.volume()
        self.pumpLastHeating = self.T_DAC.totalWatts
        if not self.paused and paused:
            self.startPause = self.pumpLastChange

        self.paused = paused
        if paused:
            if YellowLED:
                YellowLED.set(0)
            T_Pump.pump.reset_pump()
            hotTapSolenoid.set(0)

    def durationRemaining(self,now):

        warning = False
        if not self.currOperation:
            self.lastDurationEval = None
            return 0, warning
        if not self.currOperation.duration:
            if self.currOperation.typeOp == 'HEAT':
                heating = cohorts.getCalibratedValue('heating')
                #print("heating=%d" % heating)
                diffTemp = float(self.currOperation.tempRef())-float(heating)
                #print("diffTemp=%f" % diffTemp)
                if diffTemp <= 0.0:
                    self.lastDurationEval = None
                    newEval = 0
                else:
                    newEval =  diffTemp * tank * kCalWatt / ( (hardConf.power_heating-((heating-ROOM_TEMP)*WATT_LOSS))) * 3600.0
                    #print("Evaluation=%f tank=%f kCalW=%f HP=%f RT=%f WL=%f" % (newEval, tank, kCalWatt,hardConf.power_heating,ROOM_TEMP,WATT_LOSS) )
                    if not self.lastDurationEval or not self.lastDurationEvalTime:
                        self.lastDurationEval = newEval
                        self.lastDurationEvalTime = now
                    elif now > (self.lastDurationEvalTime+TANK_EMPTY_LIMIT) :
                        Factor = (self.lastDurationEval - newEval) / (now-self.lastDurationEvalTime)
                        if Factor > TANK_NOT_FILLED:
                            warning = True
                            print("!Warning: tank is heating too fast! Factor=%f" % Factor)
                        self.lastDurationEval = newEval
                        self.lastDurationEvalTime = now
                return int(newEval), warning
            else:
                self.lastDurationEval = None
                subr = self.topContext()
                if subr and subr.operation and subr.operation.duration:
                    return subr.operation.duration() - subr.duration(), warning
                return 0, warning
        else: # Timed operation
            if not self.paused or self.currOperation.typeOp == 'PAUS':
                self.lastDurationEval = self.currOperation.duration() - self.currOpContext.duration()
            return int(self.lastDurationEval), warning

    def quantityRemaining(self):
        if not self.currOperation:
            return 0.0
        currqty = self.currOperation.quantity()
        if not currqty:
            subr = self.topContext()
            if subr and subr.operation:
                subrqty = subr.operation.quantity()
                if subrqty:
                    vol = subr.volume()
                    if subrqty > 0.0 and (vol < subrqty):
                        return subrqty - vol
                    if subrqty < 0.0 and (vol > subrqty):
                        return vol - subrqty
            return 0.0
        vol = T_Pump.currOpContext.volume()
        if currqty > 0.0 and (vol < currqty):
            return currqty - vol
        if currqty < 0.0 and (vol > currqty):
            return vol - currqty
        return 0.0

    def time2speedL(self, duration):
        return (hardConf.holding_volume / duration)*3600.0/1000.0 # to get liters per hour

    def dynamicRegulation(self, pasteurization_holding_time):

        curr_volume = self.pump.volume()*1000.0  # Liters to milliliters !
        end_holding = curr_volume+hardConf.holding_volume
        if end_holding in self.pasteurizationDurations:
            prev =  self.pasteurizationDurations[end_holding]
            if pasteurization_holding_time <= prev:
                pasteurization_holding_time = prev
            else:
                self.pasteurizationDurations[end_holding] = pasteurization_holding_time
        else:
            self.pasteurizationDurations[end_holding] = pasteurization_holding_time
        #print ("Set "+str(curr_volume)+"+"+str(hardConf.holding_volume)+"="+str(end_holding)+"mL "+str(pasteurization_holding_time)+"sec.")

        to_remove = []
        max_time = pasteurization_holding_time
        for (vol,time) in self.pasteurizationDurations.items():
            if vol < curr_volume:
                to_remove.append(vol)
            elif time > max_time:
                max_time = time
        print (to_remove)
        for vol in to_remove:
            # print ("Remove "+str(vol)+"mL "+str(self.pasteurizationDurations[vol])+"sec.")
            del(self.pasteurizationDurations[vol])
        return self.time2speedL(max_time)

    def run(self):

        global display_pause, WebExit, RedConfirmationDelay, trigger_w, reportPasteur

        if GreenLED:
            GreenLED.off()
        if YellowLED:
            YellowLED.off()
        if RedLED:
            RedLED.on()
        RedPendingConfirmation = 0.0
        prec_loop = time.perf_counter()
        self.running = True
        self.stopRequest = False
        self.pasteurizationDurations = {}

        speed = 0.0
        prec_speed = 0.0

        while self.running:
            try:
                time.sleep(PUMP_LOOP_DELAY)
                now = time.perf_counter()

                if trigger_w.trigger():
                    State.transitCurrent(State.ACTION_RESUME, 'w')
                if RedPendingConfirmation != 0.0:
                    if RedLED:
                        RedLED.blink(2)
                    if self.currAction in [None,'X','Z',' ']:
                        if GreenLED:
                            GreenLED.blink(2)
                        if YellowLED:
                            YellowLED.blink(2)

                if self.stopRequest or (RedButton and RedButton.acknowledge()):
                    if self.currAction not in [None,'X','Z',' ']: # Immediate stop, no confirmation
                        self.stopAction()
                    elif self.stopRequest:
                        pass # Do not allow shuting down the machine by the Web interface
                    elif RedPendingConfirmation > 0.0: # Red button already pressed, SHUTDOWN action can be taken
                        RedPendingConfirmation = 0.0
                        if Buzzer:
                            Buzzer.on()
                        self.close()
                        self.manAction('X')
                        WebExit = True # SHUTDOWN requested
                        if Buzzer:
                            Buzzer.off()
                        try:
                            os.kill(os.getpid(),signal.SIGINT)
                        except:
                            traceback.print_exc()
                    else:
                        if RedPendingConfirmation == 0.0: # Synchronize all LED !
                            if RedLED:
                                RedLED.off()
                                RedLED.blink(2)
                            if YellowLED:
                                YellowLED.off()
                            if GreenLED:
                                GreenLED.off()
                        RedPendingConfirmation = 0.0 - (now + RedConfirmationDelay) #Confirmation must occur within 3 seconds
                    self.stopRequest = False
                else: # RedButton not pressed
                    if RedPendingConfirmation != 0.0:
                        if RedPendingConfirmation < 0.0: # Button not released yet
                            RedPendingConfirmation = 0.0 - RedPendingConfirmation
                        if now > RedPendingConfirmation:
                            RedPendingConfirmation = 0.0
                            if RedLED:
                                RedLED.on()
                    elif RedLED:
                        RedLED.on()
                if YellowButton and YellowButton.acknowledge():
                    if not self.paused:
                        self.setPause(True)  # Will make the pump stops !
                if EmergencyButton and EmergencyButton.acknowledge():
                    if not self.paused:
                        self.setPause(True)  # Will make the pump stops !
                    T_DAC.set_temp(None, None)
                if GreenButton and GreenButton.acknowledge():
                    if self.paused:
                        self.setPause(False)

                if hardConf.MICHA_device and hardConf.io: # Output probably in the buffer tank
                    # Level1 = Input (pulled HIGH = OK, in liquid), LOW = in Air: Pause!
                    hardConf.io.write_pin(hardConf.MICHApast.LEVEL1_FLAG_REG,1) # Enable Level detection (not meaning 1=PullUp)
                    self.level1 = hardConf.io.read_discrete(hardConf.MICHApast.LEVEL_SENSOR1_REG)
                    if self.level1 == 0 and T_Pump.currAction in ['M','E','P','H','I']:
                        self.setPause(True)
                    # Level2 = Output (pulled LOW = OK, in Air, NOT in liquid), HIGH = in Liquid: Pause!
                    hardConf.io.write_pin(hardConf.MICHApast.LEVEL2_FLAG_REG,1 if T_Pump.currAction in ['M','E','P','H','I'] else 0) # Enable Level detection if pasteurizing (not meaning 0=PULLDOWN)
                    self.level2 = hardConf.io.read_discrete(hardConf.MICHApast.LEVEL_SENSOR2_REG)
                    #print ("Output in liquid=%d" % self.level2)
                    if self.level2 and T_Pump.currAction in ['M','E','P','H','I']:
                        self.setPause(True)
                if Buzzer:
                    Buzzer.off()

                if self.forcing > 0:
                    now = int(time.time())
                    if now > self.forcing:
                        self.forcing = 0

                if self.paused:
                    speed = 0.0
                    if GreenLED:
                        GreenLED.blink(2) # blink twice per second
                    if self.currOperation and self.currOperation.typeOp == 'PAUS' and self.currOperation.duration and self.currOperation.isFinished():
                        self.nextOperation()
                else:
                    if GreenLED:
                        if RedPendingConfirmation != 0.0 and self.currAction in [None,'X','Z',' ']:
                            pass
                        else:
                            GreenLED.off()
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
                        speed = self.currOperation.execute(now)
                    else:
                        speed = 0.0
                if YellowLED:
                    if RedPendingConfirmation != 0.0 and self.currAction in [None,'X','Z',' ']:
                        pass
                    elif speed == 0.0 and int(hotTapSolenoid.value) == 0:
                        YellowLED.off()
                    else:
                        YellowLED.on()
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
                        State.popDelayed()

                    time.sleep(0.01)
                    if not DEBUG:
                        prec_disp = display_pause
                        display_pause = True
                        (nlines,ncols) = termSize()
                        term.pos(1,ncols-10)
                        term.write("%5.2d" % speed, term.bold, term.yellow if speed > 0.0 else term.red, term.bgwhite)
                        display_pause = prec_disp
                # if not reportPasteur.state:
                #     if State.current.letter in ['p','e'] :
                #         reportPasteur.start(menus, State.current.letter)
                # else:
                #     if State.current.letter not in ['p','e'] :
                #         if reportPasteur.volume > 0.0 :
                #             reportPasteur.save()
                #         reportPasteur.state = None
                #         reportPasteur.volume = 0.0
                #     elif State.current.letter == 'p':
                #         reportPasteur.volume = reportPasteur.base_volume+(self.pump.volume() - (self.qbout if self.qbout is not None else 0.0)) + self.fbout
                #         reportPasteur.duration = time.perf_counter() - reportPasteur.begin
                if reportPasteur.state:
                    if State.current.letter == 'p':
                        loop_delay = time.perf_counter()
                        reportPasteur.total_time_heating = reportPasteur.total_time_heating + ((loop_delay-prec_loop)*isnull(cohorts.catalog['DAC1'].value,0))
                        reportPasteur.total_temperature = reportPasteur.total_temperature + (self.pump.speed*(loop_delay-prec_loop)*cohorts.catalog['heating'].value)
                    else:
                        reportPasteur.save()
                        # reportPasteur.state = None NO! NO!
            except:
                traceback.print_exc()
                self.pump.stop()
                prec_speed = 0.0
            prec_loop = time.perf_counter()

        # if State.current.letter in ['p','e'] and reportPasteur.volume > 0.0 : # Closing while pasteurizing: save the report !
        #     reportPasteur.save()
        if reportPasteur.state:
            reportPasteur.save()
            reportPasteur.state = None
        time.sleep(0.01)
        self.pump.stop()

    def close(self):
        self.running = False
        time.sleep(0.1)
        self.pump.close()
        time.sleep(0.1)
        if RedLED:
            RedLED.off()

    def inCurrent (self,bin):
        return self.pump.volume() - (self.qbin if self.qbin is not None else 0.0)

    def inTotal (self,bin):
        return self.kbin() if callable(self.kbin) else self.kbin

    def outCurrent (self,bin):

        if self.currAction != 'V':
            currV = 0.0
            if menus.val('s') < 1.0 and self.currOpContext and self.currOperation and self.currOperation.typeOp in ['FLOO','FILL','HOTW']:
                if self.paused:
                    currV = self.lastQuantityEval
                else:
                    currV = self.currOpContext.duration()
                vol = menus.val('u')
                tim = menus.val('r')
                if vol <= 0.1 or tim < 20: # invalid parameters, return a default value
                    currV *= (FLOOD_PER_MINUTE/60.0)
                else:
                    currV *= (vol/tim)
            self.lastQuantityEval = currV

            result = (self.pump.volume() - (self.qbout if self.qbout is not None else 0.0)) + self.fbout
            return result + currV
        self.lastQuantityEval = None
        return None # remaining water in pipe is unknown

    def outTotal (self,bin):
        return self.kbout() if callable(self.kbout) else self.kbout


term.setTitle("AKUINO, pasteurisation accessible")
(lines, columns) = termSize()
term.pos(lines,1)
for i in range(1,lines):
    term.writeLine(" ",term.black, term.bgwhite)

# Solenoids:
hotTapSolenoid = Solenoid('TAP',hardConf.TAP)

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
else:
    ExtraSensor = Sensor(99,'extra','')

T_Thermistor = ThreadThermistor()
T_Thermistor.daemon = True
try:
    T_Thermistor.sensorParam("input",hardConf.T_input, hardConf.beta_input, hardConf.ohm25_input, hardConf.A_input, hardConf.B_input, hardConf.C_input) # Entrée
    T_Thermistor.sensorParam("intake",hardConf.T_intake, hardConf.beta_intake, hardConf.ohm25_intake, hardConf.A_intake, hardConf.B_intake, hardConf.C_intake) # Sortie
    T_Thermistor.sensorParam("warranty", hardConf.T_warranty, hardConf.beta_warranty, hardConf.ohm25_warranty, hardConf.A_warranty, hardConf.B_warranty, hardConf.C_warranty) # Garantie sortie serpentin long
    #T_Thermistor.sensorParam("temper",hardConf.T_sp9b) # Garantie entrée serpentin court
except:
    traceback.print_exc()
if hardConf.T_heating:
    T_Thermistor.sensorParam("heating",hardConf.T_heating, hardConf.beta_heating, hardConf.ohm25_heating, hardConf.A_heating, hardConf.B_heating, hardConf.C_heating)
if hardConf.inputPressure:
    T_Thermistor.pressureSensorParam("press", hardConf.inputPressure, hardConf.inputPressureFlag) # Garantie sortie serpentin long

if not pumpy.open():
    term.writeLine("Pompe inaccessible ?", term.red, term.bold, term.bgwhite)
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
T_Buttons = ThreadButtons([RedButton, YellowButton, GreenButton, EmergencyButton])
T_Pump = ThreadPump(pumpy,T_DAC)

dumpValve = None
# Ball Valve:
if dumpValve:
    dumpValve = Valve('DMP',hardConf.DMP_open,hardConf.DMP_close) # using default duration set in Valve.py...
else:
    dumpValve = Sensor(Valve.typeNum,'DMP',hardConf.DMP_open) # Dummy Valve only to know if we are dumping or cycling...
dumpValve.set(1.0) # Open by default

with open(datafiles.csvfile(datafiles.logfile), "w") as data_file:
    data_file.write("epoch_sec\tstate\taction\toper\tstill\tqrem\twatt\tvolume\tpump\tpause\tinput\twarant\tintake\theat\theatbath\t"
                    + ("press" if hardConf.inputPressure else "rmeter")
                    + "\tlinput\tloutput\n") #\twatt2\ttemper\theat
    term.write("Données stockées dans ",term.blue, term.bgwhite)
    term.writeLine(os.path.realpath(data_file.name),term.red,term.bold, term.bgwhite)

#x=""
#T_DAC.set_temp((options['P'][3] + BATH_TUBE))
#cohorts.dump()
#while x != "y":
#    display_pause = True
#    time.sleep(0.2)
#    x = str(getch()).lower()
#    if x:
#        if x=="d":
#            cohorts.last_travel("sp9")
#        elif x=="y":
#            break
#        else:
#            x=input("Start?")
#            x = float(x)
#            pumpy.run_liters(x)
#display_pause = False

#for x in cohorts.sequence:
#    print(x[0],x[1])
#a=input("next")

T_Thermistor.start()
T_DAC.T_Pump = T_Pump
T_DAC.daemon = False # No KILL: wait for graceful close
T_DAC.start()
T_Pump.start()
T_Buttons.start()

APPLICATION_COOKIE = "AKUINOpast"

### Web Server section
def ensureLogin(mail, password):
    if mail == KEY_ADMIN and password == PWD:
        infoCookie = mail + ',' + PWD
        web.setcookie(APPLICATION_COOKIE, infoCookie, expires=9000, samesite="Strict")
        return True
    return False

def init_access():

    data = web.input(nifile={})
    if data and ('lang' in data) and data['lang']:
        ml.setLang(data['lang'])
    mail = None
    password = None
    # redir = path = web.ctx.env.get('PATH_INFO')
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

paving = False

class WebIndex:
    def __init(self):
        self.name = u"WebIndex"

    def GET(self):
        global paving
        data, connected, mail, password = init_access()
        if 'paving' in data and len(data['paving']) > 0:
            paving = data['paving'][0].lower() in ['o','y','d','s']
        commands = 'false'
        if 'commands' in data and len(data['commands']) > 0:
            if data['commands'][0].lower() in ['o','y','d','s']:
                commands = 'true'
        return render.index(connected, mail, False, None, paving, commands) #True if Paving...

    def POST(self):
        return self.GET()

class WebOption:
    def __init(self):
        self.name = u"WebOption"

    def GET(self,page):

        global reportPasteur

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')

        if data and len(data) > 1: # Process saved options from options editing forms
            #print(data.__repr__())
            if 'reset' in data and data['reset'].lower() == 'on':
                for choice in (menus.cleanOptions if page == '1' else menus.dirtyOptions):
                    if len(menus.options[choice]) > Menus.INI:
                        menus.options[choice][Menus.VAL] = menus.options[choice][Menus.INI]
                reloadPasteurizationSpeed()
                menus.save()
            else:
                for keys in menus.options.keys():
                  if 'opt_'+keys in data:
                    val = data['opt_'+keys]
                    if not val:
                        menus.options[keys][Menus.VAL] = menus.options[keys][Menus.INI]
                    else:
                        # if menus.options[keys][Menus.TYP] == "text" and keys == 'F':
                        #     val = val.upper()
                        menus.store(keys, val)
                reloadPasteurizationSpeed()
                menus.save()
                raise web.seeother('/')

        Dt_line.set_ref_temp(menus.val('P'),menus.val('z'))
        render_page = getattr(render, 'option'+page)
        return render_page(connected, mail, reportPasteur, Dt_line.tag_index() )

    def POST(self,page):
        return self.GET(page)

class WebLogTable:
    def __init(self):
        self.name = u"WebLogTable"

    def GET(self):
        data, connected, mail, password = init_access()
        return render.index(connected,mail, True, None, False, False)

    def POST(self):
        return self.GET()

class WebExplain:

    def __init(self):
        self.name = u"WebExplain"

    def GET(self, letter):

        data, connected, mail, password = init_access()
        return render.index(connected,mail, False, letter, False, False)

def LogData(letter):
    global T_DAC, T_Pump, menus, optimal_speed, cohorts, hotTapSolenoid

    data, connected, mail, password = init_access()
    web.header('Content-type', 'application/json; charset=utf-8')
    if False: #not connected and not guest:
        currLog = {'message':str(ml.T('RECHARGER CETTE PAGE',"RELOAD THIS PAGE","HERLAAD DEZE PAGINA"))}
    else:
        nowT = time.time()
        (durationRemaining, warning) = T_Pump.durationRemaining(nowT)
        if durationRemaining:
            durationRemaining = format_time(durationRemaining)
        else:
            durationRemaining = ''
        quantityRemaining = T_Pump.quantityRemaining()
        #temper = menus.options['T'][3]
        opt_temp = menus.val('P')
        bin = None
        bout = None
        kbin = None
        kbout = None
        actif = False
        if T_Pump.currAction and T_Pump.currAction != 'Z':
            message = str(menus.actionName[T_Pump.currAction][2])
            if T_Pump.currOperation:
                actif = True
                opt_temp = T_Pump.currOperation.tempRef()
                if opt_temp == 0.0:
                    opt_temp = menus.val('P')
                if T_Pump.message:
                    message = str(T_Pump.message)
                elif T_Pump.currOperation.message:
                    message = str(T_Pump.currOperation.message)
                else:
                    message = str(menus.operName[T_Pump.currOperation.typeOp])
                bin = T_Pump.bin
                if isinstance(bin, list):
                    bin = bin[0 if menus.val('s') < 1.0 else 1]
                kbin = T_Pump.inTotal(bin)
                if kbin == 0.0:
                    kbin = None
                bout = T_Pump.bout
                if isinstance(bout, list):
                    bout = bout[0 if menus.val('s') < 1.0 else 1]
                kbout = T_Pump.outTotal(bout)
                if kbout == 0.0:
                    kbout = None
            else:
                message = str(ml.T("Opération terminée.","Operation completed.","Operatie voltooid."))
        else:
            message = str(ml.T("Choisir une action dans le menu...","Choose an action in the menu ...","Kies een actie in het menu ..."))
        pumping_time = time.perf_counter() - T_Pump.pumpLastChange
        pumping_volume = T_Pump.pump.volume() - T_Pump.pumpLastVolume
        heating_volume = T_DAC.totalWatts - T_Pump.pumpLastHeating
        danger = ''
        intake_temp = cohorts.getCalibratedValue('intake')
        input_temp = cohorts.getCalibratedValue('input')
        warranty_temp = cohorts.getCalibratedValue('warranty')
        heating_temp = cohorts.getCalibratedValue('heating')
        if (intake_temp or 0.0) < 1.0 or (input_temp or 0.0) < 1.0 or (warranty_temp or 0.0) < 1.0 or (heating_temp or 0.0) < 1.0:
            danger = str(ml.T('Capteur déconnecté?',"Sensor disconnected?","Sensor losgekoppeld?"))
        elif (intake_temp or 0.0) > 99.0 or (input_temp or 0.0) > 99.0 or (warranty_temp or 0.0) > 99.0 or (heating_temp or 0.0) > 99.0:
            danger = str(ml.T('Capteur cassé?',"Sensor broken?","Sensor kapot?"))
        elif T_DAC.empty_tank:
            danger = str(ml.T('Cuve de chauffe VIDE ou déconnectée?','Heating tank EMPTY or disconnected?','Verwarmingstank LEEG of losgemaakte?'))
        elif warning:
            danger = str(ml.T('Cuve de chauffe mal remplie?','Heating tank not correctly filled?','Verwarmingstank niet correct gevuld?'))
    return {    'date': str(datetime.fromtimestamp(int(nowT))), \
                'actif': 1 if actif else 0, \
                'actionletter': T_Pump.currAction, \
                'preconfigletter':menus.val('z'), \
                'action': str(menus.actionName[T_Pump.currAction][1]), \
                'actiontitle': str(menus.actionName[T_Pump.currAction][3]), \
                'stateletter': (State.current.letter if State.current else ''),
                'empty': ('V' if State.empty else 'W'),
                'danger': danger,
                'bin' : bin.name if bin else None,
                'bout' : bout.name if bout else None,
                'tbin' : str(ml.T(in_FR[bin],in_EN[bin],in_NL[bin])) if bin and bin != bout else None,
                'tbout' : str(ml.T(in_FR[bout],in_EN[bout],in_NL[bout])) if bout else None,
                'qbin' : T_Pump.inCurrent(bin) if bin and bin != bout else None,
                'kbin' : kbin if bin and bin != bout else None,
                'qbout' : T_Pump.outCurrent(bout) if bout else None,
                'kbout' : kbout,
                #'greasy': ('G' if State.greasy else 'J'),
                'state': (str(State.current.labels) if State.current else ''),
                'statecolor': (str(State.current.color) if State.current else 'black'),
                'allowedActions' : (str(State.current.allowedActions()) if State.current else ''),
                'accro': T_Pump.currOperation.acronym if T_Pump.currOperation else "", \
                'delay': durationRemaining, \
                'remain': quantityRemaining, \
                'totalwatts': T_DAC.totalWatts, \
                #'totalwatts2': T_DAC.totalWatts2, \
                'volume': T_Pump.pump.volume(), \
                'speed': T_Pump.pump.liters() if not T_Pump.paused else 0, \
                #'extra': isnull(cohorts.getCalibratedValue('extra'), ''), \
                'input': isnull(input_temp, ''), \
                'intake': isnull(intake_temp, ''), \
                'watts': isnull(cohorts.catalog['DAC1'].value*hardConf.power_heating, '0'), \
                #'watts2': isnull(cohorts.catalog['DAC2'].value*MITIG_POWER, ''), \
                'warranty': isnull(warranty_temp, ''), \
                'heating': isnull(heating_temp, ''), \
                #'temper': isnull(cohorts.getCalibratedValue('temper'), ''), \
                'rmeter': isnull(cohorts.val('rmeter'), ''), \
                'press': isnull(cohorts.val('press',peak=0), ''), \
                'pressMin': isnull(cohorts.val('press',peak=-1), ''), \
                'pressMax': isnull(cohorts.val('press',peak=1), ''), \
                'reft': isnull(cohorts.reft.value, ''), \
                'message': message + (str(ml.T(' - Cuve mal remplie?',' - Tank not filled?',' - Tank niet gevuld?')) if warning else ''), \
                #'opt_T': temper if temper <  99.0 else '', \
                'opt_M': menus.val('M'), \
                'opt_temp': opt_temp, \
                'added': 2 if T_Pump.added else (1 if T_Pump.waitingAdd else 0),
                'bucket': (1 if T_Pump.currAction in menus.CITY_WATER_ACTIONS else 0) if menus.val('s') < 1.0 else 2,
                'purge': (3 if T_Pump.currOperation and (not T_Pump.currOperation.dump) else 2) if dumpValve.value == 1.0 else (0 if T_Pump.currAction in ['M','E','P','H','I'] else 1), \
                'pause': 1 if T_Pump.paused else 0, \
                'fill': hotTapSolenoid.get()[0], \
                'pumpopt': optimal_speed, \
                'pumpeff': (pumping_volume/(pumping_time/3600)) if pumping_time else 0, \
                'heateff': (100.0*heating_volume/(pumping_time/3600))/hardConf.power_heating if pumping_time else 0, \
                'level1': T_Pump.level1, \
                'level2': T_Pump.level2, \
                'forcing': 2 if T_Pump.forcing > 0 else (1 if T_Pump.forcible else 0) \
                }

class WebApiAction:

    def __init(self):
        self.name = u"WebApiAction"

    def GET(self, letter):

        global menus, WebExit, dumpValve

        data, connected, mail, password = init_access()
        web.header('Content-type', 'application/json; charset=utf-8')
        if not connected:
            result = {'message':'RECHARGER CETTE PAGE'}
        else:
            message = ""
            # StateLessActions
            if letter in ['J','K','L','T','Y']:
                Heating_Profile.setProfile(letter,menus)
                reloadPasteurizationSpeed()
            # end of StateLessActions
            elif letter == 'S':  # Pause
                if not T_Pump.paused:
                    T_Pump.setPause(True)  # Will make the pump stops !
                    message = str(ml.T("Pause","Pause","Pauze"))
                else:
                    message = str(ml.T("Déjà en Pause","Already Paused","Al gepauzeerd"))
                time.sleep(0.01)
            elif letter == '_':  # Restart
                if not T_Pump.paused:
                    message = str(ml.T("Pas en Pause","Not Paused","Niet gepauzeerd"))
                else:
                    T_Pump.setPause(False)
                    message = str(ml.T("Redémarrage","Restart","Herstart"))
                time.sleep(0.01)
                if T_Pump.currOperation and (not T_Pump.currOperation.dump) and dumpValve.value != 0.0:
                    dumpValve.setWait(0.0)
                time.sleep(0.01)
            elif letter == '>':  # Forcer
                if T_Pump.forcing > 0:
                    T_Pump.forcing = 0
                else:
                    T_Pump.forcing = int(time.time()) + DEFAULT_FORCING_TIME
                time.sleep(0.01)
            elif letter == '+':  # Product added
                if T_Pump.added:
                    T_Pump.added = False
                    T_Pump.waitingAdd = True
                    message = str(ml.T("Produit PAS ajouté","Product NOT added","Product NIET toegevoegd"))
                else:
                    T_Pump.added = True
                    T_Pump.waitingAdd = False
                    message = str(ml.T("Produit ajouté","Product added","Product toegevoegd"))
                time.sleep(0.01)
            elif letter == '!':  # Seau fourni
                if menus.val('s') < 1.0:
                    menus.store('s',1.0)
                else:
                    menus.store('s',0.0)
                message = str(ml.T("Seau","Bucket","Emmer"))+'='+str(menus.val('s'))
                time.sleep(0.01)
            # elif letter == 'U':  # Dump output tank
            #        dumpValve.setWait(1.0)
            #        message = str(ml.T("Purge en cours","Purge bagan","Zuivering..."))
            #        time.sleep(0.01)
            elif letter in ['X','Z']:
                #T_Pump.stopAction()
                T_Pump.stopRequest = True
                if letter == 'X':
                    T_Pump.manAction('X')
                    os.kill(os.getpid(),signal.SIGINT)
                    WebExit = True # SHUTDOWN !
                time.sleep(0.01)
            else: # State dependent Actions
                if not T_Pump.setAction(letter):
                    message = str(ml.T("Invalide","Invalid","Ongeldig"))
            result = LogData(letter)
            if message:
                result['message'] = message
        return json.dumps(result)

    def POST(self,letter):
        return self.GET(letter)

class WebApiLinear:

    def __init(self):
        self.name = u"WebApiLinear"

    def GET(self, address, a=None, b=None):

        data, connected, mail, password = init_access()
        web.header('Content-type', 'application/json; charset=utf-8')
        if not connected:
            return json.dumps({'message':'RECHARGER CETTE PAGE'})
        else:
            #factors = {}
            if data and 'a' in data and 'b' in data: # Process saved options from options editing forms
                cohorts.saveLinear(address, data['a'],data['b'])
            elif a and b:
                cohorts.saveLinear(address, a, b)
        return json.dumps(cohorts.getLinear(address))

    def POST(self,address):
        return self.GET(address)

class WebApiState:

    def __init(self):
        self.name = u"WebApiState"

    def GET(self, letter):

        data, connected, mail, password = init_access()
        web.header('Content-type', 'application/json; charset=utf-8')
        if not connected:
            result = {'message':'RECHARGER CETTE PAGE'}
        else:
            empty = State.empty
            #greasy = State.greasy
            if data: # Process saved options from options editing forms
                empty = False
                if 'empty' in data and data['empty'].lower() == 'on':
                    empty = True
                #greasy = False
                #if ('greasy' in data and data['greasy'].lower() == 'on'):
                    #greasy = True
            State.setCurrent(letter,empty,False) #greasy
            result = LogData(T_Pump.currAction)
        return json.dumps(result)

    def POST(self,letter):
        return self.GET(letter)

def calib_digest(param_sensor):

    global temp_ref_calib

    means = {}
    for x in temp_ref_calib:
        new_temp = x[param_sensor]
        if new_temp:
            tru = x['reft']
            reducted = int(new_temp/5.0)*5.0
            if reducted not in means:
                means[reducted] = [0, 0.0, 0.0]
            means[reducted] = [means[reducted][0]+1, means[reducted][1]+new_temp, means[reducted][2]+tru]
    for key, val in means.items():
        q = val[0]
        val[1] = val[1]/q
        val[2] = val[2]/q
    return means

def calib_remove(param_sensor, temp_class):

    global temp_ref_calib

    for x in temp_ref_calib:
        app_calib = x[param_sensor]
        if app_calib and temp_class <= app_calib < (temp_class + 5.0):
            x[param_sensor] = None

class WebCalibrate:

    def __init(self):
        self.name = u"WebCalibrate"

    def GET(self, param_sensor=None):

        global calibrating, temp_ref_calib

        data, connected, mail, password = init_access()
        means = {}
        if not connected:
            raise web.seeother('/')
        elif param_sensor:
            to_be_saved = False
            if param_sensor[0] == '!':
                to_be_saved = True
                param_sensor = param_sensor[1:]
            elif param_sensor[0] == '*':
                param_sensor = param_sensor[1:]
                if 'class' in data and data['class']:
                    calib_remove(param_sensor, float(data['class']))
            if param_sensor == "reset":
                temp_ref_calib = []
                calibrating = True
            elif param_sensor == "merge": # not yet implemented...
                temp_ref_calib = cohorts.mergeCalibration(temp_ref_calib)
            elif param_sensor == "on":
                calibrating = True
            elif param_sensor == "off":
                calibrating = False
            elif len(temp_ref_calib) > 0 and param_sensor in temp_ref_calib[0]:
                means = calib_digest(param_sensor)
                if to_be_saved:
                    meansort = sorted(means.items())
                    cohorts.saveCalibration(param_sensor, meansort)
        return render.calibrate(param_sensor, calibrating, temp_ref_calib, means)

    def POST(self, param_sensor=None):
        return self.GET(param_sensor)

class WebApiPut:

    def __init(self):
        self.name = u"WebApiPut"

    def GET(self, param_sensor):

        global calibrating, temp_ref_calib, cohorts

        if param_sensor == "!s_REFT": # Reference sensor
            data = web.input(nifile={})
            if data and ('value' in data) and data['value']:
                ref_val = float(data['value'])
                if -4.0 < ref_val < 120.0:
                    cohorts.reft.set(ref_val)
                    if calibrating:
                        now = time.time()
                        temp_ref_calib.append({'time':now, \
                                    'reft':ref_val, \
                                    #'extra': cohorts.catalog['extra'].value, \
                                    'input': cohorts.catalog['input'].value, \
                                    'intake': cohorts.catalog['intake'].value, \
                                    'warranty': cohorts.catalog['warranty'].value, \
                                    'heating': cohorts.catalog['heating'].value })
        return "" # Status 200 is enough !

    def POST(self,param_sensor):
        return self.GET(param_sensor)

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
        return json.dumps(LogData(T_Pump.currAction))

    def POST(self):
        return self.GET()

class getCSS:
    def GET(self, filename):
        web.header('Content-type', 'text/css')
        with open( datafiles.static_filepath( 'css', filename) ) as f:
            try:
                return f.read()
            except IOError:
                web.notfound()

class getJS:
    def GET(self, filename):
        web.header('Content-type', 'application/javascript')
        with open( datafiles.static_filepath( 'js', filename) ) as f:
            try:
                return f.read()
            except IOError:
                web.notfound()

class getFavicon:
    def GET(self, extension):
        web.header('Content-type', 'image/x-icon')
        with open( datafiles.static_filepath( None, 'favicon.ico'), 'rb' ) as f:
            try:
                return f.read()
            except IOError:
                web.notfound()

class getCSV:
    def GET(self, fileParam=None, endParam=None):

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        elif not endParam:
            if not fileParam:
                fileParam = datafiles.logfile
            web.header('Content-type', 'text/csv')
            with open(datafiles.csvfile(fileParam),'r') as f:
                try:
                    return f.read()
                except IOError:
                    web.notfound()
        else: # Two YYYY_MMDD_HHmm
            web.header('Content-type', 'text/csv')
            # list to store files
            res = []
            gotSmall = False
            # Iterate directory
            for path in sorted(os.listdir(datafiles.DIR_DATA_CSV),reverse=True):
                # check if current path is a file
                if os.path.isfile(os.path.join(datafiles.DIR_DATA_CSV, path)) and len(path) == 18 and path.startswith("2") \
                        and path.endswith(".csv") and path <= endParam:
                    if gotSmall:
                        break
                    res.append(path)
                    if path < fileParam:
                        gotSmall = True
            result = ""
            for fileName in sorted(res):
                with open(datafiles.DIR_DATA_CSV + fileName ) as f:
                    try:
                        if result:
                            f.readline() # skip header if result is not empty
                        result = result + f.read()
                    except IOError:
                        traceback.print_exc()
            return result

class getCSVdir:
    def GET(self):

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        else:
            # list to store files
            res = []

            # Iterate directory
            for path in os.listdir(datafiles.DIR_DATA_CSV):
                # check if current path is a file
                if os.path.isfile(os.path.join(datafiles.DIR_DATA_CSV, path)) and path.startswith("2") and path.endswith(".csv"): #and len(path) == 18
                    res.append(path)
            return render.csvdir(sorted(res))

class WebReport:
    def GET(self, batchParam=None):

        global reportPasteur

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        elif not batchParam or batchParam == "current":
            return render.report(reportPasteur)
        elif batchParam:
            shownReport = report.load(batchParam)
            if shownReport:
                #print (json.dumps(shownReport.to_dict()))
                return render.report(shownReport)
            else:
                raise web.seeother('/reports')
        else:
            raise web.seeother('/reports')

    def POST(self, batchParam=None):

        global reportPasteur

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        else:
            if not batchParam or batchParam == "current" or batchParam == reportPasteur.batch:
                reportPasteur.record(data)
                return render.report(reportPasteur)
            elif batchParam:
                shownReport = report.load(batchParam)
                if shownReport:
                    shownReport.record(data)
                    return render.report(shownReport)
                else:
                    raise web.seeother('/reports')
            else:
                raise web.seeother('/reports')

class WebReports:
    def GET(self):

        global reportPasteur

        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        else:
            res = report.list_reports()
            return render.reportdir(sorted(res), reportPasteur)

class WebReportDelete:

    def GET(self,path=None):
        data, connected, mail, password = init_access()
        if not connected:
            raise web.seeother('/')
        else:
            success = report.delete(path)
            raise web.seeother('/reports')

def restart_program():
    """Restarts the current program, with file objects and descriptors
       cleanup
    """
    _lock_socket.close()
    python = sys.executable
    program_args = sys.argv
    program_args[0] = os.path.join(datafiles.DIR_BASE, os.path.basename(sys.argv[0]))
    os.execl(python, python, *program_args)

class WebLog(object):
    # format log on screen with some legibility...
    def write(self,data):
        data = data.split('\n')
        for line in data:
            if line:
                print (line+'\r')

    def flush(self):
        pass

SoftwareUpdate = False
webServerThread = None
inputProcessorThread = None

class WebSoftwareUpdate:
    def __init(self):
        self.name = "WebSoftwareUpdate"

    def GET(self):
        data, connected, mail, password = init_access()

        if not connected:
            raise web.seeother('/')
        subprocess.call(['git', 'pull'])
        git_status_out = subprocess.check_output(['git', 'status']).decode("utf-8")
        git_status_lines = git_status_out.split('\n')
        try:
            git_status_out = (git_status_lines[0]
                              + '<br>'
                              + git_status_lines[1])
        except IndexError:
            print(("Error reading git status output. " + git_status_out))
            raise
        return render.update(connected, git_status_out)

    def POST(self):
        global SoftwareUpdate, webServerThread, inputProcessorThread

        data, connected, mail, password = init_access()

        if not connected:
            raise web.seeother('/')
        if connected is not None and data.start_elsa_update is not None:
            SoftwareUpdate = True
            print ("stop requested...")
            webServerThread.stop()
            inputProcessorThread.stop()
            raise web.seeother('/')
        else:
            raise web.seeother('/')

class ThreadWebServer(threading.Thread):

    def __init__(self, param_app):
        threading.Thread.__init__(self, target=param_app.run)
        self.app = param_app

#    def run(self):
#        self.app.run()


    def stop(self):
        try:
            self.app.stop()
        except:
            traceback.print_exc()

def freshHref(letter,url):
    pieces = url.split('#')
    if len(pieces) < 2:
        pieces.append('')
    if pieces[0] == web.ctx.fullpath:
        return ' onclick="reloadHere("'+letter+'")" href="#'+pieces[1]+'"'
    else:
        return ' href="'+url+'" onclick="closeMenu("'+letter+'")"'

class ThreadInputProcessor(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global T_Pump, webServerThread, display_pause, menus

        while T_Pump.currAction != 'X' and webServerThread.is_alive():
            try:
                time.sleep(0.2)
                #now = time.time()
                menu_selection = str(getch()).upper() # BLOCKING I-O !
                if menu_selection == ' ':
                    display_pause = False
                elif menu_selection in ['M', 'E', 'P', 'H', 'I', 'R', 'V', 'F', 'A', 'C', 'D', 'X', 'Z', 'B']: # 'C','K'
                    menu_selection = menu_confirm(menu_selection, 8.0)
                    if menu_selection == 'X':
                        #T_Pump.stopAction()
                        T_Pump.stopRequest = True
                        break
                    if menu_selection == 'Z':
                        #T_Pump.stopAction()
                        T_Pump.stopRequest = True
                    elif menu_selection in ['M', 'E', 'P', 'H', 'I', 'R', 'V', 'F', 'A', 'C', 'D', 'B']: # 'C','K'
                        T_Pump.setAction(menu_selection)
                    time.sleep(0.01)
                elif menu_selection in ['J', 'K', 'L', 'T', 'Y']:
                    Heating_Profile.setProfile(menu_selection, menus)
                    option_confirm(0.0)
                elif menu_selection == 'S': # Pause / Restart
                    if not T_Pump.paused:
                        T_Pump.setPause(True) # Will make the pump stops !
                    menu_selection = menu_confirm(menu_selection)
                    if menu_selection == 'S':
                        T_Pump.setPause(False)
                    elif menu_selection == 'V':
                        T_Pump.setPause(False)
                        T_Pump.setAction(menu_selection)
                    elif menu_selection == 'Z':
                        #T_Pump.stopAction()
                        T_Pump.stopRequest = True
                elif menu_selection == 'O': # Options...
                    option_confirm()
                elif menu_selection:
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
                #T_Pump.stopAction()
                T_Pump.stopRequest = True
                break
            except:
                traceback.print_exc()
                time.sleep(5)
            ## End of main loop.

    def stop(self):
        try:
            T_Pump.setAction('X')
        except:
            traceback.print_exc()

#web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)
try:
    web.config.debug = False # NE JAMAIS METTRE A TRUE, CETTE APPLICATION NE SE "RELOADE" PAS !!!
    # Configuration Singleton ELSA
    web.template.Template.globals['str'] = str
    web.template.Template.globals['sorted'] = sorted
    web.template.Template.globals['round'] = round
    web.template.Template.globals['subprocess'] = subprocess
    web.template.Template.globals['menus'] = menus
    web.template.Template.globals['Menus'] = Menus
    web.template.Template.globals['ml'] = ml
    web.template.Template.globals['web'] = web
    web.template.Template.globals['hardConf'] = hardConf
    web.template.Template.globals['isnull'] = isnull
    web.template.Template.globals['zeroIsNone'] = zeroIsNone
    web.template.Template.globals['datetime'] = datetime
    web.template.Template.globals['datafiles'] = datafiles
    web.template.Template.globals['profiles'] = Heating_Profile.profiles
    layout = web.template.frender(datafiles.TEMPLATES_DIR + '/layout.html')
    render = web.template.render(datafiles.TEMPLATES_DIR, base=layout)
    web.httpserver.sys.stderr = WebLog()
    urls = (
        '/', 'WebIndex',
        '/index.html', 'WebIndex',
        '/index', 'WebIndex',
        '/action/(.)', 'WebApiAction',
        '/state/(.)', 'WebApiState',
        '/explain/(.)', 'WebExplain',
        '/logtable', 'WebLogTable',
        '/option(.)', 'WebOption',
        '/calibrate/(.+)', 'WebCalibrate',
        '/calibrate', 'WebCalibrate',
        '/linear/(.+)/(.+)/(.+)', 'WebApiLinear',
        '/linear/(.+)', 'WebApiLinear',
        '/api/log', 'WebApiLog',
        '/api/put/(.+)', 'WebApiPut',
        '/favicon(.+)', 'getFavicon',
        '/static/js/(.+)', 'getJS',
        '/static/css/(.+)', 'getCSS',
        '/js/(.+)', 'getJS',
        '/css/(.+)', 'getCSS',
        '/csvdir', 'getCSVdir',
        '/csv/(.+)/(.+)', 'getCSV',
        '/csv/(.+)', 'getCSV',
        '/csv', 'getCSV',
        '/report', 'WebReport',
        '/report/(.+)', 'WebReport',
        '/reportdel/(.+)', 'WebReportDelete',
        '/reports', 'WebReports',
        '/update', 'WebSoftwareUpdate',
        '/disconnect', 'WebDisconnect'
        #'/restarting', 'WebRestarting'
    )
    app = web.application(urls, globals())
    app.notfound = notfound

    webServerThread = ThreadWebServer(app)
    webServerThread.daemon = True
    webServerThread.start()
#    app.run()
except:
    traceback.print_exc()

if GreenLED:
    GreenLED.on()
if YellowLED:
    YellowLED.on()
if RedLED:
    RedLED.on()

### Console running in parallel with Web Server
inputProcessorThread = ThreadInputProcessor()
inputProcessorThread.daemon = True
display_pause = True
inputProcessorThread.start()

while T_Pump.currAction != 'X' and webServerThread.is_alive() and inputProcessorThread.is_alive():
    try:
        time.sleep(0.2)
    except:
        traceback.print_exc()
        break

if webServerThread.is_alive():
    try:
        # Stops Web Server...
        webServerThread.stop()
        time.sleep(0.1)
    except:
        traceback.print_exc()

if inputProcessorThread.is_alive():
    try:
        # Stops Web Server...
        inputProcessorThread.stop()
        time.sleep(0.1)
    except:
        traceback.print_exc()

# Close equipments...
change = dumpValve.setWait(1.0)  # better to keep dumping valve open
term.write ("Vanne ", term.blue, term.bgwhite)
term.writeLine ("OUVERTE vers l'égout.", term.green, term.bold, term.bgwhite)
try:
    T_DAC.close()
    term.write ("Chauffe ", term.blue, term.bgwhite)
    term.writeLine ("éteinte.", term.green, term.bold, term.bgwhite)
    time.sleep(0.1)
except:
    traceback.print_exc()

if T_PumpReading:
    try:
        T_PumpReading.close()
        time.sleep(0.1)
    except:
        traceback.print_exc()

try:
    T_Pump.close()
    time.sleep(0.2)
    term.write ("Pompe ", term.blue, term.bgwhite)
    term.writeLine ("éteinte.", term.green, term.bold, term.bgwhite)
except:
    traceback.print_exc()

try:
    T_Buttons.close()
    term.write ("Boutons ", term.blue, term.bgwhite)
    term.writeLine ("éteints.", term.green, term.bold, term.bgwhite)
except:
    traceback.print_exc()

try:
    hotTapSolenoid.close()
    #coldTapSolenoid.close()
except:
    traceback.print_exc()

while T_DAC.is_alive():
    T_DAC.running = False
    time.sleep(0.2)

with open(datafiles.csvfile(datafiles.logfile), "r") as data_file:
    term.write("Données stockées dans ",term.blue, term.bgwhite)
    term.writeLine(os.path.realpath(data_file.name),term.red,term.bold, term.bgwhite)

hardConf.close()

if WebExit: # Exit asked from web: shutdown the computer
    #To make the following call possible, please configure in /etc/sudoer file:
    #    username ALL = NOPASSWD: /sbin/shutdown
    #    %admin  ALL = NOPASSWD: /sbin/shutdown
    print ("shutdown...")
    #subprocess.call(['sudo','/sbin/shutdown', '-h', 'now'])
    # NEEDS: systemctl enable poweroff.target  ???
    subprocess.call(['systemctl','--no-wall','poweroff'])
    print ("Done!")
    #os.system('systemctl poweroff')  demande aussi une authentication...

if RedLED:
    RedLED.off()
if YellowLED:
    YellowLED.off()
if GreenLED:
    GreenLED.off()

try:
    if hardConf.localGPIOtype == "gpio":
        hardConf.localGPIO.cleanup()
    elif hardConf.localGPIOtype == "pigpio":
        hardConf.localGPIO.stop()
except:
    traceback.print_exc()


if SoftwareUpdate:
    SoftwareUpdate = False
    print("restart...")
    restart_program()

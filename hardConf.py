#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
import socket
import traceback
import os
import codecs
import sys
from serial import Serial, PARITY_NONE, PARITY_EVEN
import platform
import term
import ml
import MICHApast

processor = None #1: Raspberry, 2=Odroid...
io = None
adc = None
localGPIO = None
localGPIOtype = None
Rmeter = None

# Heating tanks
DAC1 = 10 # C: Pasteurization
DAC2 = 12 # T: Temperization

# Dump Valve
DMP_open = 2
DMP_close = 6

# Pump
pumpON = 0
pumpOFF = 1
pumpDirection = -14

# Solenoids to control water inputs
TAP = 8 # Hot rinsing water
CLD = 4 # Cooling water

# Thermistors number
T_input = 1 # Entrée
T_output = 2 # Sortie
T_warranty = 3 # Garantie sortie serpentin long
T_heating = 4 # If no OneWire, this will be T_sp9b
T_extra = None

OW_input = None # Entrée
OW_output= None # Sortie
OW_warranty = None # Garantie sortie serpentin long
OW_heating = None # If no OneWire, this will be T_sp9b
OW_extra = None

MICHA_device = None
thermistors_voltage = 4.087 # Surprisingly not 4.095
thermistors_Rtop = 2000.0 # Divider bridge to measure temperature (top resistor). Should include 2 ohms for the transistor of stimulation power

hostname = socket.gethostname()
machine = platform.machine()
print (hostname+" / "+machine)

HARDdirectory = os.path.join(os.path.dirname(os.path.abspath(__file__)),"configs")

serialNumber = ""
configCode = ""
prefixHostname = "pasto"
configFile = ""
configParsing = None
MICHA_version = None
reversedPump = False

if hostname.startswith(prefixHostname):
    i = hostname.index('-')
    if i < len(prefixHostname):
        print ("A '-'(dash) must precede the pasteurizer serial number in the hostname")
    else:
        configCode = hostname[len(prefixHostname):i]
        serialNumber = hostname[i:]
        configFile = os.path.join(HARDdirectory,configCode+'.ini')
else:
    print ("hostname must begin by pasto")

if configFile:
    configParsing = configparser.RawConfigParser()
    try:
        with codecs.open(configFile, 'r', 'utf8' ) as f:
            configParsing.read_file(f)
    except IOError:
        new_path = os.path.join(HARDdirectory, 'DEFAULT.ini')
        print((configFile+' not found. Using ' + new_path))
        try:
            with codecs.open(new_path, 'r', 'utf8' ) as f:
                configParsing.read_file(f)
        except IOError:
            print("No valid hardware configuration file found. \
                   Using built-in defaults...")
if configParsing:
    if 'system' in configParsing.sections():
        for anItem in configParsing.items('system'):
            if anItem[0].lower() == 'type':
                processor = anItem[1].lower()
                if processor == "rpi" and not localGPIOtype:
                    localGPIOtype = 'pigpio'
                elif processor == "odroid" and not localGPIOtype:
                    localGPIOtype = "pypi"
            elif anItem[0].lower() == 'gpio':
                localGPIOtype = anItem[1].lower()
        if localGPIOtype == "pigpio":
            import pigpio
            localGPIO = pigpio.pi() # Uses BCM numbering for pins...
            pigpio_PUD_UP = pigpio.PUD_UP
            pigpio_INPUT = pigpio.INPUT
            pigpio_OUTPUT = pigpio.OUTPUT
        elif localGPIOtype == "pypi":
            try:
                if processor == "odroid":
                    import Odroid.GPIO as GPIO
                else:
                    import RPi.GPIO as GPIO
            except RuntimeError:
                print("Error importing RPi or Odroid.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")
            GPIO.setmode(GPIO.BOARD)
            localGPIO = GPIO # Uses BOARD numbering for pins...

    if 'user' in configParsing.sections():
        for anItem in configParsing.items('user'):
            if anItem[0].lower() == 'lang':
                ml.setLang(anItem[1].lower())

    if 'MICHA' in configParsing.sections():
        for anItem in configParsing.items('MICHA'):
            if anItem[0].lower() == 'device':
                MICHA_device = anItem[1]
            elif anItem[0].lower() == 'version':
                try:
                    MICHA_version = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
        if MICHA_version >= 40:
            import MICHA40past
            io = MICHA40past.Micha4(MICHA_device)
        else:
            io = MICHApast.Micha(MICHA_device)
            reversedPump = True

    if 'heating' in configParsing.sections():
        for anItem in configParsing.items('heating'):
            if anItem[0].lower() == 'port':
                try:
                    T_heating = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_heating = anItem[1]

    if 'extra' in configParsing.sections():
        for anItem in configParsing.items('extra'):
            if anItem[0].lower() == 'port':
                try:
                    T_extra = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_extra = anItem[1]

    if 'input' in configParsing.sections():
        for anItem in configParsing.items('input'):
            if anItem[0].lower() == 'port':
                try:
                    T_input = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_input = anItem[1]

    if 'output' in configParsing.sections():
        for anItem in configParsing.items('output'):
            if anItem[0].lower() == 'port':
                try:
                    T_output = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_output = anItem[1]

    if 'warranty' in configParsing.sections():
        for anItem in configParsing.items('warranty'):
            if anItem[0].lower() == 'port':
                try:
                    T_warranty = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_warranty = anItem[1]

    if 'Rmeter' in configParsing.sections():
        import RMETERpast
        #BCM (pigpio) configuration
        R_S1=25
        R_S2=6
        R_S3=5
        R_polarity=16
        for anItem in configParsing.items('Rmeter'):
            if anItem[0].lower() == 's1':
                try:
                    R_S1 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 's2':
                try:
                    R_S2 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 's3':
                try:
                    R_S2 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 'polarity':
                try:
                    R_polarity = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
        Rmeter = RMETERpast.R_Meter(S1=R_S1, S2=R_S2, S3=R_S3, polarityIO=R_polarity) # bus=0, spi_channel=0, bus2=1, spi_channel2=0

# One Wire sensors address
# if hostname == "pastOnomic":
#     Raspberry = True
#     MICHA_device = "/dev/serial0"
#     io = MICHApast.Micha(MICHA_device)
#     OW_heating = "28.CC3EAF040000"  # Extra: typiquement sortie du refroidissement rapide
#     OW_extra = None # "28.AA5659501401"  # Bain de tempérisation (sortie) régulé en refroidissement   28.FFDD64931504 est mort (FFDD)
# elif hostname == "pastoB04001":
#     Odroid = True
#     MICHA_device = "/dev/ttyS1"
#     pumpON = 1
#     pumpOFF = 0
#     import MICHA40past
#     io = MICHA40past.Micha4(MICHA_device)
#     T_heating = T_extra
#     OW_heating = None
#     OW_extra = None # "28.AA5659501401"  # Bain de tempérisation (sortie) régulé en refroidissement   28.FFDD64931504 est    # OW_temper = "28.AABA43501401"  # Bain de chauffe
#     ml.setLang('f')
# elif hostname == "christophe-Latitude-E7440":
#     #OW_temper = "28.A6156B070000"  # Extra: typiquement sortie du refroidissement rapide
#     OW_heating = "28.AA5E36501401"  # Bain de chauffe
#     OW_extra = "28.CC3EAF040000"  # Bain de tempérisation (sortie) régulé en refroidissement
#     ml.setLang('e')
# else keep variables undefined...

if MICHA_device:
    thermistors_voltage = MICHApast.VOLTAGE_REF
    
    # Heating tanks
    DAC1 = MICHApast.TANK1_REG # C: Pasteurization
    DAC2 = MICHApast.TANK2_REG # T: Temperization

    # Dump Valve
    DMP_open = MICHApast.VALVE1_POW_REG
    DMP_close = MICHApast.VALVE1_DIR_REG

    # Solenoids to control water inputs
    CLD = MICHApast.SOL_HOT_REG # Hot rinsing water
    TAP = MICHApast.SOL_COLD_REG # Cooling water

elif localGPIOtype == "pypi":
    from ExpanderPi import IO
    from ExpanderPi import ADC

    try:
        io = IO()
        # All ExpanderPI GPIO in output mode:
        io.set_port_direction(0, 0x00)
        io.set_port_direction(1, 0x00)
        # All OFF except Thermistor stimulation (1,3,5,7):
        io.write_port(0, 0x00)
        io.write_port(1, 0x00)
        adc = ADC()
    except:
        io = None
        adc = None
        print("PANNE des Signaux de contrôle")
        traceback.print_exc()

def close():
    if MICHA_device:
        io.close()
    elif localGPIOtype == "pypi":
        # All ExpanderPI GPIO in input mode:
        io.set_port_direction(0, 0xFF)
        io.set_port_direction(1, 0xFF)
        ## We do not leave output floating because we are not sure we have the right pull up always there...
        ##io.set_port_direction(0, 0xFF)
        ##io.set_port_direction(1, 0xFF)
        localGPIO.cleanup()
    elif localGPIOtype == "pigpio":
        localGPIO.stop()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
import socket
import traceback
import os
import codecs
import sys
from serial import Serial, PARITY_NONE, PARITY_EVEN # pip install pyserial
import platform
import term
import ml
import MICHApast
import owner

processor = None # pc, rpi, odroid
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

# Max allowed speed (RPM) allowed for the pump (theoretical: 600)
pumpMaxRPM = 600 #360 #450 #Maximum pump speed without "rattrapage"

# Solenoids to control water inputs
TAP = 8 # Hot rinsing water
CLD = 4 # Cooling water

# Thermistors number
T_input = 1 # Entrée
T_intake = 2 # Juste après la pompe
T_warranty = 3 # Garantie sortie serpentin long
T_heating = 4 # If no OneWire, this will be T_sp9b
T_extra = None

inputPressure = None
inputPressureFlag = None

In_Emergency = None
In_Level1 = None
In_Level2 = None

In_Green = None
Out_Green = None

In_Yellow = None
Out_Yellow = None

In_Red = None
Out_Red = None # TXD, SYS_LED for Odroid?

Out_Buzzer = None

OW_input = None # Entrée
OW_output = None # Sortie
OW_warranty = None # Garantie sortie serpentin long
OW_heating = None # If no OneWire, this will be T_sp9b
OW_extra = None

A_input = None # Entrée de la chauffe
A_intake = None # Entrée du pasteurisateur
A_warranty = None # Garantie sortie serpentin long
A_heating = None # If no OneWire, this will be T_sp9b
A_extra = None

B_input = None # Entrée de la chauffe
B_intake = None # Entrée du pasteurisateur
B_warranty = None # Garantie sortie serpentin long
B_heating = None # If no OneWire, this will be T_sp9b
B_extra = None

C_input = None # Entrée de la chauffe
C_intake = None # Entrée du pasteurisateur
C_warranty = None # Garantie sortie serpentin long
C_heating = None # If no OneWire, this will be T_sp9b
C_extra = None

beta_input = None # Entrée de la chauffe
beta_intake = None # Entrée du pasteurisateur
beta_warranty = None # Garantie sortie serpentin long
beta_heating = None # If no OneWire, this will be T_sp9b
beta_extra = None

ohm25_input = None # Entrée de la chauffe
ohm25_intake = None # Entrée du pasteurisateur
ohm25_warranty = None # Garantie sortie serpentin long
ohm25_heating = None # If no OneWire, this will be T_sp9b
ohm25_extra = None

vol_intake = None
vol_input = None
vol_warranty = None
vol_heating = None
vol_heating_DEFAULT = 23790 # en mL
vol_extra = None
vol_total = None

power_heating = None # Heating electricity power consumption (and energy released)
power_heating_DEFAULT = 2500 # en Watts
power_dummy = None # do not use!

#holding_length = 8820 #mm for 150L/h, 11757 mm for 200L/h
holding_volume = 625 #mL for 150L/h, 833mL for 200L/h
dynamicRegulation = False

MICHA_device = None
thermistors_voltage = 4.087 # Surprisingly not 4.095
thermistors_Rtop = 2000.0 # Divider bridge to measure temperature (top resistor). Should include 2 ohms for the transistor of stimulation power

hostname = socket.gethostname()
machine = platform.machine()
operatingSystem = platform.system()
print (hostname+" / "+machine)

HARDdirectory = os.path.join(os.path.dirname(os.path.abspath(__file__)),"configs")

serialNumber = ""
configCode = ""
prefixHostname = "PASTO-"
configFile = ""
configParsing = None
MICHA_version = None
reversedPump = False
tubing = None

def string_mL(anItem_param):
    if not anItem_param[1]:
        return None
    try:
        fd = float(anItem_param[1])
        if fd < 100.0: # Liters and not milliters
            return fd * 1000.0
        else:
            return fd
    except:
        print((anItem_param[0] + ': ' + anItem_param[1] + ' is not decimal.'))
        return None

if hostname and hostname.startswith(prefixHostname):
    i = hostname.index('-',len(prefixHostname))
    if i < len(prefixHostname):
        print ("A '-'(dash) must precede the pasteurizer serial number in the hostname")
        configCode = "DEV"
        serialNumber = "0"
    else:
        configCode = hostname[len(prefixHostname):i]
        serialNumber = hostname[i:]
else:
    print ("hostname must begin by pasto")
    configCode = "DEV"
    serialNumber = "0"

configFile = os.path.join(HARDdirectory,configCode+'.ini')
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
            opt = anItem[0].lower()
            if opt == 'type':
                processor = anItem[1].lower()
                if processor == "rpi" and not localGPIOtype:
                    localGPIOtype = 'pigpio'
                elif processor == "odroid" and not localGPIOtype:
                    localGPIOtype = "gpio"
            elif opt == 'gpio':
                localGPIOtype = anItem[1].lower()
            elif opt == 'tubing':
                tubing = anItem[1].lower()
            elif opt == 'volume':
                vol_total = string_mL(anItem)
            #elif opt == 'pasteurization':
            #    vol_pasteurization = string_mL(anItem)
            elif opt == 'holding': #holding tube volume in mL
                holding_volume = string_mL(anItem)
            elif opt == 'regulation':
                dynamicRegulation = anItem[1].lower() == "dynamic"
            elif opt == 'pump':
                try:
                    pumpMaxRPM = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            else:
                print('[system] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: type, pigpio, gpio, tubing, volume, pasteurization, regulation')

        if localGPIOtype == "pigpio":
            import pigpio
            localGPIO = pigpio.pi() # Uses BCM numbering for pins...
            gpio_PUD_UP = pigpio.PUD_UP
            gpio_INPUT = pigpio.INPUT
            gpio_OUTPUT = pigpio.OUTPUT
            In_Green = 22
            Out_Green = 23
            In_Yellow = 27
            Out_Yellow = 24
            In_Red =  13
            Out_Red = None # TXD, SYS_LED for Odroid?
            Out_Buzzer = 26
        elif localGPIOtype and localGPIOtype.startswith("gpio"):
            try:
                if processor == "odroid":
                    import Odroid.GPIO as GPIO
                    #import odroid_wiringpi as GPIO
                    #GPIO.wiringPiSetupGpio()
                else:
                    import RPi.GPIO as GPIO
            except RuntimeError:
                print("Error importing RPi or Odroid.GPIO.")
                traceback.print_exc()
            #print("GPIO BCM")
            GPIO.setmode(GPIO.BCM)
            localGPIO = GPIO # Uses BOARD numbering for pins...
            gpio_PUD_UP = GPIO.PUD_UP
            gpio_INPUT = GPIO.IN
            #gpio_INPUT = GPIO.INPUT
            gpio_OUTPUT = GPIO.OUT
            #gpio_OUTPUT = GPIO.OUTPUT
            if processor == "odroid":
                In_Green = 483 # board 15 # BCM 22
                Out_Green = 476 # board 16 # BCM 23
                In_Yellow = 480 # board 13 # BCM 27
                Out_Yellow = 477 # board 18 # BCM 24
                In_Red = 482 # board 33 # BCM 13
                Out_Red = 432 # board 36 # was TXD, SYS_LED for Odroid
                Out_Buzzer = 495 # board 35 # BCM 26
                In_Emergency = - MICHApast.EMERGENCY_STOP_REG # Negative to signal indirect read through MICHA
                In_Level1 = - MICHApast.LEVEL_SENSOR1_REG # Negative to signal indirect read through MICHA
                In_Level2 = - MICHApast.LEVEL_SENSOR2_REG # Negative to signal indirect read through MICHA
            else:
                In_Green = 22 # board 15 # BCM 22
                Out_Green = 23 # board 16 # BCM 23
                In_Yellow = 27 # board 13 # BCM 27
                Out_Yellow = 24 # board 18 # BCM 24
                In_Red = 13 # board 33 # BCM 13
                Out_Red = None # TXD, SYS_LED for Odroid
                Out_Buzzer = 26 # board 35 # BCM 26

    if 'emergency' in configParsing.sections():
        for anItem in configParsing.items('emergency'):
            opt = anItem[0].lower()
            if opt == 'input':
                try:
                    In_Emergency = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            elif opt == 'output':
                try:
                    Out_Emergency = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            else:
                print('[emergency] '+opt + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'level' in configParsing.sections():
        for anItem in configParsing.items('level'):
            opt = anItem[0].lower()
            if opt == '1':
                try:
                    In_Level1 = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            elif opt == '2':
                try:
                    In_Level2 = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            else:
                print('[level] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: 1, 2')

    if 'green' in configParsing.sections():
        for anItem in configParsing.items('green'):
            opt = anItem[0].lower()
            if opt == 'input':
                try:
                    In_Green = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 'output':
                try:
                    Out_Green = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[green] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'yellow' in configParsing.sections():
        for anItem in configParsing.items('yellow'):
            opt = anItem[0].lower()
            if opt == 'input':
                try:
                    In_Yellow = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 'output':
                try:
                    Out_Yellow = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[yellow] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'red' in configParsing.sections():
        for anItem in configParsing.items('red'):
            opt = anItem[0].lower()
            if opt == 'input':
                try:
                    In_Red = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 'output':
                try:
                    Out_Red = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[red] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'buzzer' in configParsing.sections():
        for anItem in configParsing.items('buzzer'):
            opt = anItem[0].lower()
            if opt == 'output':
                try:
                    Out_Buzzer = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[buzzer] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: output')

    if 'user' in configParsing.sections():
        for anItem in configParsing.items('user'):
            opt = anItem[0].lower()
            if opt == 'lang':
                ml.setLang(anItem[1].lower())
            elif opt == 'name' and anItem[1]:
                owner.owner.name = anItem[1]
            elif opt == 'address' and anItem[1]:
                owner.owner.address = anItem[1]
            elif opt == 'city' and anItem[1]:
                owner.owner.city = anItem[1]
            elif opt == 'email' and anItem[1]:
                owner.owner.email = anItem[1]
            else:
                print('[user] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: lang')

    if 'MICHA' in configParsing.sections():
        for anItem in configParsing.items('MICHA'):
            opt = anItem[0].lower()
            if opt == 'device':
                MICHA_device = anItem[1]
            elif opt == 'version':
                try:
                    MICHA_version = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[MICHA] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: device, version')
        if MICHA_version >= 40:
            import MICHA40past
            io = MICHA40past.Micha4(MICHA_device)
            reversedPump = (MICHA_version >= 50)
        else:
            io = MICHApast.Micha(MICHA_device)
            reversedPump = True

    def parseThermistor (section,T):

        OW = None
        vol = None
        beta = None
        ohm25 = None
        A = None
        B = None
        C = None
        POWER = None
        if section in configParsing.sections():
            for currItem in configParsing.items(section):
                opt = currItem[0].lower()
                if opt == 'port':
                    try:
                        T = int(currItem[1])
                    except:
                        print((currItem[0] + ': ' + currItem[1] + ' is not decimal.'))
                elif opt == 'power':
                    try:
                        POWER = int(currItem[1])
                    except:
                        print((currItem[0] + ': ' + currItem[1] + ' is not decimal.'))
                elif opt == 'onewire':
                    OW = currItem[1]
                elif opt == 'volume':
                    vol = string_mL(currItem)
                elif opt == 'beta':
                    beta = float(currItem[1])
                elif opt == 'ohm25':
                    ohm25 = float(currItem[1])
                elif opt == 'a':
                    A = float(currItem[1])
                elif opt == 'b':
                    B = float(currItem[1])
                elif opt == 'c':
                    C = float(currItem[1])
                else:
                    print('['+section+'] '+currItem[0] + ': ' + currItem[1] + ' unknown option. Valid: port, onewire, volume, beta, ohm25, a, b, c, power')
        return (T,OW,vol,beta,ohm25,A,B,C,POWER)

    (T_heating, OW_heating, vol_heating, beta_heating, ohm25_heating, A_heating, B_heating, C_heating, power_heating) = parseThermistor('heating', T_heating)
    if not vol_heating:
        vol_heating = vol_heating_DEFAULT # milliLitres dans le bassin de chauffe
    if not power_heating:
        power_heating = power_heating_DEFAULT # watts to heat the tank...

    (T_input, OW_input, vol_input, beta_input, ohm25_input, A_input, B_input, C_input, power_dummy) = parseThermistor('input', T_input)
    (T_intake, OW_intake, vol_intake, beta_intake, ohm25_intake, A_intake, B_intake, C_intake, power_dummy) = parseThermistor('intake', T_intake)
    (T_warranty, OW_warranty, vol_warranty, beta_warranty, ohm25_warranty, A_warranty, B_warranty, C_warranty, power_dummy) = parseThermistor('warranty', T_warranty)
    (T_extra, OW_extra, vol_extra, beta_extra, ohm25_extra, A_extra, B_extra, C_extra, power_dummy) = parseThermistor('extra', T_extra)

    if 'Rmeter' in configParsing.sections():
        import RMETERpast
        #BCM (pigpio) configuration
        R_S1 = 25
        R_S2 = 6
        R_S3 = 5
        R_polarity = 16
        for anItem in configParsing.items('Rmeter'):
            opt = anItem[0].lower()
            if opt == 's1':
                try:
                    R_S1 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 's2':
                try:
                    R_S2 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 's3':
                try:
                    R_S2 = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif opt == 'polarity':
                try:
                    R_polarity = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[Rmeter] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire')

        Rmeter = RMETERpast.R_Meter(S1=R_S1, S2=R_S2, S3=R_S3, polarityIO=R_polarity) # bus=0, spi_channel=0, bus2=1, spi_channel2=0

if MICHA_device:
    thermistors_voltage = MICHApast.VOLTAGE_REF
    
    # Heating tanks
    DAC1 = MICHApast.TANK1_REG # C: Pasteurization
    DAC2 = MICHApast.TANK2_REG # T: Temperization

    # Dump Valve
    DMP_open = MICHApast.VALVE1_POW_REG
    DMP_close = MICHApast.VALVE1_DIR_REG

    # Solenoids to control water inputs
    TAP = MICHApast.SOL_HOT_REG # Hot rinsing water
    CLD = MICHApast.SOL_COLD_REG # Cooling water

    if MICHA_version >= 40:
        inputPressure = MICHApast.PRESS_SENSOR_REG
        inputPressureFlag = MICHApast.PRESS_FLAG_REG

elif localGPIOtype and localGPIOtype.startswith("gpio"):
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
    elif io:
        # All ExpanderPI GPIO in input mode:
        io.set_port_direction(0, 0xFF)
        io.set_port_direction(1, 0xFF)
        # We do not leave output floating because we are not sure we have the right pull up always there...
        #io.set_port_direction(0, 0xFF)
        #io.set_port_direction(1, 0xFF)

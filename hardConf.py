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
OW_output= None # Sortie
OW_warranty = None # Garantie sortie serpentin long
OW_heating = None # If no OneWire, this will be T_sp9b
OW_extra = None

vol_intake = None
vol_input = None
vol_warranty = None
vol_heating = None
vol_total = None

vol_pasteurization = None

MICHA_device = None
thermistors_voltage = 4.087 # Surprisingly not 4.095
thermistors_Rtop = 2000.0 # Divider bridge to measure temperature (top resistor). Should include 2 ohms for the transistor of stimulation power

hostname = socket.gethostname()
machine = platform.machine()
print (hostname+" / "+machine)

HARDdirectory = os.path.join(os.path.dirname(os.path.abspath(__file__)),"configs")

serialNumber = ""
configCode = ""
prefixHostname = "PASTO-"
configFile = ""
configParsing = None
MICHA_version = None
reversedPump = False
tubing=None

def string_mL(anItem):
    if not anItem[1]:
        return None
    try:
        fd = float(anItem[1])
        if (fd < 100.0): # Liters and not milliters
            return fd * 1000.0
        else:
            return fd
    except:
        print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
        return None

if hostname and hostname.startswith(prefixHostname):
    i = hostname.index('-',len(prefixHostname))
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
                    localGPIOtype = "gpio"
            elif anItem[0].lower() == 'gpio':
                localGPIOtype = anItem[1].lower()
            elif anItem[0].lower() == 'tubing':
                tubing = anItem[1].lower()
            elif anItem[0].lower == 'volume':
                vol_total = string_mL(anItem)
            elif anItem[0].lower == 'pasteurization':
                vol_pasteurization = string_mL(anItem)
            else:
                print('[system] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: type, pigpio, gpio, tubing, volume, pasteurization')

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
            if anItem[0].lower() == 'input':
                try:
                    In_Emergency = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            elif anItem[0].lower() == 'output':
                try:
                    Out_Emergency = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            else:
                print('[emergency] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'level' in configParsing.sections():
        for anItem in configParsing.items('level'):
            if anItem[0].lower() == '1':
                try:
                    In_Level1 = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            elif anItem[0].lower() == '2':
                try:
                    In_Level2 = int(anItem[1])
                except:
                    print(anItem[0] + ': ' + anItem[1] + ' is not decimal.')
            else:
                print('[level] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: 1, 2')

    if 'green' in configParsing.sections():
        for anItem in configParsing.items('green'):
            if anItem[0].lower() == 'input':
                try:
                    In_Green = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 'output':
                try:
                    Out_Green = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[green] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'yellow' in configParsing.sections():
        for anItem in configParsing.items('yellow'):
            if anItem[0].lower() == 'input':
                try:
                    In_Yellow = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 'output':
                try:
                    Out_Yellow = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[yellow] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'red' in configParsing.sections():
        for anItem in configParsing.items('red'):
            if anItem[0].lower() == 'input':
                try:
                    In_Red = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower() == 'output':
                try:
                    Out_Red = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[red] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: input, output')

    if 'buzzer' in configParsing.sections():
        for anItem in configParsing.items('buzzer'):
            if anItem[0].lower() == 'output':
                try:
                    Out_Buzzer = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            else:
                print('[buzzer] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: output')

    if 'user' in configParsing.sections():
        for anItem in configParsing.items('user'):
            if anItem[0].lower() == 'lang':
                ml.setLang(anItem[1].lower())
            elif anItem[0].lower() == 'name' and anItem[1]:
                owner.owner.name = anItem[1]
            elif anItem[0].lower() == 'address' and anItem[1]:
                owner.owner.address = anItem[1]
            elif anItem[0].lower() == 'city' and anItem[1]:
                owner.owner.city = anItem[1]
            elif anItem[0].lower() == 'email' and anItem[1]:
                owner.owner.email = anItem[1]
            else:
                print('[user] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: lang')

    if 'MICHA' in configParsing.sections():
        for anItem in configParsing.items('MICHA'):
            if anItem[0].lower() == 'device':
                MICHA_device = anItem[1]
            elif anItem[0].lower() == 'version':
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

    if 'heating' in configParsing.sections():
        for anItem in configParsing.items('heating'):
            if anItem[0].lower() == 'port':
                try:
                    T_heating = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_heating = anItem[1]
            elif anItem[0].lower == 'volume':
                vol_heating = string_mL(anItem)
            else:
                print('[heating] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire, volume')

    if 'extra' in configParsing.sections():
        for anItem in configParsing.items('extra'):
            if anItem[0].lower() == 'port':
                try:
                    T_extra = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_extra = anItem[1]
            elif anItem[0].lower == 'volume':
                vol_total = string_mL(anItem)
            else:
                print('[extra] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire, volume')

    if 'input' in configParsing.sections():
        for anItem in configParsing.items('input'):
            if anItem[0].lower() == 'port':
                try:
                    T_input = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_input = anItem[1]
            elif anItem[0].lower == 'volume':
                vol_input = string_mL(anItem)
            else:
                print('[input] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire, volume')

    if 'intake' in configParsing.sections():
        for anItem in configParsing.items('intake'):
            if anItem[0].lower() == 'port':
                try:
                    T_intake = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_output = anItem[1]
            elif anItem[0].lower == 'volume':
                vol_intake = string_mL(anItem)
            else:
                print('[intake] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire, volume')

    if 'warranty' in configParsing.sections():
        for anItem in configParsing.items('warranty'):
            if anItem[0].lower() == 'port':
                try:
                    T_warranty = int(anItem[1])
                except:
                    print((anItem[0] + ': ' + anItem[1] + ' is not decimal.'))
            elif anItem[0].lower == 'onewire':
                OW_warranty = anItem[1]
            elif anItem[0].lower == 'volume':
                vol_warranty = string_mL(anItem)
            else:
                print('[warranty] '+anItem[0] + ': ' + anItem[1] + ' unknown option. Valid: port, onewire, volume')

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
        ## We do not leave output floating because we are not sure we have the right pull up always there...
        ##io.set_port_direction(0, 0xFF)
        ##io.set_port_direction(1, 0xFF)


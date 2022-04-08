#!/usr/bin/python3
# -*- coding: utf-8 -*-
import socket
import platform
import term
import traceback
import ml
import MICHApast

hostname = socket.gethostname()
machine = platform.machine()

Raspberry = False
Odroid = False
io = None
adc = None
pi = None
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
T_heatout = 2 # Sortie
T_sp9 = 3 # Garantie sortie serpentin long
T_sp9b = 4 # Garantie entrée serpentin court
T_heating = None # If no OneWire, this will be T_sp9b

MICHA_device = None
thermistors_voltage = 4.087 # Surprisingly not 4.095
thermistors_Rtop = 2000.0 # Divider bridge to measure temperature (top resistor). Should include 2 ohms for the transistor of stimulation power

print (hostname+" / "+machine)

# One Wire sensors address
if hostname == "pastOnomic":
    Raspberry = True
    MICHA_device = "/dev/serial0"
    io = MICHApast.Micha(MICHA_device)
    OW_heating = "28.CC3EAF040000"  # Extra: typiquement sortie du refroidissement rapide
    OW_extra = None # "28.AA5659501401"  # Bain de tempérisation (sortie) régulé en refroidissement   28.FFDD64931504 est mort (FFDD)
elif hostname == "pastoB04001":
    Odroid = True
    import MICHA40past
    MICHA_device = "/dev/ttyS1"
    pumpON = 1
    pumpOFF = 0
    pumpDirection = 14
    io = MICHA40past.Micha4(MICHA_device)
    T_heating = T_sp9b
    OW_heating = None
    OW_extra = None # "28.AA5659501401"  # Bain de tempérisation (sortie) régulé en refroidissement   28.FFDD64931504 est    # OW_temper = "28.AABA43501401"  # Bain de chauffe
    ml.setLang('f')
elif hostname == "christophe-Latitude-E7440":    
    #OW_temper = "28.A6156B070000"  # Extra: typiquement sortie du refroidissement rapide
    OW_heating = "28.AA5E36501401"  # Bain de chauffe
    OW_extra = "28.CC3EAF040000"  # Bain de tempérisation (sortie) régulé en refroidissement
    ml.setLang('e')
# else keep variables undefined...


if Raspberry:
    import pigpio
    pi = pigpio.pi() # Uses BCM numbering for pins...

if Odroid:
    import Odroid.GPIO as GPIO
    GPIO.setmode(GPIO.BOARD)
    pi = GPIO # Uses BCM numbering for pins...

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

    # Thermistors number = MODBUS register numbers !
    T_input = 1 # Entrée
    T_heatout = 3 # Sortie
    T_sp9 = 2 # Garantie sortie serpentin long
    T_sp9b = 4 # Garantie entrée serpentin court
    
elif Raspberry:
    import RMETERpast
    Rmeter = RMETERpast.R_Meter() # bus=0, spi_channel=0, bus2=1, spi_channel2=0, S1=25, S2=6, S3=5

    # We use "pigpio" now, always with BCM numbering...
    # import RPi.GPIO as GPIO
    # GPIO.setmode(GPIO.BOARD)
    # GPIO.setwarnings(False)

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
elif Odroid:
    pass
else:
    print("SIMULATION car pas sur un RaspberryPi")

def close():
    if MICHA_device:
        io.close()
    elif Raspberry:
        # All ExpanderPI GPIO in input mode:
        io.set_port_direction(0, 0xFF)
        io.set_port_direction(1, 0xFF)
        ## We do not leave output floating because we are not sure we have the right pull up always there...
        ##io.set_port_direction(0, 0xFF)
        ##io.set_port_direction(1, 0xFF)
    if pi and Raspberry:
        pi.stop()


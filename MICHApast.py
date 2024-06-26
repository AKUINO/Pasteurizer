#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This code allows to communicate with the MICHA board in a pasteurizer configuration. It can be use as:
#     - a library to communicate with the MICHA board using another main code file
#     - a standalone code to test the I/O of the MICHA board

import traceback
from serial import Serial, PARITY_NONE
from umodbus.client.serial import rtu # pip install uModbus
import time

SLAVE_ID = 1
MODBUS_RETRY = 2
WRITE_RETRY = 5
DELAY_RETRY = 0.05

VOLTAGE_REF = 2.497 # value of the excitement voltage reference
THERMI_WIRE = 0.6 # value of the twin wire resistor

# Registre configuration

# coils
THERMIS_POW_REG             = 0x00  # 4.0 register which stores the thermistor power state
LEVEL1_FLAG_REG             = 0x01  # 4.0 register which stores the default value of the level sensor 1 when unplugged
LEVEL2_FLAG_REG             = 0x02  # 4.0 register which stores the default value of the level sensor 2 when unplugged
PRESS_FLAG_REG              = 0x03  # 4.0 register which stores the flag which enables/disables the pressure sensor management

PUMP_DIR_REG                = 0x10  # register which stores the pump direction
PUMP_POW_REG                = 0x11  # register which stores the pump power state
TANK1_REG                   = 0x20  # register which stores the tank 1 state
TANK2_REG                   = 0x21  # register which stores the tank 2 state
SOL_HOT_REG                 = 0x30  # register which stores the hot water solenoid state
SOL_COLD_REG                = 0x31  # register which stores the cold water solenoid state
VALVE1_POW_REG              = 0x32  # register which stores the valve 1 power state; OPEN with chinese valve
VALVE2_POW_REG              = 0x34  # register which stores the valve 2 power state
VALVE1_DIR_REG              = 0x33  # register which stores the valve 1 direction; CLOSE with chinese valve
VALVE2_DIR_REG              = 0x35  # register which stores the valve 2 direction
BOOT_FLAG_REG               = 0x40  # register which stores the boot state
DEBUG_FLAG_REG              = 0x41  # register which stores the state of the debug mode

# discrete registers
LEVEL_SENSOR1_REG           = 0x01  # 4.0 register which stores the state of the input level sensor (1 for water)
LEVEL_SENSOR2_REG           = 0x02  # 4.0 register which stores the state of the output level sensor (1 for water)
EMERGENCY_STOP_REG          = 0x10  # 4.0 register which stores the state of  the emergency stop button (0 for active emergency stop)

# input registers
GEN_STATE_REG               = 0x00  # register which stores the general state of the system
THERMI1_REG                 = 0x01  # register which stores the thermistor 1 value (0 - 4095)
THERMI2_REG                 = 0x02  # register which stores the thermistor 2 value (0 - 4095)
THERMI3_REG                 = 0x03  # register which stores the thermistor 3 value (0 - 4095)
THERMI4_REG                 = 0x04  # register which stores the thermistor 4 value (0 - 4095)
PRESS_SENSOR_REG            = 0x18  # 4.0 register which stores the pressure sensor value (0 (low pressure) - 4095 (high pressure))
PRESS_SENSOR_MIN_REG        = 0x19  # 4.0 register which stores the pressure sensor value (0 (low pressure) - 4095 (high pressure))
PRESS_SENSOR_MAX_REG        = 0x1A  # 4.0 register which stores the pressure sensor value (0 (low pressure) - 4095 (high pressure))
PUMP_ERR_REG                = 0x10  # register which stores the error code returned by the pump regulator
PUMP_SERVO_PERIODMAX_REG    = 0x11  # register which stores the max period of the servo signal returned by the pump
PUMP_SERVO_PERIODMIN_REG    = 0x12  # register which stores the min period of the servo signal returned by the pump
PUMP_SERVO_PERIODAVG_REG    = 0x13  # register which stores the period average of the servo signal returned by the pump (on some time)
PUMP_SERVO_PERIODSTDDEV_REG = 0x14  # register which stores the period standard deviation of the servo signal returned by the pump  (on some time)
ERROR_CODE_REG              = 0x20  # register which stores the general error codes

# holding registers
ID_REG                      = 0x00  # register which stores the modbus ID
PUMP_SPEED_REG              = 0x10  # register which stores the pump speed
PUMP_SPEED_INC_REG          = 0x11  # register which stores the increasing/decreasing value of the pump frequency
#PUMP_SPIN_RATE_REG         = 0x12  # register which stores the pump spining rate approved
PUMP_SERVO_PULSES_REG       = 0x13  # register which stores the pulse count of the servo signal returned by the pump (on some time)

# Class to manage the MICHA board
class Micha:
    def __init__(self,device='/dev/serial0'):
        self.device = device
        self.boot_flag = 1
        self.thermi = 0
        self.pump_speed = 0
        self.pump_dir = 0
        self.pump_power = 0
        self.tank1 = 0
        self.tank2 = 0
        self.sol_hot = 0
        self.sol_cold = 0
        self.valve1_power = 0
        self.valve1_dir = 0
        self.valve2_power = 0
        self.valve2_dir = 0
        self.general_state = 0
        self.error_code = 0
        self.debug_flag = 0
        self.busy = False
        self.port = None
    
    # Configuration and starting of the modbus communication
    def get_serial_port(self):
        while self.busy:
            time.sleep(DELAY_RETRY)
        self.busy = True
        while not self.port: # In case of error, we reset the access to the ModBus
            try:
                """Return a serial.Serial instance which is ready to use with a RS485 adaptor."""
                self.port = Serial(port=self.device, baudrate=19200, parity=PARITY_NONE, stopbits=1, bytesize=8, timeout=DELAY_RETRY)
            except:
                #traceback.print_exc()
                print("MICHA open failed\r")
                self.port = None
                time.sleep(DELAY_RETRY) # Do not retry too fast...
        return self.port

    def close_serial_port(self):
        if self.port:
            try:
                self.port.close()
            except:
                pass
            self.port = None
        self.busy = False

    def close (self):
        self.close_serial_port()

    def release_serial_port(self):
        #self.busy = False
        self.close_serial_port()
        
    def read_pin(self,reg): # read a single coil register at reg address
        i = 0
        while i < MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                message = rtu.read_coils(SLAVE_ID, reg, 1)
                #print("READ mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                response = response[0]
                self.release_serial_port()
                return response
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read pin %d failed\r"%reg)
                i = i+1
                #time.sleep(0.1)
        return None

    def write_pin(self,reg,val): # write val in a single coil register at reg address
        i = 0
        while i < WRITE_RETRY:
            try:
                serial_port = self.get_serial_port()                
                message = rtu.write_single_coil(SLAVE_ID, reg, val)
                #print("WRITE mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response
            except:
                #traceback.print_exc()
                self.close_serial_port()
                #print("MICHA write pin %d=%d failed\r"%(reg,val))
                i = i+1
                #time.sleep(0.1)
        return None

    def read_input(self,reg): # read a single input register at reg address
        i = 0
        while i < MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()            
                message = rtu.read_input_registers(SLAVE_ID, reg, 1)
                #print("INPUT mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read input %d failed\r"%reg)
                i = i+1
                #time.sleep(0.1)
        return None

    def read_holding(self,reg): # read a single holding register at reg address
        i = 0
        while i < MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                message = rtu.read_holding_registers(SLAVE_ID, reg, 1)
                #print("HOLDING mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read holding %d failed\r"%reg)
                i = i+1
                #time.sleep(0.1)
        return None

    def write_holding(self,reg, val): # write val in the holding register at reg address
        i = 0
        while i < WRITE_RETRY:
            try:
                serial_port = self.get_serial_port()            
                message = rtu.write_single_register(SLAVE_ID, reg, val)
                #print("WRITE HOLDING mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA write holding %d=%d failed\r"%(reg,val))
                i = i+1
                #time.sleep(0.1)
        return None

    def get_boot_flag(self): # to get the boot state
        self.boot_flag = self.read_pin(BOOT_FLAG_REG)
        return self.boot_flag
    
    def set_boot_flag(self,flag=0): # to set the boot state
        self.boot_flag = flag
        response = self.write_pin(BOOT_FLAG_REG, flag)
        return response
    
    def get_thermi(self, th=0): # to get the thermistor value, returns the thermistor value
        self.thermi = th
        i=0
        while i < MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()

                message = None
                response = None
                if self.thermi==0: # get the value of all the thermistors
                    message = rtu.read_input_registers(SLAVE_ID, THERMI1_REG, 4)
                elif self.thermi==1: # get the thermistor 1 value
                    message = rtu.read_input_registers(SLAVE_ID, THERMI1_REG, 1)
                elif self.thermi==2: # get the thermistor 2 value
                    message = rtu.read_input_registers(SLAVE_ID, THERMI2_REG, 1)
                elif self.thermi==3: # get the thermistor 3 value
                    message = rtu.read_input_registers(SLAVE_ID, THERMI3_REG, 1)
                elif self.thermi==4: # get the thermistor 4 value
                    message = rtu.read_input_registers(SLAVE_ID, THERMI4_REG, 1)
                else:
                    print("ERROR: no thermistor was found at this value")
                if message:
                   response = rtu.send_message(message, serial_port)
                
                self.release_serial_port()
                return response
            except:
                traceback.print_exc()
                self.close_serial_port()
                i = i+1
                #time.sleep(0.1)
    
        return None
    
    def set_pump_power(self,power=0): # to set the power of the pump
        self.pump_power = power
        response = self.write_pin(PUMP_POW_REG, power)
        return response

    def set_pump_speed(self,speed=0): # to set the speed of the pump
        self.pump_speed = speed
        return self.write_holding(PUMP_SPEED_REG, speed)
    
    def set_pump_dir(self, direction=0): # to set the direction of the pump
        self.pump_dir = direction
        response = self.write_pin(PUMP_DIR_REG, direction)
        return response
    
    def get_pump_power(self): # to get the power state of the pump (stored in the register), returns the pump power state
        self.pump_power = self.read_pin(PUMP_POW_REG)
        return self.pump_power
    
    def get_pump_dir(self): # to get the direction state of the pump (stored in the register), returns the pump direction value
        self.pump_dir = self.read_pin(PUMP_DIR_REG)
        return self.pump_dir
    
    def get_pump_speed(self): # to get the speed of the pump (stored in the register), returns the pump speed
        self.pump_speed = self.read_holding(PUMP_SPEED_REG)
        return self.pump_speed
    
    def get_pump_error(self): # to get the error code returned by the pump regulator, returns the pump error code
        return self.read_input(PUMP_ERR_REG)
            
    def get_pump_servo(self): # to get the pump speed returned by the servo of the pump
        i=0
        while i < MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                
                message = rtu.read_input_registers(SLAVE_ID, PUMP_SERVO_PERIODMAX_REG , 3)
                response = rtu.send_message(message, serial_port)
                
                message = rtu.read_holding_registers(SLAVE_ID, PUMP_SERVO_PULSES_REG , 1)
                response2 = rtu.send_message(message, serial_port)
                response.append(response2[0])
                
                # Auto re-init every second...
                #message = rtu.write_single_register(SLAVE_ID, PUMP_SERVO_PULSES_REG , 0)
                #response3 = rtu.send_message(message, serial_port)
                
                self.release_serial_port()
                return response
            except:
                traceback.print_exc()
                self.close_serial_port()
                i = i+1
                #time.sleep(0.1)
        return None
    
    def set_tank1(self,state=0): # to set the state of the tank 1
        self.tank1 = state
        response = self.write_pin(TANK1_REG, state)
        return response

    def set_tank2(self,state=0): # to set the state of the tank 2
        self.tank2 = state
        response = self.write_pin(TANK2_REG, state)
        return response
    
    def get_tank1(self): # to get the state of the tank 1 (stored in the register)
        self.tank1 = self.read_pin(TANK1_REG)
        return self.tank1
    
    def get_tank2(self): # to get the state of the tank 2 (stored in the register)
        self.tank2 = self.read_pin(TANK2_REG)
        return self.tank2
    
    def set_sol_hot(self,state=0): # to set the state of the hot water solenoid
        self.sol_hot = state
        response = self.write_pin(SOL_HOT_REG, state)
        return response
    
    def set_sol_cold(self,state=0): # to set the state of the cold water solenoid
        self.sol_cold = state
        response = self.write_pin(SOL_COLD_REG, state)
        return response
    
    def get_sol_hot(self): # to get the state of the hot water solenoid (stored in the register)
        self.sol_hot = self.read_pin(SOL_HOT_REG)
        return self.sol_hot
    
    def get_sol_cold(self): # to get the state of the cold water solenoid (stored in the register)
        self.sol_cold = self.read_pin(SOL_COLD_REG)
        return self.sol_cold
    
    def set_valve1_power(self,power=0): # to set the power state of the valve 1
        self.valve1_power = power
        response = self.write_pin(VALVE1_POW_REG, power)
        return response
    
    def set_valve2_power(self,power=0): # to set the power state of the valve 2
        self.valve2_power = power
        response = self.write_pin(VALVE2_POW_REG, power)
        return response
    
    def get_valve1_power(self): # to get the power state of the valve 1 (stored in the register)
        self.valve1_power = self.read_pin(VALVE1_POW_REG)
        return self.valve1_power
    
    def get_valve2_power(self): # to get the power state of the valve 2 (stored in the register)
        self.valve2_power = self.read_pin(VALVE2_POW_REG)
        return self.valve2_power
    
    def set_valve1_dir(self, direction=0): # to set the direction of the valve 1
        self.valve1_dir = direction
        response = self.write_pin(VALVE1_DIR_REG, direction)
        return response
    
    def set_valve2_dir(self, direction=0): # to set the direction of the valve 2
        self.valve2_dir = direction
        response = self.write_pin(VALVE2_DIR_REG, direction)
        return response
    
    def get_valve1_dir(self): # to get the direction of the valve 1 (stored in the register)
        self.valve1_dir = self.read_pin(VALVE1_DIR_REG)
        return self.valve1_dir

    def get_valve2_dir(self): # to get the direction of the valve 2 (stored in the register)
        self.valve2_dir = self.read_pin(VALVE2_DIR_REG)
        return self.valve2_dir

    def get_general_state(self): # to get the general state of the system (stored in the register)
        self.general_state = self.read_input(GEN_STATE_REG)
        return self.general_state
    
    def get_error_code(self): # to get the general error code
        self.error_code = self.read_input(ERROR_CODE_REG)
        return self.error_code

    def get_debug_flag(self):  # to get the debug state
        self.debug_flag = self.read_pin(DEBUG_FLAG_REG)
        return self.debug_flag

    def set_debug_flag(self, flag=0):  # to set the debug state
        self.debug_flag = flag
        response = self.write_pin(DEBUG_FLAG_REG, flag)
        return response
    
# test section
if __name__ == "__main__":
    
    def boot_monitoring():
        if pasto.get_boot_flag():
            print("\n\nTHE DEVICE HAS REBOOTED!")
            pasto.set_boot_flag()
        
        return 0
    
    def menu_choice(mini,maxi):
        choice_made = '-1'
        
        while (int(choice_made)<mini or int(choice_made)>maxi):
            choice_made = input("Choose an option: ")
            
            boot_monitoring()
                
            if (int(choice_made)<mini or int(choice_made)>maxi):
                print("ERROR: incorrect choice. Your choice must be [{}:{}]".format(mini,maxi))
        
        return choice_made

    # A sub-menu to manage the thermistors
    def subMenu_thermis():
        """Display a sub-menu to manage the thermistors."""
        choice_made = '-1'
        
        while choice_made!='0':
            print("########## THERMISTORS SUB-MENU ##########")
            print(" 1 - Get the thermistor 1 value\n",
                  "2 - Get the thermistor 2 value\n",
                  "3 - Get the thermistor 3 value\n",
                  "4 - Get the thermistor 4 value\n",
                  "5 - Get teh value of all the thermistors\n",
                  "0 - Back\n")
            
            choice_made = menu_choice(0,5)
            print("\n")
            
            # If the choice is valid
            if choice_made!='0':
                thermi1 = pasto.get_thermi(1)[0]
                thermi2 = pasto.get_thermi(2)[0]
                thermi3 = pasto.get_thermi(3)[0]
                thermi4 = pasto.get_thermi(4)[0]
                
                thermi1_mV = (VOLTAGE_REF*thermi1/4096)*1000
                thermi2_mV = (VOLTAGE_REF*thermi2/4096)*1000
                thermi3_mV = (VOLTAGE_REF*thermi3/4096)*1000
                thermi4_mV = (VOLTAGE_REF*thermi4/4096)*1000
                
                if choice_made=='1':
                    print("Thermistor 1 = {} ({:4.3f} mV)".format(thermi1,thermi1_mV))
                elif choice_made=='2':
                    print("Thermistor 2 = {} ({:4.3f} mV)".format(thermi2,thermi2_mV))
                elif choice_made=='3':
                    print("Thermistor 3 = {} ({:4.3f} mV)".format(thermi3,thermi3_mV))
                elif choice_made=='4':
                    print("Thermistor 4 = {} ({:4.3f} mV)".format(thermi4,thermi4_mV))
                elif choice_made=='5':
                    i = 1
                    for value in pasto.get_thermi():
                        print("Thermistor {} = {} ({:4.3f} mV)".format(i,value,(VOLTAGE_REF*value/4096)*1000))
                        i+=1
                
                # input()
                
                choice_made = '-1'
        
        return 0

    # A sub-menu to manage the pump
    def subMenu_pump():
        """Display a sub-menu to manage the pump."""
        choice_made = '-1'
        
        while choice_made!='0':
            print("########## PUMP SUB-MENU ##########")
            print(" 1 - Power\n",
                  "2 - Speed\n",
                  "3 - Direction\n",
                  "4 - Get the speed return by the servo\n",
                  "5 - Get the error code return by the regulator\n",
                  "0 - Back\n")
            
            choice_made = menu_choice(0,5)
            print("\n")
            
            # If the choice is valid
            if choice_made!='0':
                if choice_made=='1':
                    print("### Power ###")
                    
                    if pasto.get_pump_power()==1:
                        print(" 0 - (OFF)\n",
                              "1 - ON\n")
                    elif pasto.get_pump_power()==0:
                        print(" 0 - OFF\n",
                              "1 - (ON)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_pump_power(1)
                        print("Power OFF")
                    elif choice_made=='1':
                        pasto.set_pump_power(0)
                        print("Power ON")
                    choice_made = '1'
                if choice_made=='2':
                    while choice_made!='0':
                        print("### Speed ###")
                        print("\nCurrent speed = {}\n".format(pasto.get_pump_speed()))
                        print(" 1 - Modify\n",
                              "0 - Back\n")
                        
                        choice_made = menu_choice(0,1)
                        print("\n")
                        
                        if choice_made!='0':
                            updatedSpeed = input("Enter a new speed: ")
                            pasto.set_pump_speed(int(updatedSpeed))
                            choice_made = '-1'
                    choice_made = '4'
                if choice_made=='3':
                    print("### Direction ###")
                    
                    if pasto.get_pump_dir()==0:
                        print(" 0 - (Suction mode)\n",
                              "1 - Backflow mode\n")
                    elif pasto.get_pump_dir()==1:
                        print(" 0 - Suction mode\n",
                              "1 - (Backflow mode)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_pump_dir(0)
                        print("Suction mode ON")
                    elif choice_made=='1':
                        pasto.set_pump_dir(1)
                        print("Backflow mode ON")
                    choice_made = '2'
                if choice_made=='4':
                    cursp = pasto.get_pump_speed()
                    servol = pasto.get_pump_servo()
                    # spmin = 99999999
                    # spmax = 0
                    # spavg = 0
                    # spvar = 0
                    # for i in range(0,50):
                        # sp = pasto.get_pump_servo();
                        # print("Ticks from the servo = {}".format(sp))
                        # spmin = sp if sp < spmin else spmin
                        # spmax = sp if sp > spmax else spmax
                        # spavg += sp
                        # spvar += (sp*sp)
                        # time.sleep(0.050)
                    # spmin = int(spmin*20*6.4)
                    # spmax = int(spmax*20*6.4)
                    # spavg = int(spavg*20*6.4/50)
                    # stress = (((spvar*400*6.4*6.4)-(spavg*spavg))/2500)**0.5
                    # print ("Min=%d, Max=%d, Avg=%d Hz, Var²=%f" % (spmin,spmax, spavg, stress) )
                    # if cursp:
                        # print ("Min=%f1%%, Max=%f1%%, Avg=%f1%%, stress=%f1%%" % (spmin*100.0/cursp-100.0,spmax*100.0/cursp-100.0, spavg*100.0/cursp-100.0, 100.0*stress/cursp ) )
                    print ("Min=%d, Max=%d, Avg=%d Hz, Pulse²=%d" % (servol[1],servol[0], servol[2], servol[3]) )
                    if cursp:
                        print ("Min=%f1%%, Max=%f1%%, Avg=%f1%%" % (servol[1]*100.0/cursp-100.0,servol[0]*100.0/cursp-100.0, servol[2]*100.0/cursp-100.0 ) )
                if choice_made=='5':
                    print("Error returned by the regulator = {}".format(pasto.get_pump_error()))
                
                choice_made= '-1'
        
        return 0

    # Sub-menu to manage the tanks
    def subMenu_tanks():
        """Display a sub-menu to manage the tanks."""
        choice_made = '-1'
        
        while choice_made!='0':
            print("########## TANKS SUB-MENU ##########")
            print(" 1 - Tank 1 state\n",
                  "2 - Tank 2 state\n",
                  "0 - Back\n")
            
            choice_made = menu_choice(0,2)
            print("\n")
            
            # If the choice is valid
            if choice_made!='0':
                if choice_made=='1':
                    print("### Tank 1 ###")
                    
                    if pasto.get_tank1()==0:
                        print(" 0 - (OFF)\n",
                              "1 - ON\n")
                    elif pasto.get_tank1()==1:
                        print(" 0 - OFF\n",
                              "1 - (ON)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_tank1(0)
                        print("Tank 1 OFF")
                    elif choice_made=='1':
                        pasto.set_tank1(1)
                        print("Tank 1 ON")
                    # input()
                elif choice_made=='2':
                    print("### Tank 2 ###")
                    
                    if pasto.get_tank2()==0:
                        print(" 0 - (OFF)\n",
                              "1 - ON\n")
                    elif pasto.get_tank2()==1:
                        print(" 0 - OFF\n",
                              "1 - (ON)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_tank2(0)
                        print("Tank 2 OFF")
                    elif choice_made=='1':
                        pasto.set_tank2(1)
                        print("Tank 2 ON")
                    # input()
            
                choice_made = '-1'
        
        return 0

    # Sub-menu to manage the valves and solenoids
    def subMenu_valvesSol():
        """Display en sub-menu to manage the valves and solenoids."""
        choice_made = '-1'
        
        while choice_made!='0':
            print("########## VALVES AND SOLENOIDS SUB-MENU ##########")
            print(" 1 - Hot water solenoid\n",
                  "2 - Cold water solenoid\n",
                  "3 - Manage the valve 1\n",
                  "4 - Manage the valve 2\n",
                  "0 - Back\n")
            
            choice_made = menu_choice(0,4)
            print("\n")
            
            # If the choice is valid
            if choice_made!='0':
                if choice_made=='1':
                    print("### Hot water solenoid ###")
                    
                    if pasto.get_sol_hot()==0:
                        print(" 0 - (Close)\n",
                              "1 - Open\n")
                    elif pasto.get_sol_hot()==1:
                        print(" 0 - Close\n",
                              "1 - (Open)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_sol_hot(0)
                        print("Hot water solenoid is closing")
                    elif choice_made=='1':
                        pasto.set_sol_hot(1)
                        print("Hot water solenoid is opening")
                    # input()
                elif choice_made=='2':
                    print("### Cold water solenoid ###")
                    
                    if pasto.get_sol_cold()==0:
                        print(" 0 - (Close)\n",
                              "1 - Open\n")
                    elif pasto.get_sol_cold()==1:
                        print(" 0 - Close\n",
                              "1 - (Open)\n")
                    
                    choice_made = menu_choice(0,1)
                    print("\n")
                    
                    if choice_made=='0':
                        pasto.set_sol_cold(0)
                        print("Cold water solenoid is closing")
                    elif choice_made=='1':
                        pasto.set_sol_cold(1)
                        print("Cold water solenoid is opening")
                    # input()
                elif choice_made=='3':
                    while choice_made!='0':
                        print("### Valve 1 ###")
                        print(" 1 - Power\n",
                              " 2 - Direction\n",
                              " 0 - Back")
                        
                        choice_made = menu_choice(0,2)
                        print("\n")
                        
                        if choice_made!='0':
                            if choice_made=='1':
                                print("### Valve 1 power ###")

                                if pasto.get_valve1_power()==0:
                                    print(" 0 - (OFF)\n",
                                          "1 - ON")
                                elif pasto.get_valve1_power()==1:
                                    print(" 0 - OFF\n",
                                          "1 - (ON)\n")
                                    
                                choice_made = menu_choice(0,1)
                                print("\n")
                                
                                if choice_made=='0':
                                    pasto.set_valve1_power(0)
                                    print("Valve 1 power OFF")
                                elif choice_made=='1':
                                    pasto.set_valve1_power(1)
                                    print("Valve 1 power ON")
                                # input()
                            
                            elif choice_made=='2':
                                print("### Valve 1 direction ###")

                                if pasto.get_valve1_dir()==0:
                                    print(" 0 - (Direction 1)\n",
                                          "1 - Direction 2")
                                elif pasto.get_valve1_dir()==1:
                                    print(" 0 - Direction 1\n",
                                          "1 - (Direction 2)\n")
                                    
                                choice_made = menu_choice(0,1)
                                print("\n")
                                
                                if choice_made=='0':
                                    pasto.set_valve1_dir(0)
                                    print("Valve 1 set in direction 1")
                                elif choice_made=='1':
                                    pasto.set_valve1_dir(1)
                                    print("Valve 1 set in direction 2")
                                # input()
                            choice_made = '-1'
                elif choice_made=='4':
                    while choice_made!='0':
                        print("### Valve 2 ###")
                        print(" 1 - Power\n",
                              " 2 - Direction\n",
                              " 0 - Back")
                        
                        choice_made = menu_choice(0,2)
                        print("\n")
                        
                        if choice_made!='0':
                            if choice_made=='1':
                                print("### Valve 2 power ###")

                                if pasto.get_valve2_power()==0:
                                    print(" 0 - (OFF)\n",
                                          "1 - ON")
                                elif pasto.get_valve2_power()==1:
                                    print(" 0 - OFF\n",
                                          "1 - (ON)\n")
                                    
                                choice_made = menu_choice(0,1)
                                print("\n")
                                
                                if choice_made=='0':
                                    pasto.set_valve2_power(0)
                                    print("Valve 2 power OFF")
                                elif choice_made=='1':
                                    pasto.set_valve2_power(1)
                                    print("Valve 2 power ON")
                                # input()
                            
                            elif choice_made=='2':
                                print("### Valve 2 direction ###")

                                if pasto.get_valve2_dir()==0:
                                    print(" 0 - (Direction 1)\n",
                                          "1 - Direction 2")
                                elif pasto.get_valve2_dir()==1:
                                    print(" 0 - Direction 1\n",
                                          "1 - (Direction 2)\n")
                                    
                                choice_made = menu_choice(0,1)
                                print("\n")
                                
                                if choice_made=='0':
                                    pasto.set_valve2_dir(0)
                                    print("Valve 2 set in direction 1")
                                elif choice_made=='1':
                                    pasto.set_valve2_dir(1)
                                    print("Valve 2 set in direction 2")
                                # input()
                            choice_made = '-1'
            
                choice_made = '-1'
                
        return 0

    def subMenu_generalState():
        """Display the error code and the general state of the system"""
        
        print("########## General state ##########")
        print("Boot state flag \t= {}".format(pasto.get_boot_flag()))
        print("Debug mode flag \t= {}".format(pasto.get_debug_flag()))
        print("General state = {}".format(pasto.get_general_state()))
        print("Error code = {}\n".format(pasto.get_error_code()))

        choice_made = '9'
        while choice_made!='0':
            print(" 1 - debug ON\n",
                      "2 - debug OFF\n",
                      "0 - Back")
            
            choice_made = menu_choice(0,2)
            print("\n")
            
            if choice_made!='0':
                pasto.set_debug_flag(choice_made=='1')

    def subMenu_registers():
        """Display the value of all the registers."""
        
        print("########## Registers ##########")
        # State
        print("Boot state flag \t= {}".format(pasto.get_boot_flag()))
        print("Debug mode flag \t= {}".format(pasto.get_debug_flag()))
        print("General state \t\t= {}".format(pasto.get_general_state()))
        print("Error code \t\t= {}".format(pasto.get_error_code()))
        # Thermistors
        i = 1
        for value in pasto.get_thermi():
            print("Thermistor {} \t\t= {}".format(i,value))
            i+=1
        # Pompe
        print("Pump power \t\t= {}".format(pasto.get_pump_power()))
        print("Pump speed \t\t= {}".format(pasto.get_pump_speed()))
        print("Pump direction \t\t= {}".format(pasto.get_pump_dir()))
        print("Pump servo \t\t= {}".format(pasto.get_pump_servo()))
        print("Pump error \t\t= {}".format(pasto.get_pump_error()))
        print("Tank 1 state \t\t= {}".format(pasto.get_tank1()))
        print("Tank 2 state \t\t= {}".format(pasto.get_tank2()))
        print("Hot water solenoid \t= {}".format(pasto.get_sol_hot()))
        print("Cold water solenoid \t= {}".format(pasto.get_sol_cold()))
        print("Valve 1 power \t\t= {}".format(pasto.get_valve1_power()))
        print("Valve 1 direction \t= {}".format(pasto.get_valve1_dir()))
        print("Valve 2 power \t\t= {}".format(pasto.get_valve2_power()))
        print("Valve 2 direction \t= {}".format(pasto.get_valve2_dir()))
        
    ################ main program ################

    choice = '-1'
    menuPrincipal = {'1':subMenu_thermis, '2':subMenu_pump, '3':subMenu_tanks, '4':subMenu_valvesSol, '5':subMenu_generalState, '6':subMenu_registers}
    pasto = Micha()

    while choice!='0':
        
        print("################ MENU ################")
        print(" 1 - Thermistors\n",
              "2 - Pump\n",
              "3 - Tanks\n",
              "4 - Valves/solenoids\n",
              "5 - General state\n",
              "6 - All registers\n",
              "0 - Exit\n")
        
        choice = menu_choice(0,6)  
        print("\n")
        
        if choice!='0':
            choice = menuPrincipal[choice]()

    pasto.close()
    print("\nBye!\n")

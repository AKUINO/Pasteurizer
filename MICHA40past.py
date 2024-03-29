#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This code allows to communicate with the MICHA board in a pastorizator configuration. It can be use as:
#     - a library to communicate with the MICHA board using another main code file
#     - a standalone code to test the I/O of the MICHA board

import traceback
from serial import Serial, PARITY_NONE
from umodbus.client.serial import rtu
import time
import MICHApast


# Class to manage the MICHA board
class Micha4:
    def __init__(self,device='/dev/ttyS1'):  # serial0 for RPi, ttyS1 for Odroid
        self.device = device
        self.id = 0
        self.boot_flag = 1
        self.thermi = 0
        self.thermis_pow = 0
        self.pump_speed = 0
        self.pump_speed_inc = 0
        self.pump_dir = 0
        self.pump_power = 0
        self.tank1 = 0
        self.sol_hot = 0
        self.general_state = 0
        self.error_code = 0
        self.debug_flag = 0
        self.level = 0
        self.level1_flag = 0
        self.level2_flag = 0
        self.press_flag = 0
        self.busy = False
        self.port = None
    
    # Configuration and starting of the modbus communication
    def get_serial_port(self):
        while self.busy:
            time.sleep(MICHApast.DELAY_RETRY)
        self.busy = True
        while not self.port: # In case of error, we reset the access to the ModBus
            try:
                """Return a serial.Serial instance which is ready to use with a RS485 adaptor."""
                self.port = Serial(port=self.device, baudrate=19200, parity=PARITY_NONE, stopbits=1, bytesize=8, timeout=1)
            except:
                print("MICHA4 open failed\r")
                traceback.print_exc()
                self.port = None
                time.sleep(MICHApast.DELAY_RETRY) # Do not retry too fast...
        return self.port

    def close_serial_port(self):
        if self.port:
            try:
                self.port.close()
            except:
                traceback.print_exc()
            self.port = None
        self.busy = False

    def close (self):
        self.write_pin(MICHApast.PRESS_FLAG_REG,0)
        self.close_serial_port()

    def release_serial_port(self):
        #self.busy = False
        self.close_serial_port()
        
    def read_pin(self,reg): # read a single coil register at reg address
        i = 0
        while i < MICHApast.MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                message = rtu.read_coils(MICHApast.SLAVE_ID, reg, 1)
                #print("READ mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read pin %d failed\r" % reg)
                i = i+1
        return None

    def write_pin(self,reg,val): # write val in a single coil register at reg address
        i = 0
        while i < MICHApast.WRITE_RETRY:
            try:
                serial_port = self.get_serial_port()                
                message = rtu.write_single_coil(MICHApast.SLAVE_ID, reg, val)
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

    def read_discrete(self,reg): # read a discrete input register at reg address
        i = 0
        while i < MICHApast.MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                message = rtu.read_discrete_inputs(MICHApast.SLAVE_ID, reg, 1)
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read discrete %d failed\r" % reg)
                i = i + 1
        return None

    def read_input(self,reg): # read a single input register at reg address
        i = 0
        while i < MICHApast.MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()            
                message = rtu.read_input_registers(MICHApast.SLAVE_ID, reg, 1)
                #print("INPUT mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read input %d failed\r" % reg)
                i = i+1
                #time.sleep(0.1)
        return None

    def read_holding(self,reg): # read a single holding register at reg address
        i = 0
        while i < MICHApast.MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                message = rtu.read_holding_registers(MICHApast.SLAVE_ID, reg, 1)
                #print("HOLDING mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response[0]
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA read holding %d failed\r" % reg)
                i = i+1
                #time.sleep(0.1)
        return None

    def write_holding(self,reg, val): # write val in the holding register at reg address
        i = 0
        while i < MICHApast.WRITE_RETRY:
            try:
                serial_port = self.get_serial_port()            
                message = rtu.write_single_register(MICHApast.SLAVE_ID, reg, val)
                #print("WRITE HOLDING mess=%s\r"%(''.join('%02x '%i for i in message)))
                response = rtu.send_message(message, serial_port)
                self.release_serial_port()
                return response
            except:
                #traceback.print_exc()
                self.close_serial_port()
                print("MICHA write holding %d=%d failed\r" % (reg,val))
                i = i+1
                #time.sleep(0.1)
        return None

    def get_id(self): # to get the modbus ID
        self.id = self.read_holding(MICHApast.ID_REG)
        return self.id

    def get_boot_flag(self): # to get the boot state
        self.boot_flag = self.read_pin(MICHApast.BOOT_FLAG_REG)
        return self.boot_flag
    
    def set_boot_flag(self,flag=0): # to set the boot state
        self.boot_flag = flag
        response = self.write_pin(MICHApast.BOOT_FLAG_REG, flag)
        return response

    def get_thermis_pow(self):  # to get the power state of the thermistors (stored in the register), returns the thermistors power state
        self.thermis_pow = self.read_pin(MICHApast.THERMIS_POW_REG)
        return self.thermis_pow

    def set_thermis_pow(self,power=0):  # to set the power of the thermistors
        if self.thermis_pow != power:
            self.thermis_pow = power
            response = self.write_pin(MICHApast.THERMIS_POW_REG, power)
            return response
        return 0
    
    def get_thermi(self, th=0): # to get the thermistor value, returns the thermistor value
        self.thermi = th
        i = 0
        message = None
        response = None
        while i < MICHApast.MODBUS_RETRY:
            try:
                serial_port = self.get_serial_port()
                
                if self.thermi == 0: # get the value of all the thermistors
                    message = rtu.read_input_registers(MICHApast.SLAVE_ID, MICHApast.THERMI1_REG, 4)
                elif self.thermi == 1: # get the thermistor 1 value
                    message = rtu.read_input_registers(MICHApast.SLAVE_ID, MICHApast.THERMI1_REG, 1)
                elif self.thermi == 2: # get the thermistor 2 value
                    message = rtu.read_input_registers(MICHApast.SLAVE_ID, MICHApast.THERMI2_REG, 1)
                elif self.thermi == 3: # get the thermistor 3 value
                    message = rtu.read_input_registers(MICHApast.SLAVE_ID, MICHApast.THERMI3_REG, 1)
                elif self.thermi == 4: # get the thermistor 4 value
                    message = rtu.read_input_registers(MICHApast.SLAVE_ID, MICHApast.THERMI4_REG, 1)
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
        if self.pump_power != power:
            self.pump_power = power
            response = self.write_pin(MICHApast.PUMP_POW_REG, power)
            return response
        return 0

    def set_pump_speed(self,speed=0): # to set the speed of the pump
        if self.pump_speed != speed:
            self.pump_speed = speed
            return self.write_holding(MICHApast.PUMP_SPEED_REG, speed)
        return 0

    def set_pump_speed_inc(self,inc=0): # to set the speed incrementation of the pump
        if self.pump_speed_inc != inc:
            self.pump_speed_inc = inc
            return self.write_holding(MICHApast.PUMP_SPEED_INC_REG, inc)
        return 0
    
    def set_pump_dir(self, direction=0): # to set the direction of the pump
        if self.pump_dir != direction:
            self.pump_dir = direction
            response = self.write_pin(MICHApast.PUMP_DIR_REG, direction)
            return response
        return 0
    
    def get_pump_power(self): # to get the power state of the pump (stored in the register), returns the pump power state
        self.pump_power = self.read_pin(MICHApast.PUMP_POW_REG)
        return self.pump_power
    
    def get_pump_dir(self): # to get the direction state of the pump (stored in the register), returns the pump direction value
        self.pump_dir = self.read_pin(MICHApast.PUMP_DIR_REG)
        return self.pump_dir
    
    def get_pump_speed(self): # to get the speed of the pump (stored in the register), returns the pump speed
        self.pump_speed = self.read_holding(MICHApast.PUMP_SPEED_REG)
        return self.pump_speed

    def get_pump_speed_inc(self): # to get the speed incrementation of the pump (stored in the register), returns the pump speed incrementation
        self.pump_speed_inc = self.read_holding(MICHApast.PUMP_SPEED_INC_REG)
        return self.pump_speed_inc
    
    def set_tank1(self,state=0): # to set the state of the tank 1
        if self.tank1 != state:
            self.tank1 = state
            response = self.write_pin(MICHApast.TANK1_REG, state)
            return response
        return 0
    
    def get_tank1(self): # to get the state of the tank 1 (stored in the register)
        self.tank1 = self.read_pin(MICHApast.TANK1_REG)
        return self.tank1
    
    def set_sol_hot(self,state=0): # to set the state of the hot water solenoid
        if self.sol_hot != state:
            self.sol_hot = state
            response = self.write_pin(MICHApast.SOL_HOT_REG, state)
            return response
        return 0
    
    def get_sol_hot(self): # to get the state of the hot water solenoid (stored in the register)
        self.sol_hot = self.read_pin(MICHApast.SOL_HOT_REG)
        return self.sol_hot

    def get_level1_sensor(self): # to get the level 1 sensor value, returns the level 1 sensor value
        return self.read_discrete(MICHApast.LEVEL_SENSOR1_REG)

    def set_level1_flag(self,state=0): # to set the level 1 sensor flag value
        if self.level1_flag != state:
            self.level1_flag = state
            response = self.write_pin(MICHApast.LEVEL1_FLAG_REG, state)
            return response
        return 0

    def get_level1_flag(self): # to get the level 1 sensor flag value, returns the level 1 sensor flag value
        return self.read_pin(MICHApast.LEVEL1_FLAG_REG)

    def get_level2_sensor(self): # to get the level 2 sensor value, returns the level 2 sensor value
        return self.read_discrete(MICHApast.LEVEL_SENSOR2_REG)

    def set_level2_flag(self,state=0): # to set the level 2 sensor flag value
        if self.level2_flag != state:
            self.level2_flag = state
            response = self.write_pin(MICHApast.LEVEL2_FLAG_REG, state)
            return response
        return 0

    def get_level2_flag(self): # to get the level 2 sensor flag value, returns the level 2 sensor flag value
        return self.read_pin(MICHApast.LEVEL2_FLAG_REG)

    def get_press_sensor(self): # to get the pressure sensor value, returns the pressure sensor value
        return self.read_input(MICHApast.PRESS_SENSOR_REG)

    def set_press_flag(self, state=0):  # to set the pressure sensor flag value
        if self.press_flag != state:
            self.press_flag = state
            response = self.write_pin(MICHApast.PRESS_FLAG_REG, state)
            return response
        return 0

    def get_press_flag(self):  # to get the pressure sensor flag value, returns the pressure sensor flag value
        return self.read_pin(MICHApast.PRESS_FLAG_REG)

    def get_emergency_stop(self): # to get the emergency stop value, returns the emergency stop value
        return self.read_discrete(MICHApast.EMERGENCY_STOP_REG)

    def get_general_state(self): # to get the general state of the system (stored in the register)
        self.general_state = self.read_input(MICHApast.GEN_STATE_REG)
        return self.general_state
    
    def get_error_code(self): # to get the general error code
        self.error_code = self.read_input(MICHApast.ERROR_CODE_REG)
        return self.error_code

    def get_debug_flag(self):  # to get the debug state
        self.debug_flag = self.read_pin(MICHApast.DEBUG_FLAG_REG)
        return self.debug_flag

    def set_debug_flag(self, flag=0):  # to set the debug state
        if self.debug_flag != flag:
            self.debug_flag = flag
            response = self.write_pin(MICHApast.DEBUG_FLAG_REG, flag)
            return response
        return 0


# test section
if __name__ == "__main__":

    def boot_monitoring():
        if pasto.get_boot_flag():
            print("\n\nTHE DEVICE HAS REBOOTED!")
            pasto.set_boot_flag()

        return 0


    def menu_choice(mini, maxi):
        choice_made = '-1'

        while int(choice_made) < mini or int(choice_made) > maxi:
            choice_made = input("Choose an option: ")

            boot_monitoring()

            if int(choice_made) < mini or int(choice_made) > maxi:
                print("ERROR: incorrect choice. Your choice must be [{}:{}]".format(mini, maxi))

        return choice_made


    # Allows to manage the thermistors
    def thermis(choice_made):
        """Display the value of the thermistors."""

        if choice_made == 'tps':  # gets the current thermistors power pin state
            print("\nCurrent thermistor power pin state = {}\n".format(pasto.get_thermis_pow()))
        elif choice_made == 'tp0':  # sets the thermistors power pin state to 0
            pasto.set_thermis_pow(0)
            print('\nThermistor power pin state sets to 0 (OFF)\n')
        elif choice_made == 'tp1':  # sets the thermistors power pin state to 1
            pasto.set_thermis_pow(1)
            print('\nThermistor power pin state sets to 1 (ON)\n')
        elif choice_made == 'ts':
            thermi1 = pasto.get_thermi(1)[0]
            thermi2 = pasto.get_thermi(2)[0]
            thermi3 = pasto.get_thermi(3)[0]
            thermi4 = pasto.get_thermi(4)[0]

            thermi1_mV = (MICHApast.VOLTAGE_REF * thermi1 / 4096) * 1000
            thermi2_mV = (MICHApast.VOLTAGE_REF * thermi2 / 4096) * 1000
            thermi3_mV = (MICHApast.VOLTAGE_REF * thermi3 / 4096) * 1000
            thermi4_mV = (MICHApast.VOLTAGE_REF * thermi4 / 4096) * 1000

            print('\n')
            i = 1
            for value in pasto.get_thermi():
                print("Thermistor {} = {} ({:4.3f} mV)".format(i, value, (MICHApast.VOLTAGE_REF * value / 4096) * 1000))
                i += 1
            print('\n')
        elif choice_made == 'ts1':
            thermi1 = pasto.get_thermi(1)[0]
            thermi1_mV = (MICHApast.VOLTAGE_REF * thermi1 / 4096) * 1000
            print("\nThermistor 1 = {} ({:4.3f} mV)\n".format(thermi1, thermi1_mV))
        elif choice_made == 'ts2':
            thermi2 = pasto.get_thermi(2)[0]
            thermi2_mV = (MICHApast.VOLTAGE_REF * thermi2 / 4096) * 1000
            print("\nThermistor 2 = {} ({:4.3f} mV)\n".format(thermi2, thermi2_mV))
        elif choice_made == 'ts3':
            thermi3 = pasto.get_thermi(3)[0]
            thermi3_mV = (MICHApast.VOLTAGE_REF * thermi3 / 4096) * 1000
            print("\nThermistor 3 = {} ({:4.3f} mV)\n".format(thermi3, thermi3_mV))
        elif choice_made == 'ts4':
            thermi4 = pasto.get_thermi(4)[0]
            thermi4_mV = (MICHApast.VOLTAGE_REF * thermi4 / 4096) * 1000
            print("\nThermistor 4 = {} ({:4.3f} mV)\n".format(thermi4, thermi4_mV))

        return 0


    # Allows to manage the pump
    def pump(choice_made):
        """Get or set a value related to the pump."""

        if choice_made == 'ps':  # gets all the current pump pin state
            print("\nCurrent pump power pin state = {}".format(pasto.get_pump_power()))
            print("Current pump direction pin state = {}".format(pasto.get_pump_dir()))
            print("Current pump speed = {}".format(pasto.get_pump_speed()))
            print("Current pump speed incrementation = {}\n".format(pasto.get_pump_speed_inc()))
        elif choice_made == 'pps':  # gets the current pump power pin state
            print("\nCurrent pump power pin state = {}\n".format(pasto.get_pump_power()))
        elif choice_made == 'pp0':  # sets the pump power pin state to 0
            pasto.set_pump_power(0)
            print('\nPump power pin state sets to 0 (ON)\n')
        elif choice_made == 'pp1':  # sets the pump power pin state to 1
            pasto.set_pump_power(1)
            print('\nPump power pin state sets to 1 (OFF)\n')
        elif choice_made == 'pds':  # gets the current pump direction pin state
            print("\nCurrent pump direction pin state = {}\n".format(pasto.get_pump_dir()))
        elif choice_made == 'pd0':  # sets the pump direction pin state to 0
            pasto.set_pump_dir(0)
            print('\nPump direction pin state sets to 0\n')
        elif choice_made == 'pd1':  # sets the pump direction pin state to 1
            pasto.set_pump_dir(1)
            print('\nPump direction pin state sets to 1\n')
        elif choice_made == 'pss':  # gets the current pump speed value
            print("\nCurrent pump speed = {}\n".format(pasto.get_pump_speed()))
        elif choice_made == 'psis':  # gets the current pump speed incrementation value
            print("\nCurrent pump speed incrementation = {}\n".format(pasto.get_pump_speed_inc()))

        return 0


    # Allows to manage the tank
    def tank(choice_made):
        """Get or set a value related to the pump."""

        if choice_made == 'cps':  # gets the current cistern pin state
            print("\nCurrent heating cistern power pin state = {}\n".format(pasto.get_tank1()))
        elif choice_made == 'cp0':  # sets the cistern pin state to 0
            pasto.set_tank1(0)
            print('\nHeating cistern power pin state sets to 0 (OFF)\n')
        elif choice_made == 'cp1':  # sets the cistern pin state to 1
            pasto.set_tank1(1)
            print('\nHeating cistern power pin state sets to 1 (ON)\n')

        return 0


    # Allows to manage the water solenoid valve
    def sol(choice_made):
        """Get or set a value related to the water solenoid valve."""

        if choice_made == 'ss':  # gets the current water solenoid pin state
            print("\nCurrent water solenoid pin state = {}\n".format(pasto.get_sol_hot()))
        elif choice_made == 's0':  # sets the water solenoid pin state to 0
            pasto.set_sol_hot(0)
            print('\nWater solenoid pin state sets to 0 (CLOSED)\n')
        elif choice_made == 's1':  # sets the water solenoid pin state to 1
            pasto.set_sol_hot(1)
            print('\nWater solenoid pin state sets to 1 (OPENED)\n')

        return 0


    def levelSensors(choice_made):
        """Get or set a value related to the level sensors."""

        if choice_made == 'ls':  # gets all the current level sensor values
            if pasto.get_level1_flag():
                print("\nCurrent level sensor 1 value = {}".format(pasto.get_level1_sensor()))
            else:
                print("\nCurrent level sensor 1 value = désactivé")
            if pasto.get_level2_flag():
                print("Current level sensor 2 value = {}".format(pasto.get_level2_sensor()))
            else:
                print("Current level sensor 2 value = désactivé")
        elif choice_made == 'lfs':  # gets all the current level sensor flag states
            print("\nLevel sensor 1 flag state = {}".format(pasto.get_level1_flag()))
            print("Level sensor 2 flag state = {}\n".format(pasto.get_level2_flag()))
        elif choice_made == 'l1s':  # gets the current level sensor 1 value
            print("\nCurrent level sensor 1 value = {}\n".format(pasto.get_level1_sensor()))
        elif choice_made == 'lf1s':  # gets the current level sensor 1 flag state
            print("\nLevel sensor 1 flag state = {}\n".format(pasto.get_level1_flag()))
        elif choice_made == 'lf10':  # sets the level sensor 1 flag state to 0
            pasto.set_level1_flag(0)
            print('\nLevel sensor 1 flag state sets to 0 (OFF)\n')
        elif choice_made == 'lf11':  # sets the level sensor 1 flag state to 1
            pasto.set_level1_flag(1)
            print('\nLevel sensor 1 flag state sets to 1 (ON)\n')
        elif choice_made == 'l2s':  # gets the current level sensor 2 value
            print("\nCurrent level sensor 2 value = {}\n".format(pasto.get_level2_sensor()))
        elif choice_made == 'lf2s':  # gets the level sensor 2 flag state
            print("\nLevel sensor 2 flag state = {}\n".format(pasto.get_level2_flag()))
        elif choice_made == 'lf20':  # gsts the level sensor 2 flag state to 0
            pasto.set_level2_flag(0)
            print('\nLevel sensor 2 flag state sets to 0 (OFF)\n')
        elif choice_made == 'lf21':  # sets the level sensor 2 flag state to 1
            pasto.set_level2_flag(1)
            print('\nLevel sensor 2 flag state sets to 1 (ON)\n')

        return 0


    def emergency_stop():
        """Get the emergency stop pin state"""

        print("\nCurrent emergency stop pin state = {}".format(pasto.get_emergency_stop()))

        return 0


    def pressSensor(choice_made):
        """Get or set a value related to the pressure sensor."""
        Vcc = 5.1  # power voltage applied to the pressure sensor
        pressure = pasto.get_press_sensor()  # raw value of the pressure (0-4095)
        pressure_V = pressure / 1638  # pressure in V
        #pressure_psi = 125 * (pressure_V / Vcc) - 12.5  # pressure in Psi

        #pressure_psi = (pressure_V - (Vcc*0.1) ) * (90 / (Vcc*0.8))  # pressure in Psi
        pressure_psi = 100*(pressure_V/Vcc)
        pressure_bar = pressure_psi / 14.504  # pressure in bar

        if choice_made == 'prs':  # gets the current pressure sensor value
            if pasto.get_press_flag():
                print("\nCurrent pressure sensor value = {} ({:4.3f} mV, {:4.3f} bars)\n".format(pressure, pressure_V,
                                                                                                 pressure_bar))
            else:
                print("\nCurrent pressure sensor value = désactivé\n")
        elif choice_made == 'prfs':  # gets the current pressure sensor flag state
            print("\nLevel sensor 1 flag state = {}\n".format(pasto.get_press_flag()))
        elif choice_made == 'prf0':  # sets the pressure sensor flag state to 0
            pasto.set_press_flag(0)
            print('\nPressure sensor flag state sets to 0 (OFF)\n')
        elif choice_made == 'prf1':  # sets the pressure sensor flag state to 1
            pasto.set_press_flag(1)
            print('\nPressure sensor flag state sets to 1 (ON)\n')

        return 0


    def generalState(choice_made):
        """Get the error code and the general state of the system"""

        if choice_made == 'id':
            print("\nModbus ID = {}\n".format(pasto.get_id()))
        elif choice_made == 'bss':
            print("\nBoot state = {}\n".format(pasto.get_boot_flag()))
        elif choice_made == 'dms':
            print("\nDebug mode = {}\n".format(pasto.get_debug_flag()))
        elif choice_made == 'dm0':
            pasto.set_debug_flag(0)
            print('\nDebug mode sets to 0 (OFF)\n')
        elif choice_made == 'dm1':
            pasto.set_debug_flag(1)
            print('\nDebug mode sets to 1 (ON)\n')
        elif choice_made == 'gss':
            print("\nGeneral state = {}\n".format(pasto.get_general_state()))
        elif choice_made == 'ecs':
            print("\nError code = {}\n".format(pasto.get_error_code()))

        return 0


    def registers():
        """Display the value of all the registers."""

        # State
        print("\nModbus ID \t\t= {}".format(pasto.get_id()))
        print("Boot state flag \t= {}".format(pasto.get_boot_flag()))
        print("Debug mode flag \t= {}".format(pasto.get_debug_flag()))
        print("General state \t\t= {}".format(pasto.get_general_state()))
        print("Error code \t\t= {}".format(pasto.get_error_code()))
        print("Emergency stop \t\t= {}".format(pasto.get_emergency_stop()))
        # Thermistors
        print("Thermistor power \t= {}".format(pasto.get_thermis_pow()))
        i = 1
        for value in pasto.get_thermi():
            print("Thermistor {} \t\t= {}".format(i, value))
            i += 1
        # Pump
        print("Pump power \t\t= {}".format(pasto.get_pump_power()))
        print("Pump direction \t\t= {}".format(pasto.get_pump_dir()))
        print("Pump speed \t\t= {}".format(pasto.get_pump_speed()))
        print("Pump speed increment \t= {}".format(pasto.get_pump_speed_inc()))
        # Tank
        print("Tank 1 power \t\t= {}".format(pasto.get_tank1()))
        # Water solenoid
        print("Water solenoid \t\t= {}".format(pasto.get_sol_hot()))
        # Level sensors
        print("Level sensor 1 flag \t= {}".format(pasto.get_level1_flag()))
        print("Level sensor 1 \t\t= {}".format(pasto.get_level1_sensor()))
        print("Level sensor 2 flag \t= {}".format(pasto.get_level2_flag()))
        print("Level sensor 2 \t\t= {}".format(pasto.get_level2_sensor()))
        # Pressure sensor
        print("Pressure sensor flag \t= {}".format(pasto.get_press_flag()))
        print("Pressure sensor \t= {}".format(pasto.get_press_sensor()))


    ################ main program ################

    pasto = Micha4()
    choice = -1

    while choice != 'exit':

        print("################ MENU ################")
        print(" all \t- Show all register values\n",
              "bss \t- Show boot state\n",
              "cps \t- Show the current heating cistern power pin state\n",
              "cp0 \t- Set the heating cistern power pin state to 0\n",
              "cp1 \t- Set the heating cistern power pin state to 1\n",
              "dms \t- Show debug mode state\n",
              "dm0 \t- Set debug mode to 0 (OFF)\n",
              "dm1 \t- Set debug mode to 1 (ON)\n",
              "ess \t- Get the emergency stop pin state\n",
              "ecs \t- Show error code\n",
              "id \t- Show the modbus ID\n",
              "ls \t- Show all the level sensor values\n",
              "lfs \t- Show all the current level sensor flag states\n",
              "l1s \t- Show the current level sensor 1 value\n",
              "lf1s \t- Show the current level sensor 1 flag state\n",
              "lf10 \t- Set the level sensor 1 flag state to 0\n",
              "lf11 \t- Set the level sensor 1 flag state to 1\n",
              "l2s \t- Show the current level sensor 2 value\n",
              "lf2s \t- Show the current level sensor 2 flag state\n",
              "lf20 \t- Set the level sensor 2 flag state to 0\n",
              "lf21 \t- Set the level sensor 2 flag state to 1\n",
              "ps \t- Show all the pump registers\n",
              "pds \t- Show the current pump direction pin state\n",
              "pd0 \t- Set the pump direction pin state to 0\n",
              "pd1 \t- Set the pump direction pin state to 1\n",
              "pps \t- Show the current pump power\n",
              "pp0 \t- Set the pump power pin state to 0 (ON)\n",
              "pp1 \t- Set the pump power pin state to 1 (OFF)\n",
              "pss \t- Show the current pump speed\n",
              "psX \t- Set the pump speed to X (0 <= X <= 65000)\n",
              "psis \t- Show the current pump speed incrementation\n",
              "psiX \t- Set the pump speed incrementation to X (0 <= X <= 65000)\n",
              "prs \t- Show the current pressure sensor value\n",
              "prfs \t- Show the current pressure sensor flag state\n",
              "prf0 \t- Set the pressure sensor flag state to 0\n",
              "prf1 \t- Set the pressure sensor flag state to 1\n",
              "ss \t- Show the current water solenoid pin state\n",
              "s0 \t- Set the water solenoid pin state to 0\n",
              "s1 \t- Set the water solenoid pin state to 1\n",
              "tps \t- Show the current thermistor power pin state\n",
              "tp0 \t- Set the thermistor power pin state to 0\n",
              "tp1 \t- Set the thermistor power pin state to 1\n",
              "ts \t- Show all thermistor values\n",
              "ts1 \t- Show thermistor 1 value\n",
              "ts2 \t- Show thermistor 2 value\n",
              "ts3 \t- Show thermistor 3 value\n",
              "ts4 \t- Show thermistor 4 value\n",
              "exit \t- Exit\n")

        choice = input('Entrez votre commande : ')

        if choice == 'all':
            registers()
            input()
        elif choice == 'bss':
            generalState('bss')
            input()
        elif choice == 'cps':
            tank('cps')
            input()
        elif choice == 'cp0':
            tank('cp0')
            input()
        elif choice == 'cp1':
            tank('cp1')
            input()
        elif choice == 'dms':
            generalState('dms')
            input()
        elif choice == 'dm0':
            generalState('dm0')
            input()
        elif choice == 'dm1':
            generalState('dm1')
            input()
        elif choice == 'ess':
            try:
                while True:
                    emergency_stop()
                    time.sleep(1)
            except:
                pass
        elif choice == 'ecs':
            generalState('ecs')
        elif choice == 'id':
            generalState('id')
            input()
        elif choice == 'ls':
            try:
                while True:
                    levelSensors('ls')
                    time.sleep(1)
            except:
                pass
        elif choice == 'lfs':
            levelSensors('lfs')
            input()
        elif choice == 'l1s':
            try:
                while True:
                    levelSensors('l1s')
                    time.sleep(1)
            except:
                pass
        elif choice == 'lf1s':
            levelSensors('lf1s')
            input()
        elif choice == 'lf10':
            levelSensors('lf10')
            input()
        elif choice == 'lf11':
            levelSensors('lf11')
            input()
        elif choice == 'l2s':
            try:
                while True:
                    levelSensors('l2s')
                    time.sleep(1)
            except:
                pass
        elif choice == 'lf2s':
            levelSensors('lf2s')
            input()
        elif choice == 'lf20':
            levelSensors('lf20')
            input()
        elif choice == 'lf21':
            levelSensors('lf21')
            input()
        elif choice == 'ps':
            pump('ps')
            input()
        elif choice == 'pps':
            pump('pps')
            input()
        elif choice == 'pp0':
            pump('pp0')
            input()
        elif choice == 'pp1':
            pump('pp1')
            input()
        elif choice == 'pds':
            pump('pds')
            input()
        elif choice == 'pd0':
            pump('pd0')
            input()
        elif choice == 'pd1':
            pump('pd1')
            input()
        elif choice.find(
                'ps') == 0:  # if the string 'ps' is found, there is possible un number after (to change the pump speed or the pump speed incrementtation)
            if choice.find('psi') == 0:  # if the string 'psi' is found, it's about the pump speed increment
                if choice == 'psis':  # if it's 'psis', show the pump speed incrementation value
                    pump('psis')
                    input()
                else:  # else, there is perhaps a number to update the pump speed incrementation...
                    try:
                        value = int(choice[3:])  # try to extract the number to update the speed incrementation

                        if 0 <= value <= 65000:
                            pasto.set_pump_speed_inc(value)
                            print('\nPump speed incrementation sets to {}\n'.format(value))
                            input()
                        else:
                            print('\nWrong speed incrementation value (0 <= increment <= 65000)\n')
                            input()
                    except:  # if it's not a valid int, continue to 'Wrong command' below
                        print('\nWrong command!\n')
                        input()
            else:  # else, it's about the pump speed
                if choice == 'pss':  # if it's 'pss', show the pump speed value
                    pump('pss')
                    input()
                else:  # else, there is perhaps a number to update the pump speed...
                    try:
                        value = int(choice[2:])  # try to extract the number to update the speed

                        if 0 <= value <= 65000:
                            pasto.set_pump_speed(value)
                            print('\nPump speed sets to {}\n'.format(value))
                            input()
                        else:
                            print('\nWrong speed value (0 <= speed <= 65000)\n')
                            input()
                    except:  # if it's not a valid int, continue to 'Wrong command' print below
                        print('\nWrong command!\n')
                        input()
        elif choice == 'prs':
            try:
                while True:
                    pressSensor('prs')
                    time.sleep(1)
            except:
                pass
        elif choice == 'prfs':
            pressSensor('prfs')
            input()
        elif choice == 'prf0':
            pressSensor('prf0')
            input()
        elif choice == 'prf1':
            pressSensor('prf1')
            input()
        elif choice == 'ss':
            sol('ss')
            input()
        elif choice == 's0':
            sol('s0')
            input()
        elif choice == 's1':
            sol('s1')
            input()
        elif choice == 'tps':
            thermis('tps')
            input()
        elif choice == 'tp0':
            thermis('tp0')
            input()
        elif choice == 'tp1':
            thermis('tp1')
            input()
        elif choice == 'ts':
            try:
                while True:
                    thermis('ts')
                    time.sleep(1)
            except:
                pass
        elif choice == 'ts1':
            try:
                while True:
                    thermis('ts1')
                    time.sleep(1)
            except:
                pass
        elif choice == 'ts2':
            try:
                while True:
                    thermis('ts2')
                    time.sleep(1)
            except:
                pass
        elif choice == 'ts3':
            try:
                while True:
                    thermis('ts3')
                    time.sleep(1)
            except:
                pass
        elif choice == 'ts4':
            try:
                while True:
                    thermis('ts4')
                    time.sleep(1)
            except:
                pass
        elif choice != 'exit' and choice != '':
            print('\nWrong command!\n')
            input()

    pasto.close()
    print("\nBye!\n")

#!/usr/bin/python3
# -*- coding: utf-8 -*-
import term
import time
import sensor
import threading
import traceback

import hardConf


class button(sensor.Sensor):

    typeNum = 13

    def __init__(self,address,param,LED=None):
        try:
            if param < 0:
                pass # MICHA...
            elif hardConf.localGPIOtype == 'gpio':
                hardConf.localGPIO.setup(param, hardConf.gpio_INPUT, pull_up_down=hardConf.gpio_PUD_UP)
            elif hardConf.localGPIOtype == 'pigpio':
                hardConf.localGPIO.set_mode(param, hardConf.gpio_INPUT)
                hardConf.localGPIO.set_pull_up_down(param, hardConf.gpio_PUD_UP)
        except:
            print ("%s: init GPIO no.%d" % (address,param))
            traceback.print_exc()
        self.lastwrite = 0
        self.LED = LED
        super().__init__(button.typeNum,address,param)

    def poll(self):
        value = None
        try:
            if self.param < 0:
                value = hardConf.io.read_discrete( - self.param)
            elif hardConf.localGPIOtype == 'gpio':
                value = hardConf.localGPIO.input(self.param)
            elif hardConf.localGPIOtype == 'pigpio':
                value = hardConf.localGPIO.read(self.param)
            #print ("%d=%d" % (self.param,value))
            #traceback.print_stack()
            value = 0 if value > 0 else 1 # REVERSE because pressing is grounding !!!
        except:
            print ("%s: %d=%d" % (self.address, self.param, value if value != None else 9))
            traceback.print_exc()
        return value

    def acknowledge(self):
        value = self.poll()
        if (value and value > 0.0) or (self.value and self.value > 0.0):
            self.set(0.0)
            return True
        return False

    def display(self,format=" %d"):
        if self.changed < 0.0:
            attr = term.blue
        elif self.changed > 0.0:
            attr = term.red
        else:
            attr = term.black
        term.write(format % self.value, attr, term.bgwhite)

class ThreadButtons (threading.Thread):

    def __init__(self,buttons):
        threading.Thread.__init__(self)
        self.running = False
        self.buttons = []
        for button in buttons: #Take only the existing buttons
            if button:
                self.buttons.append(button)

    def run(self):
        self.running = True
        i = 0
        while self.running:
            try:
                time.sleep(0.1)
                if button.LED:
                    i += 1
                    button.LED.phase = ( i <= 5 ) # Blink twice a second
                    if i >= 10:
                        i = 0
                for button in self.buttons: #Take only the existing buttons
                    time.sleep(0.01)
                    if button.poll() > 0:
                        button.set(1.0)
            except KeyboardInterrupt:
                self.running = False
                break
            except:
                traceback.print_exc()

    def close(self):
        self.running = False
        time.sleep(0.02)
        self.join()

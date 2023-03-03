#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json

class Owner(object): # Info about the Owner of the Pasteurizee

    def __init__(self
                 ,ownerDict:dict = {
                    'name': "akuino"
                    ,'address' : "rue des Vignes 4 / 105"
                    ,'city' : "1435 Mont-Saint-Guibert (Belgique)"
                    ,'mail' : "support@akuino.net"
                }):
        self.name = ownerDict['name']
        self.address = ownerDict['address']
        self.city = ownerDict['city']
        self.mail = ownerDict['mail']

    def to_dict(self):
        return {
            'name' : self.name
            ,'address' : self.address
            ,'city' : self.city
            ,'mail' : self.mail
        }

owner = Owner()

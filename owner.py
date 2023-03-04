#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json

import datafiles

class Owner(object): # Info about the Owner of the Pasteurizee

# Fonction pour lire un objet de la classe courante depuis le disque en utilisant JSON
    def load(dummy = None):
        try:
            objdict = None
            with open(datafiles.ownerfile, 'r') as f:
                objdict = json.load(f)
                #print(objdict)
            return Owner(objdict)
        except:
            pass
        temp = Owner(None)
        temp.save()
        return temp

    def __init__(self, ownerDict:dict = None):
        if not ownerDict:
            ownerDict = {
                'name': "akuino"
                ,'address' : "rue des Vignes 4 / 105"
                ,'city' : "1435 Mont-Saint-Guibert (Belgique)"
                ,'mail' : "support@akuino.net"
            }
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

    # Fonction pour sauvegarder un objet de la classe courante en utilisant JSON
    def save(self):
        with open(datafiles.ownerfile, 'w') as f:
            json.dump(self.to_dict(),f)

owner = Owner.load(None)

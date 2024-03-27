#!/usr/bin/python3
# -*- coding: utf-8 -*-

lang = 'f' # default current language

allowed = 'efn'

def setLang(some_lang):
    global lang, allowed
    some_lang = some_lang.lower()
    if some_lang in allowed:
        lang = some_lang
        return True
    return False

# manages Multilinguism
# Initialized using t("français","english","nederlands")
# and accessed using .t property
class T(object):

    def __init__(self,f=None,e=None,n=None):
        self.french = f if f else (e if e else n)
        self.english = e if e else (f if f else n)
        self.dutch = n if n else (e if e else f)

    def __str__(self):

        global lang

        if lang == 'f':
            return self.french
        elif lang == 'n':
            return self.dutch
        else:
            return self.english

if __name__ == "__main__":
    if setLang('n'):
        print ('OK')
    print (T("français","english","nederlands"))

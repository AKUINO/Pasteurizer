import os
import datetime

DIR_BASE = os.path.dirname(os.path.abspath(__file__)) + '/'

# TO BE CALLED AT BEGINNING OF APPLICATION
def goto_application_root():
    if not os.path.samefile(os.getcwd(), DIR_BASE):
        os.chdir(DIR_BASE)

DIR_STATIC = os.path.join(DIR_BASE, 'static/')
URL_STATIC = u'/static/'

DIR_DATA_CSV = os.path.join(DIR_BASE, 'csv/')

DIR_DATA_REPORT = os.path.join(DIR_BASE, 'report/')

DIR_WEB_TEMP = os.path.join(DIR_STATIC, 'temp/')

TEMPLATES_DIR = os.path.join(DIR_BASE, 'templates/')

FILENAME_FORMAT = "%Y_%m%d_%H%M"
logfile = datetime.datetime.now().strftime(FILENAME_FORMAT)

def csvfile(fileName):
    return DIR_DATA_CSV + fileName + ".csv"

def reportfile(fileName): # always begin with 2 !
    return DIR_DATA_REPORT + fileName + ".json"

ownerfile = DIR_DATA_REPORT + "owner.json" # do not begins with 2 !

def static_filepath( subdir, filename):
    return (os.path.join(DIR_STATIC,subdir+'/') if subdir else DIR_STATIC) + filename




import os
import datetime
from pathlib import Path

DIR_BASE = os.path.dirname(os.path.abspath(__file__)) + '/'

# TO BE CALLED AT BEGINNING OF APPLICATION
def goto_application_root():
    if not os.path.samefile(os.getcwd(), DIR_BASE):
        os.chdir(DIR_BASE)

DIR_STATIC = os.path.join(DIR_BASE, 'static/')
URL_STATIC = u'/static/'

DIR_BASE_DATA = os.path.join(DIR_BASE, '../PasteurizerData')
if not os.path.exists(DIR_BASE_DATA):
    os.mkdir(DIR_BASE_DATA)
DIR_BASE_DATA = DIR_BASE_DATA + '/'

if (os.path.exists(os.path.join(DIR_BASE, 'calib'))):
    os.rename(os.path.join(DIR_BASE, 'calib'),os.path.join(DIR_BASE_DATA, 'calib'))
DIR_DATA_CALIB = os.path.join(DIR_BASE_DATA, 'calib/')

if (os.path.exists(os.path.join(DIR_BASE, 'csv'))):
    os.rename(os.path.join(DIR_BASE, 'csv'),os.path.join(DIR_BASE_DATA, 'csv'))
DIR_DATA_CSV = os.path.join(DIR_BASE_DATA, 'csv/')

if (os.path.exists(os.path.join(DIR_BASE, 'report'))):
    os.rename(os.path.join(DIR_BASE, 'report'),os.path.join(DIR_BASE_DATA, 'report'))
DIR_DATA_REPORT = os.path.join(DIR_BASE_DATA, 'report/')

if (os.path.exists(os.path.join(DIR_BASE, 'param'))):
    os.rename(os.path.join(DIR_BASE, 'param'),os.path.join(DIR_BASE_DATA, 'param'))
DIR_DATA_PARAM = os.path.join(DIR_BASE_DATA, 'param/')

DIR_WEB_TEMP = os.path.join(DIR_STATIC, 'temp/')
TEMPLATES_DIR = os.path.join(DIR_BASE, 'templates/')

FILENAME_FORMAT = "%Y_%m%d_%H%M"
logfile = datetime.datetime.now().strftime(FILENAME_FORMAT)

def calibfile(fileName):
    return DIR_DATA_CALIB + fileName + ".csv"

def linearfile(fileName):
    return DIR_DATA_CALIB + fileName + ".json"

def csvfile(fileName):
    return DIR_DATA_CSV + fileName + ".csv"

def reportfile(fileName):
    return DIR_DATA_REPORT + fileName + ".json"

def paramfile(fileName):
    return DIR_DATA_PARAM + fileName # WITH EXTENSION !

ownerfile = DIR_DATA_PARAM + "owner.json"

def static_dirpath( subdir, filename):
    return (os.path.join(DIR_STATIC,subdir+'/') if subdir else DIR_STATIC) + filename

def static_filepath( subdir, filename):
    return (os.path.join(DIR_STATIC,subdir+'/') if subdir else DIR_STATIC) + filename

# Ensures Data directories exist
Path(static_dirpath(DIR_DATA_CALIB,"")).mkdir(parents=True, exist_ok=True)
Path(static_dirpath(DIR_DATA_CSV,"")).mkdir(parents=True, exist_ok=True)
Path(static_dirpath(DIR_DATA_REPORT,"")).mkdir(parents=True, exist_ok=True)
Path(static_dirpath(DIR_DATA_PARAM,"")).mkdir(parents=True, exist_ok=True)

''' 
    Author : Ankit Kr. Sahu
    Fabric utility to run vic model dialy on the given input data and generate cumulative report.
'''

from fabric.state import output
import threading
from ftplib import FTP
from fabric.operations import *
from StringIO import StringIO
from fabric.colors import *
from pytz import timezone
from fabric.api import *
import subprocess
import datetime
import string
import time
import sys
import os
import ftplib
import pysftp
import logging
from datetime import timedelta

logging.basicConfig()

# set DEBUG to true or false to disable/enable the file upload functionality
DEBUG = True

#NRSC ftp details.
NRSC_HOST = "ftp1.nrsc.gov.in"
NRSC_USER = "APWRD"
NRSC_PASS = "apwrd$123"
OUT_TXT = "OUT_TXT"
INP_MET = "INP_MET"
OUT_FLUX = "OUT_FLUX"

#input ftp ip
# IP = '52.41.48.202'
IP = '54.191.217.243'
VIC_PORT = 21
VIC_USER = "vicftp"
VIC_PASS = "vic@vassar"
FTP_INPUT_DIR = 'input/kgbasin' #'pub'
FTP_OUTPUT_DIR = 'output/kgbasin' #'pub/output'
PLAY_MACHINE_ADDR = "ubuntu@ec2-34-217-79-156.us-west-2.compute.amazonaws.com"
#output iwm ftp details
OUT_FTP_ADDR = "ftp://iwmftp:iwm@vassar@iwm.vassarlabs.com"
OUT_FTP_DIR = "kgbasin" #"nrsc"

#------------Configurables----------------------------------------------------
#pem filep ath
PEM_FILE_PATH = "~/AWS/iwm-cassandra-play.pem"

# global date variable to contain date in format YYYYMMDD. It will be updated later
HOME_DIR = "/home/iwm-ui/VIC/Vic/"
ROUTING_HOME_DIR = "/home/iwm-ui/VIC/Rout"

INP_MET_DATA_DIR_PATH = "Vic_Model/VIC_Inputs/3min_VIC_APSDPS_SETUP/MetData"
CONF_FILE_DIR = "Vic_Model/VIC_Inputs/3min_VIC_APSDPS_SETUP/Global parameter/"
CONF_FILE_NAME = "global_param_3min_APSDPS"

#-----------------------------------------------------------------------------
#Set till what date the model should run. Initialized to random value. It will get update later.
#Initialized numbers have no significance here. They will be updated later.
till_year = 2017
till_month = 06
till_day = 12

#Store the last processed met file name and current met file name. This is required to avoid re-computation.
LAST_MET_ZIP = ""
LATEST_MET_ZIP = ""     #we can put the name here manually as well. Remember to reset to "" before deployment
date = "" 

'''uncomment below one when we are providing the MET FILE MANUALLY
so that it doesn't download the file. Comment it out otherwise.'''
date = LATEST_MET_ZIP.split("_")[0]

#Directory that contains VIC OUTPUT Flux files for each day
OUT_DIR_NAME = "VIC_OUTPUT"
#Directory that contains final text files for each grid for each day
REPORT_DIR_NAME = "VIC_DAILY"
#Directory from where VIC Model takes daily met data input. To be updated later in init() method
INP_MET_DATA_SUB_DIR_PATH = ""
#Directory to which MET Data file is downloaded daily
FTP_MET_DATA_DIR = HOME_DIR + "FTP_MET_DATA"
#Path to VIC Configuration file
CONF_FILE_PATH = HOME_DIR + CONF_FILE_DIR + CONF_FILE_NAME

#VIC output subfolder path. Name signifies output folder for that day
VIC_FLUX_OUT_DIR = HOME_DIR + OUT_DIR_NAME
#. To be updated later in init() method
VIC_FLUX_OUT_SUB_DIR = ""

#Input flux source folder for VIC Routing model
VIC_ROUTING_FLUX_SOURCE = ROUTING_HOME_DIR + "/flux"
VIC_ROUTING_POINTS_INP_DIR = ROUTING_HOME_DIR + "/input"
VIC_ROUTING_POINTS_OUT_DIR = ROUTING_HOME_DIR + "/output"
#Directory that contains daily report(.txt) files generated using output fluxes. Name signifies output folder for that day
DAILY_REPORT_DIR = HOME_DIR + REPORT_DIR_NAME
#. To be updated later in init() method
DAILY_REPORT_SUB_DIR = ""

# vic_input_dir = HOME_DIR + IN_DIR_NAME
# vic_input_sub_dir = vic_input_dir + "/" + str(date)

#LFTP Conf file that downloads met data zip file daily from lftp server
LFTP_DWLD_SCRIPT = HOME_DIR + "lftp_file_download"

SECONDS_IN_DAY = 24*60*60
SECONDS_IN_HOUR = 60*60
VIC_MODEL_RETRY_FREQUENCY = 2*60
VIC_MODEL_RUN_FREQUENCY = 10*60
ONE_MINUTE = 30

tags = [
    '# year model simulation ends', 
    '# month model simulation ends', 
    '# day model simulation ends', 
    '# Forcing file path and prefix, ending in "_"',
    # '# Soil parameter path/file',
    # '# Veg parameter path/file',
    # '# Veg library path/file',
    '# Results directory path'
]

updated_line_value = []

def init():
    #Date variable is initialized in download_latest_file method.
    global date
    global INP_MET_DATA_SUB_DIR_PATH
    global VIC_FLUX_OUT_SUB_DIR
    global DAILY_REPORT_SUB_DIR

    # date = datetime.datetime.today().strftime('%Y-%m-%d')
    INP_MET_DATA_SUB_DIR_PATH = HOME_DIR + INP_MET_DATA_DIR_PATH + "/" + str(date)
    VIC_FLUX_OUT_SUB_DIR = VIC_FLUX_OUT_DIR + "/" + str(date)
    DAILY_REPORT_SUB_DIR = DAILY_REPORT_DIR + "/" + str(date)


''' entry point for our vic model
    The following function will run itself every 24 hr, performing all the operations required
'''

def run_vic_model():
    global LATEST_MET_ZIP
    while True:
        # threading.Timer(frequency, run_vic_model).start()
        now = datetime.datetime.now()
        start_ts = int(round(time.time()))
        print(green("\n\nInitiating VIC Model computation at : " + str(now.strftime("%Y-%m-%d %H:%M"))))
        
        result = {}
        result['status'] = 0

        #if we have provided name manually then we do not need to trigger file download script
        if LATEST_MET_ZIP == "":
            result = download_latest_file()
        
        #initialize all the directory paths.
        init()
        
        # checks if the file we found is already processed or not. If yes then rest of the methods will be skipped
        # if result['status'] == 0:
        #     result = is_file_processed()

        if result['status'] == 0:
            result = update_directories()

        if result['status'] == 0:
            result = copy_input_files()

        if result['status'] == 0:
            #update the conf file
            result = init_conf_file_updation()

        if result['status'] == 0:
            #run vic model
            result = run_model()

        if result['status'] == 0:
            #process flux files to generate cumulative report
            # generate_final_file()
            init_vic_routing()

        # print(green("\n\nCleaning up temporary files created."))
        # cleanup()

        end_ts = int(round(time.time()))
        now = datetime.datetime.now()

        if(result['status'] == 1):
            print(red("\n" + result['msg']))
            time.sleep(VIC_MODEL_RETRY_FREQUENCY)
        else:
            print(green("\n\nVIC Model computation finished at : " + str(now.strftime("%Y-%m-%d %H:%M"))))
            print(green("\nTotal time taken : " + str(end_ts-start_ts) + "s"))
            time.sleep(VIC_MODEL_RUN_FREQUENCY)

        # reset this variable to force model to look into ftp for latest file.
        LATEST_MET_ZIP = ""

'''
This method will clean up all the temporary files that were created while running the VIC and
Routing model
'''
def cleanup():
    print(green("\nRemoving input metdata file."))
    cmd = "rm -r " + MET_DATA_INP_FILES_DIR
    local(cmd, capture=True)

''' This method will update the configuration file for the vic model. Commonly updated 
    fields are end date, output direcotory path and vic input file path.
'''
def init_conf_file_updation():
    try:
        MET_DATA_INP_FILES_DIR = INP_MET_DATA_SUB_DIR_PATH + "/" + str(LATEST_MET_ZIP.split(".")[0])
        print(green("MET_DATA_INP_FILES_DIR : " + MET_DATA_INP_FILES_DIR))
        updated_line_value = []
        updated_line_value.append('ENDYEAR  ' + str(till_year) + '    # year model simulation ends')
        updated_line_value.append('ENDMONTH ' + str(till_month) + '  # month model simulation ends')
        updated_line_value.append('ENDDAY      ' + str(till_day) + '  # day model simulation ends')
        updated_line_value.append('FORCING1    ' + str(MET_DATA_INP_FILES_DIR) + '/data_     # Forcing file path and prefix, ending in "_"   ')
        # SOIL          /home/iwm-ui/Vic_Model/VIC_Inputs/3min_VIC_APSDPS_SETUP/Soil_parameter/3min_soil_AP_VIC_20170531.txt          # Soil parameter path/file
        # VEGPARAM      /home/iwm-ui/Vic_Model/VIC_Inputs/3min_VIC_APSDPS_SETUP/Vegetation_Parameter/3min_AP_VP_kharif.txt                        # Veg parameter path/file
        # VEGLIB         /home/iwm-ui/Vic_Model/VIC_Inputs/3min_VIC_APSDPS_SETUP/Vegetation_Parameter/3min_AP_VL.txt                      # Veg library path/file
        updated_line_value.append('RESULT_DIR   ' +  str(VIC_FLUX_OUT_SUB_DIR)  + ' # Results directory path')
        print(green("VIC_FLUX_OUT_SUB_DIR : " + VIC_FLUX_OUT_SUB_DIR))
        #open the conf file and update the lines which are needed to be updated
        #the following code will update the required lines in the conf file and create a temporary file
        #which will later replace the original conf file
        
        orig_conf_file_path = CONF_FILE_PATH
        j=0

        #create temp conf file and update it with the latest data
        print(green("\n\nCreating temporary Global params conf file"))
        tf_name = "temp"
        tf_path = HOME_DIR + CONF_FILE_DIR + tf_name
        temp_file = open(tf_path, "a+b")
        temp_file.seek(0)
        temp_file.truncate()
        print(green("Temporary Global params conf file created"))
        print(green("Reading original Global params conf file and updating required rows."))
        with open(orig_conf_file_path) as f:
            f.seek(0)
            #read the file content line by line
            content = f.readlines()
            #remove the trailing whitespaces
            content = [x.strip() for x in content]
            #iterate all the rows from number 6 till the end and search for the given date in the given file
            for i in range(0,len(content)):
                #split the data of each row
                row_data = content[i]
                # print tags
                # print row_data
                if j < len(tags) and tags[j] in row_data:
                    temp_file.write(updated_line_value[j]+"\n")
                    # print row_data
                    j=j+1
                else:
                    temp_file.write(row_data+"\n")

            f.close()
            temp_file.close()
            print(green("Global params conf file has been updated."))
            
        #now the temporary updated conf file is created. Remove the original file and rename temp conf file 
        #to that of original conf file name.
        print(green("\nReplacing old Global params conf file with the new one."))
        with lcd(HOME_DIR+CONF_FILE_DIR):
            with hide('output','running','warnings'):
                with settings(warn_only=True):
                    cmd = "rm " + CONF_FILE_NAME
                    # print cmd
                    msg = local(cmd, capture=True)
                    # print msg
                    cmd = "mv " +  tf_name + " " + CONF_FILE_NAME
                    # print cmd
                    local(cmd, capture=True)
                    print(green("Old Global params conf file has been successfully replaced with the new one."))
        
        # temp_file.flush()
        # temp_file.close()
    except Exception as e:
        # print(red("FATAL : \n" + str(e)))
        return {"msg":"method : init_conf_file_updation : FATAL : " + str(e), "status":1}

    return {"msg":"","status":0}


def download_latest_file():
    try:
        # curr date based on which the file will be fetched
        # date = datetime.datetime.today().strftime('%Y%m%d')

        global date
        global LATEST_MET_ZIP
        global LAST_MET_ZIP

        #get the latest file name from the ftp. ls -altr | grep '^-'
        # with hide('output','running','warnings'):
        #     with settings(warn_only=True):
        #         cmd = 'lftp -u anonymous, -e "ls -altr | grep ''^-''; quit" ' + IP + '/' + FTP_INPUT_DIR + ' | tail -n 1'
        #         # cmd = 'lftp -u anonymous, -e "ls -rt; quit" 52.41.48.202/pub | tail -n 1'
        #         msg = local(cmd, capture=True)
        #         latest_fname = msg.split(" ")[len(msg.split(" "))-1]

        LATEST_MET_ZIP = getLatestMetFile()
        latest_fname = LATEST_MET_ZIP.split("##")[0]    #since method returns in format <filename>##<timestamp>

        if LATEST_MET_ZIP == LAST_MET_ZIP:
            return {"msg":"Latest file Name : " + str(latest_fname) + " on ftp has already been processed.", "status":1}

        if latest_fname in ('', ' '):
            return {"msg":"method : download_latest_file : Invalid filename observed. Aborting.", "status":1}

        LAST_MET_ZIP = LATEST_MET_ZIP   #LAST_MET_ZIP will have zipname.zip along with timestamp, separated by '##'.
        LATEST_MET_ZIP = latest_fname   #LATEST_MET_ZIP should always have zipname.zip
        timestamp = ''
        if len(LAST_MET_ZIP.split("##")) == 2:
            timestamp = LAST_MET_ZIP.split("##")[1]
        print(green("\nLatest file available on FTP : " + latest_fname + " with TS : " + str(timestamp)))
        '''for now disabling this date assignment. Later on it must be enabled and taken from 
        the zip filename instead once that is corrected'''
        date = latest_fname.split("_")[0]
        # date = datetime.datetime.now().strftime("%Y%m%d")

        with hide('output','running','warnings'):
            #first update lftp conf file so that it fetches the latest file from the ftp
            # print(green("\nPreparing script to download latest file from FTP."))
            # # manually write all the commands that will transfer files to the required directory
            # with hide('output','running','warnings'):
            #     with settings(warn_only=True):
            #         cmd = "echo open " + IP + " > " + LFTP_DWLD_SCRIPT
            #         local(cmd, capture=True)
            #         cmd = "echo cd pub >> " + LFTP_DWLD_SCRIPT
            #         local(cmd, capture=True)
            #         cmd = "echo mget -E " + str(date) + "* >> " + LFTP_DWLD_SCRIPT
            #         local(cmd, capture=True)
            # print(green("Script to download latest file has been prepared."))
            # print(green("Downloading new file from the lftp server"))
            # cmd = "lftp -f " + LFTP_DWLD_SCRIPT
            # msg = local(cmd, capture=True)
            # print(green("File has been downloaded from the server. "))
            
            print(green("Downloading latest file from the FTP server"))
            filepath = FTP_MET_DATA_DIR + "/" + latest_fname
            downloadFile(filepath)
            print(green("File has been downloaded from the server. "))
            # transferring latest file to NRSC Server FTP
            # if not DEBUG:
            #     print(green("Transferrring latest met file to NRSC server."))
            #     transferFileToNRSC((FTP_MET_DATA_DIR+"/"+latest_fname), INP_MET)
                    
        return {"msg":"", "status":0}
    except Exception as e:
        return {"msg":"method : download_latest_file : FATAL : exception occurred : " + str(e), "status":1}


def is_file_processed():
    try:
        with hide('output','running','warnings'):
            with settings(warn_only=True):
                exists = local("if test -d " + FTP_MET_DATA_DIR + "; then echo 'True'; else echo 'False'; fi", capture=True)
                if exists == 'True':
                    cmd = "ls -Art " + FTP_MET_DATA_DIR + " | tail -n 1"
                    msg = local(cmd, capture=True)
                    global LATEST_MET_ZIP
                    global LAST_MET_ZIP

                    LATEST_MET_ZIP = msg

                    if LATEST_MET_ZIP == str(LAST_MET_ZIP):
                        return {"msg":"method : is_file_processed : VIC Model for latest met data has already been run. Last Met_data File Processed : " + str(LAST_MET_ZIP), "status":1}

                    LAST_MET_ZIP = LATEST_MET_ZIP

    except Exception as e:
        return {"msg" : "method : is_file_processed : FATAL : " + str(e), "status":1}

    return {"msg":"", "status":0}

'''Copy the input data files to the desired location'''
def copy_input_files():
    global LATEST_MET_ZIP
    print(green("\n\nCopying input files from ftp folder to vic input dir."))
    with hide('output','running','warnings'):
        with settings(warn_only=True):
            #copy the file to the input met dir
            cmd = "cp " + FTP_MET_DATA_DIR + "/" + LATEST_MET_ZIP + " " + INP_MET_DATA_SUB_DIR_PATH
            msg = local(cmd, capture=True)

            #extract the file
            with lcd(INP_MET_DATA_SUB_DIR_PATH):
                # cmd = "unzip -o " + INP_MET_DATA_SUB_DIR_PATH + "/" + LATEST_MET_ZIP
                cmd = "unzip -o " + INP_MET_DATA_SUB_DIR_PATH + "/" + LATEST_MET_ZIP + " -d " + str(LATEST_MET_ZIP.split(".")[0])
                print "extract cmd : " + str(cmd)
                msg = local(cmd, capture=True)

            #set till what date we have the data in the file we are receiving
            # print LATEST_MET_ZIP
            to_date = LATEST_MET_ZIP.split(".")[0].split("_")[1]
            
            #TODO: clean up met_dir_name
            global met_dir_name
            global till_year
            global till_month
            global till_day

            # met_dir_name = LATEST_MET_ZIP.split(".")[0]
            till_year = to_date[0:4]
            till_month = to_date[4:6]
            till_day = to_date[6:]
            print(green("Input file from ftp folder has been copied and extracted."))

    return {"msg":"","status":0}

''' create directory. If exists then remove and re-create. Removal is done so as to prevent any data inconsistency while
    writing back to this directory.
'''
def removeAndCreateDirectory(dir_path):
    removeDirectory(dir_path)
    createDirectory(dir_path)

''' create directory. If exists then remove and re-create. Removal is done so as to prevent any data inconsistency while
    writing back to this directory.
'''
def createDirectory(dir_path):
    exists = local("if test -d " + dir_path + "; then echo 'True'; else echo 'False'; fi", capture=True)
    if exists == 'False':
        print(red("\n" + dir_path + " directory doesn't exist. Creating one."))
        cmd = "mkdir " + dir_path
        local(cmd, capture=True)
        print(green("\n" + dir_path + " directory created successfully."))
    else:
        print(green("\n" + dir_path + " directory already exists."))


'''remove directory'''
def removeDirectory(dir_path):
    try:
        print(red("\nRemoving " + dir_path + " directory."))
        cmd = "rm -r " + dir_path
        local(cmd, capture=True)
        print(green("\n" + dir_path + " directory removed successfully."))
    except:
        print("Directory doesn't exist. Skipping.")


''' function that creates necessary directory for working '''
def update_directories():
    print(green("\nStarting to create necessary directories"))
    #check if required directories exist or not. If not then create them.
    try:
        createDirectory(VIC_FLUX_OUT_DIR)
        createDirectory(DAILY_REPORT_DIR)
        removeAndCreateDirectory(VIC_FLUX_OUT_SUB_DIR)
        removeAndCreateDirectory(DAILY_REPORT_SUB_DIR)
        removeAndCreateDirectory(INP_MET_DATA_SUB_DIR_PATH)
        # exists = local("if test -d " + VIC_FLUX_OUT_DIR + "; then echo 'True'; else echo 'False'; fi", capture=True)
        # if exists == 'False':
        #     createDirectory(VIC_FLUX_OUT_DIR)

        # exists = local("if test -d " + VIC_FLUX_OUT_SUB_DIR + "; then echo 'True'; else echo 'False'; fi", capture=True)
        # if exists == 'False':
        #     createDirectory(VIC_FLUX_OUT_SUB_DIR)

        # #check if cumulative data directory exists or not
        # exists = local("if test -d " + DAILY_REPORT_DIR + "; then echo 'True'; else echo 'False'; fi", capture=True)
        # if exists == 'False':
        #     createDirectory(DAILY_REPORT_DIR)

        # exists = local("if test -d " + DAILY_REPORT_SUB_DIR + "; then echo 'True'; else echo 'False'; fi", capture=True)
        # if exists == 'False':
        #     createDirectory(DAILY_REPORT_SUB_DIR)
        # else:
        #     removeDirectory(DAILY_REPORT_SUB_DIR)
        #     createDirectory(DAILY_REPORT_SUB_DIR)

        # #check if met data folder exists
        # exists = local("if test -d " + INP_MET_DATA_SUB_DIR_PATH + "; then echo 'True'; else echo 'False'; fi", capture=True)
        # if exists == 'False':
        #     createDirectory(INP_MET_DATA_SUB_DIR_PATH)

        print(green("All necessary directories have been created."))
        return {"msg":"", "status":0}
    
    except Exception as e:
        return {"msg":"method : update_directories : FATAL : Error while creating directories"}



'''function that reads all the flux files in the given output directory and combine the data from all the files into one file which we need'''
def generate_final_file():
    
    global LATEST_MET_ZIP
    #date format YYYYMMDD
    global date
    
    curr_year = date[0:4]
    curr_month = date[4:6]
    curr_day = date[6:]

    file_start_ts = time.mktime(datetime.datetime.strptime(date, "%Y%m%d").timetuple())

    #hard coding start day to be june 1 2017
    # fromDate = "20170601" #LATEST_MET_ZIP.split(".")[0].split("_")[0]
    toDate = LATEST_MET_ZIP.split(".")[0].split("_")[1]

    # from_year = (int)(fromDate[0:4])
    # from_month = (int)(fromDate[4:6])
    # from_day = (int)(fromDate[6:])
                
    global till_year
    global till_month
    global till_day

    till_year = (int)(toDate[0:4])
    till_month = (int)(toDate[4:6])
    till_day = (int)(toDate[6:])

    # start = datetime.date(year=from_year,day=from_day,month=from_month)
    
    #for each day between start and end create one cumulative file
    # curr = start 

    loop = True

    # create zip for daily output text files. later delete this file when the use case finishes
    daily_zip_name = str(date) + ".zip"
    #This particular code within try except block transfers flux output to NRSC
    try:
        with lcd(VIC_FLUX_OUT_DIR):
            print(green("\nCreating flux output as zip file to transfer it to NRSC."))
            cmd = "zip -r " + daily_zip_name + " " + str(date)
            local(cmd, capture=True)
            print(green("Zipping done."))
            print(green("Transferring flux output to NRSC server."))
            transferFileToNRSC((VIC_FLUX_OUT_DIR + "/" + daily_zip_name), OUT_FLUX)
            print(green("\nTransfer done. Removing temporary file created."))
            cmd = "rm " + daily_zip_name
            local(cmd, capture=True)
            print(green("\nTemporary file removed."))
    except Exception as e:
        print(red("Some error occurred while transferring file to NRSC server. Check log.txt for more information"))
        cmd = "echo '" + date + ":" + str(e) + "' >> log.txt"
        local(cmd, capture=True)
    
    #change pwd to vic output directory
    #below code reads each and every individual flux file and then creates daily file to be uploaded to the server for use.
    #for current purpose we do not need to process this at all.
    if not DEBUG and False:
        try:
            with lcd(VIC_FLUX_OUT_SUB_DIR):
                #run ls command to see the all the files present in the output folder
                with hide('output','running','warnings'):
                    with settings(warn_only=True):
                        # print(green("Removing all snow files (if any)"))
                        # cmd = "rm snow_*"
                        # msg = local(cmd, capture=True)
                        # print(green("All snow files removed."))
                        
                        print(green("\n\nReading VIC_OUTPUT directory for required data files..."))
                        cmd =  "ls"
                        msg = local(cmd, capture=True)
                        files = string.split(msg, '\n')
                        # print(files)
                        print(green("Directory scanned. Number of o/p data files : " + str(len(files))))
                        # print files
                        '''
                        Logic :
                            for all the files in the current directory:
                                get the data for the requested date from the file and store it in the output file in the requested format.
                        '''
                        print(green("Reading o/p flux files and packing data in individual files"))
                        i=0
                        
                        start_ts = int(round(time.time()))
                        for idx, file in enumerate(files):
                            if "snow_" in str(file):
                                continue
                            #split the file name to read lat and long
                            sys.stdout.write("Current File : " + str(file) + " .... Progress : " + str(idx+1) + "/" + str(len(files)) + " .... " + str((idx+1)*100/len(files)) + "%\r")
                            sys.stdout.flush()
                            # print "file : " + str(file) + " Progress : " + str(idx+1) + "/" + str(len(files)) + " .... " + str((idx+1)*100/len(files)) + "%"
                            f_parts = str(file).split("_")
                            lat = str(f_parts[1])
                            lon = str(f_parts[2])

                            #actual path of the file which we need to read
                            file_path = VIC_FLUX_OUT_SUB_DIR+"/"+str(file)
                            with open(file_path) as f:
                                #read the file content line by line
                                content = f.readlines()
                                #remove the trailing whitespaces
                                content = [x.strip() for x in content]
                                #iterate all the rows from number 6 till the end and search for the given date in the given file
                                for i in range(6,len(content)):
                                    #split the data of each row
                                    row_data = content[i].split("\t")
                                    # print "row : " + str(row_data)
                                    #get the row that corresponds to the requested date
                                    _date = row_data[2]
                                    _month = row_data[1]
                                    _year = row_data[0]

                                    #Zubaeyr requested to subtract one day from the vic output. i.e today's o/p is actually yest. data
                                    #remove below lines till 'till here' tag to undo this change
                                    _yest_obj = datetime.date(year=int(_year),day=int(_date),month=int(_month)) - timedelta(days=1)
                                    _date = str('%02d' %_yest_obj.day)
                                    _month = str('%02d' %_yest_obj.month)
                                    _year = str(_yest_obj.year)
                                    #till here

                                    curr_ts = time.mktime(datetime.datetime.strptime(_year+_month+_date, "%Y%m%d").timetuple())
                                    if curr_ts < file_start_ts:
                                        fname = "NRSC_VIC_AP_3min_WBC_" + _year + _month + _date + ".txt"
                                    else:
                                        fname = "NRSC_VIC_AP_3min_WBC_FORECAST_" + _year + _month + _date + ".txt"

                                    
                                    out_file_name = DAILY_REPORT_SUB_DIR + "/" + fname

                                    # print out_file_name
                                    evapo = round((float)(row_data[4].strip()),3)
                                    runoff = round((float)(row_data[5].strip()),3)
                                    sm1 = round(((float)(row_data[7].strip()))/50,3)
                                    sm2 = round(((float)(row_data[8].strip()))/450,3)
                                    sm3 = round(((float)(row_data[9].strip()))/1000,3)
                                    et = round((float)(row_data[12].strip()),3)
                                    short_grass = round((float)(row_data[13].strip()),3)
                                    baseflow = round((float)(row_data[6].strip()),3)
                                    satsoil = round((float)(row_data[14].strip()),3)
                                    h2osurf = round((float)(row_data[15].strip()),3)
                                    # cmd = "echo '" + str(idx+1) + " " + lat + " " + lon +" " + str(evapo) +  " " + str(runoff) + " " + str(sm1) + " " + str(sm2) + " " + str(sm3) + " "  + str(et) + " " + str(short_grass) + " " + str(body_evapo) + "' >> " + out_file_name
                                    cmd = "echo '" + str(idx+1) + " " + lat + " " + lon +" " + str(evapo) +  " " + str(runoff) + " " + str(sm1) + " " + str(sm2) + " " + str(sm3) + " "  + str(et) + " " + str(short_grass) + " " + str(baseflow) + " " + str(satsoil) + " " + str(h2osurf) + "' >> " + out_file_name
                                    # # print cmd
                                    local(cmd, capture=True)

                        end_ts = int(round(time.time()))
                        print(green("\nData from all flux files has been processed. Time taken : " + str(end_ts-start_ts) + "s"))
         
            #below is the code which used to upload zip on old ftp 
            #taking backup on old ftp for the same file in zipped format as well.
            # print(green("\n\nTaking backup on $storm machine lftp server."))
            # print(green("Zipping the directory containing all output files..."))
            #For current purpose we don't need to transfer files at all
            if not DEBUG and False:    
                with lcd(DAILY_REPORT_DIR):
                    with hide('output','running','warnings'):
                        with settings(warn_only=True):
                            # zip_file_name = str(date) + ".zip"
                            zip_file_name = "vic_files.zip"
                            print(green("Copying computed files to vic_files for zipping"))
                            # clean up old files in the directory
                            cmd = "rm vic_files/* vic_files.zip"
                            local(cmd, capture=True)

                            # copy new computed files to vic_files directory for zipping
                            cmd = "cp -R " + str(date) + "/* vic_files"
                            local(cmd, capture=True)
                            print(green("Copied computed files to vic_files for zipping"))

                            # zip the directory
                            cmd = "zip -r " + zip_file_name + " vic_files"
                            local(cmd, capture=True)
                            print(green("Zipping completed."))
                            
                            # transfer the file to $storm machine
                            print(green("Transferring zip file to $storm ftp..."))
                            cmd = 'lftp -c "open ' + IP + '; put -O ' + FTP_OUTPUT_DIR + ' ' + DAILY_REPORT_DIR + '/' + zip_file_name + '"'
                            print("command used : " + cmd)
                            local(cmd, capture=True)
                            print(green("Backup on $storm machine lftp server completed."))

                            # transfer the file to cassandra system
                            print(green("\nTransferring zip to cassandra stagin machine"))
                            cmd="scp -i " + PEM_FILE_PATH + " " + DAILY_REPORT_DIR + "/" + zip_file_name + " " + PLAY_MACHINE_ADDR + ":~/../iwmftp/nrsc/"
                            print("command used : " + cmd)
                            local(cmd, capture=True)
                            print(green("\nFile Transferred to cassandra stagin machine"))

                            print(green("\nCreating text output as zip file to transfer it to NRSC."))
                            cmd = "zip -r " + daily_zip_name + " " + str(date)
                            local(cmd, capture=True)
                            print(green("Zipping done."))
                            print(green("\nTransferring text file zip to NRSC."))
                            transferFileToNRSC((DAILY_REPORT_DIR + "/" + daily_zip_name), OUT_TXT)
                            print(green("\nTransfer completed"))
                            print(green("\nRemoving temporary file created"))
                            cmd = "rm " + daily_zip_name
                            local(cmd, capture=True)
                            print(green("\nTemporary file removed"))

                #below is the code that transfers each file one by one to the new FTP server where it is taken by Zubair's service to 
                #insert into our db.
                try:
                    start_ts = int(round(time.time()))
                    print(green("\n\nStarted transferring file to IWM FTP at : " + str(start_ts)))
                    with lcd(DAILY_REPORT_DIR+"/"+date):
                        with hide('output','running','warnings'):
                            with settings(warn_only=True):
                                cmd = "ls"
                                msg = local(cmd, capture=True)
                                files = msg.split()
                                # print msg

                                for idx, file in enumerate(files):
                                    sys.stdout.write("Current File : " + str(file) + " .... Progress : " + str(idx+1) + "/" + str(len(files)) + " .... " + str((idx+1)*100/len(files)) + "%\r")
                                    sys.stdout.flush()
                                    cmd = "lftp -c \"open " + OUT_FTP_ADDR + "; put -O " + OUT_FTP_DIR+ " '" + file + "'\""
                                    msg = local(cmd, capture = True)
                                    # print msg

                    end_ts = int(round(time.time()))
                    print(green("\nCompleted files transfer to FTP at : " + str(end_ts) + " Total time taken : " + str(end_ts-start_ts) +"s"))
                except Exception as e:
                    return{"msg":"method : generate_final_file : Exception while transferring individual files to ftp : " + e, "status":1}

                        
        except Exception as e:
            return {"msg":"FATAL : exception : " + str(e), "status":1}


def init_vic_routing():
    #global date
    #comment this below hard coding once production starts
    #VIC_FLUX_OUT_SUB_DIR = "/home/iwm-ui/VIC/Vic/VIC_OUTPUT/20180626"
    
    print(green("Starting to run VIC Routing model."))
    print(green("Copying vic flux output files to the required folder"))
    createDirectory(VIC_ROUTING_FLUX_SOURCE)
    cmd = "cp " + VIC_FLUX_OUT_SUB_DIR +  "/* " + VIC_ROUTING_FLUX_SOURCE + "/"
    
    with hide('output','running'):
        local(cmd)
    
    print(green("Flux files have been copied."))
    print(green("Trimming flux files so as to remove the top header part."))
    with lcd(VIC_ROUTING_FLUX_SOURCE):
        with hide('output', 'running'):
            cmd = "sed -i 1,6d fluxes_*"
            local(cmd, capture=False)
    
    # now go to the input point folder and read all the locations for which we need to run the routing model 
    list_points = []
    with lcd(VIC_ROUTING_POINTS_INP_DIR):
        with hide('output', 'running'):
            cmd = "ls -d */"
            msg = local(cmd, capture=True)
            list_points = msg.split("\n")

    #For all the points create their respective output directory
    for point in list_points:
        createDirectory(VIC_ROUTING_POINTS_OUT_DIR+"/"+point)
        
        #For all the points check if their unit hydrograph file exists or not.
        #If exists then in the stnloc file provide the path to that hydrograph file
        #Otherwise put NONE
        UH_FILE_PATH = VIC_ROUTING_POINTS_INP_DIR + "/" + point + "*.uh_s"
        STN_FILE_PATH = VIC_ROUTING_POINTS_INP_DIR + "/" + point + "*.stnloc"
        print str(point) + " : " + str(file_exists(UH_FILE_PATH))
        cmd = ""
        if file_exists(UH_FILE_PATH):
            cmd = "ls " + UH_FILE_PATH
            msg = local(cmd, capture=True)
            UH_FILE = msg.split("/")[len(msg.split("/"))-1]
            UH_FILE_PATH = VIC_ROUTING_POINTS_INP_DIR + "/" + point + UH_FILE
            UH_FILE_PATH = UH_FILE_PATH.replace("/","\/")
            cmd = "sed -i '2s/.*/" + UH_FILE_PATH + " /' " + STN_FILE_PATH
        else:
            cmd = "sed -i '2s/.*/NONE /' " + STN_FILE_PATH
        
        try:
            local(cmd, capture=False)
        except:
            print(red("Error while updating " + point.split("/")[0] + " stnloc file."))
        
        #update the init file for each of the point
        #This update is required because we're interested in running routing file for a month only
        #so we need to put the start month and end month in the file respectively
        ROUT_INP_FILE_PATH = VIC_ROUTING_POINTS_INP_DIR + "/" + point + "rout_input.STEHE"
        date = VIC_FLUX_OUT_SUB_DIR.split("/")[len(VIC_FLUX_OUT_SUB_DIR.split("/"))-1]
        from_year = date[:4]
        from_month = date[4:6]
        from_day = date[6:]
        delta = 30
        if int(from_month) == 1 and int(from_day) > 5:
            delta = 28

        to_month_obj = datetime.date(year=int(from_year),day=int(from_day),month=int(from_month)) + timedelta(days=delta)
        to_month = str('%02d' %to_month_obj.month)
        to_year = to_month_obj.year
        time_range = str(from_year) + " " + str(from_month) + " " + str(to_year) + " " + str(to_month)
        print time_range
        cmd = "sed -i '24s/.*/" + time_range + " /' " + ROUT_INP_FILE_PATH
        cmd += " && "
        cmd += "sed -i '25s/.*/" + time_range + " /' " + ROUT_INP_FILE_PATH
        try:
            local(cmd, capture=False)
        except:
            print(red("Error while updating " + point.split("/")[0] + " rout_input.STEHE"))
        
        print(green("All necessary configuration files have been updated. Initiating VIC Routing Model."))
    
    run_routing(list_points)
    post_process_routing(list_points)

def run_routing(list_points):
    with hide('running', 'output'):
        for point in list_points:
            print(green("\nRunning Routing for point : " + point.split("/")[0]))
            with lcd(VIC_ROUTING_POINTS_INP_DIR + "/" + point):
                # ROUT_INP_FILE_PATH = VIC_ROUTING_POINTS_INP_DIR + "/" + point + "rout_input.STEHE"
                cmd = "rout rout_input.STEHE"
                local(cmd, capture=False)
                print(green("Completed."))

def post_process_routing(list_points):
    global date
    # date = "20180630"
    print(green("Creating consolidated report for all the reservoir points."))
    consolidated_file_path = VIC_ROUTING_POINTS_OUT_DIR + "/" + date + "_inflow_daily"
    if file_exists(consolidated_file_path):
        cmd = "rm " + consolidated_file_path
        local(cmd, capture=False)
    with hide('running', 'output'):
        for point in list_points:
            name = point.split("/")[0]
            flow_file = VIC_ROUTING_POINTS_OUT_DIR + "/" + name + "/" + "*.day"
            cmd = "ls " + flow_file
            try:
                msg = local(cmd, capture=True)
                flow_file = msg.split("/")[len(msg.split("/"))-1]
                file_path = VIC_ROUTING_POINTS_OUT_DIR + "/" + name + "/" + flow_file
                with open(file_path) as f:
                    #read the file content line by line
                    content = f.readlines()
                    #remove the trailing whitespaces
                    content = [x.strip() for x in content]
                    #iterate all the rows from number 6 till the end and search for the given date in the given file
                    for i in range(0,len(content)):
                        #split the data of each row
                        row_data = content[i].split("\t")
                        for row in row_data:
                            #for each row first remove unwanted spaces and then join the contents with ','
                            row = filter(None, row.split(" "))
                            row = ",".join(row)
                            cmd = "echo " + name.replace("_", " ") + "," + str(row) + " >> " + consolidated_file_path
                            local(cmd, capture=False)
            except:
                print(red("Error happened while reading " + name + " output file."))
        print(green("Consolidated report has been created successfully."))
    print(green("Transferring file to IWM FTP : "))
    #cmd = "lftp -c \"open " + OUT_FTP_ADDR + "; put -O " + OUT_FTP_DIR+ " '" + consolidated_file_path + "'\""
    cmd="scp -i " + PEM_FILE_PATH + " " + consolidated_file_path + " " + PLAY_MACHINE_ADDR + ":~/../iwmftp/kgbasin/"
    local(cmd, capture = True)
    print(green("File has been transferred successfully."))

def file_exists(file_path):
    with hide('output', 'running'):
        exists = local("if test -f " + file_path + "; then echo 'True'; else echo 'False'; fi", capture=True)
        if exists == 'False':
            return False
        return True

def run_model():
    print(green("\n\nStarting vic model for the given input data."))
    try:
        with lcd(HOME_DIR+CONF_FILE_DIR):
            with hide('output','running','warnings'):
                with settings(warn_only=True):
                    # cmd="vicNl -v"
                    cmd = "vicNl -g " + CONF_FILE_NAME
                    print(green("Command used : " + cmd))
                    msg = local(cmd, capture=True)
                    # print msg
                    print(green("vic model has been run on the given input data successfully.\n\n"))
                    return {"msg":"", "status":0}
    except Exception as e:
        return {"msg":"method : run_model : FATAL : exception occurred while running vic model on given input data. Exception : " + str(e), "status":1}


def transferFileToNRSC(fileToTransfer, targetFolder):
    print(green("Initiating file transfer to NRSC FTP"))
    print(green("Copying " + fileToTransfer + " to " + targetFolder))
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(NRSC_HOST, username=NRSC_USER, password=NRSC_PASS, cnopts=cnopts) as sftp:
        with sftp.cd(targetFolder):
            sftp.put(fileToTransfer)

        sftp.close()
    print(green("File transfer to NRSC FTP completed."))


def openFTP():
    with hide('output', 'running'):
        try:
            print(green("\nOpening FTP connection"))
            ftp = ftplib.FTP()
            ftp.debug(3)
            ftp.connect(IP, VIC_PORT)
            ftp.login(VIC_USER, VIC_PASS)
            return ftp
        except Exception, e:
            print e

    return None

def closeFTP(ftp):
    if ftp is not None:
        print(green("\nClosing FTP connection"))
        ftp.quit()

'''pass ftp object and the complete filepath where the file should be downloaded. The file will be downloaded from 
    ftp server from to the given location'''
def downloadFile(filepath):
    ftp = openFTP()
    if ftp is None:
        return

    filename = filepath.split("/")[len(filepath.split("/"))-1]
    ftp.cwd(FTP_INPUT_DIR)
    ftp.set_pasv(False)
    file = open(filepath, "w+b")
    ftp.retrbinary("RETR " + filename, file.write)
    closeFTP(ftp)

def uploadFile(ftp, filepath):
    ftp = openFTP()
    if ftp is None:
        return

    filename = filepath.split("/")[len(filepath.split("/"))-1]
    ftp.cwd(FTP_OUTPUT_DIR)
    ftp.set_pasv(False)
    file = open(filepath, "r+b")
    ftp.storbinary("STOR " + filename, file)
    closeFTP(ftp)

def getLatestMetFile():
    filelist = []
    ftp = openFTP()
    if ftp is None:
        return

    ftp.cwd(FTP_INPUT_DIR)
    ftp.set_pasv(False)
    ftp.retrlines('LIST', filelist.append)
    latest = filelist[len(filelist)-1]
    latest_fname = latest.split(" ")[len(latest.split(" "))-1]
    timestamp = ftp.sendcmd("MDTM " + latest_fname).split(" ")[1]
    closeFTP(ftp)
    return latest_fname + "##" + timestamp

def test():
    filelist = []
    ftp = openFTP()
    if ftp is None:
        return

    ftp.cwd(FTP_INPUT_DIR)
    ftp.set_pasv(False)
    ftp.retrlines('LIST', filelist.append)
    latest = filelist[len(filelist)-1]
    latest_fname = latest.split(" ")[len(latest.split(" "))-1]
    timestamp = ftp.sendcmd("MDTM " + latest_fname).split(" ")[1]
    closeFTP(ftp)
    return latest_fname + "##" + timestamp


                

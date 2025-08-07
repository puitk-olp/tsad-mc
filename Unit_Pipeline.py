#!/usr/local/bin/python

## Simple pipeline to run a unit experiment
# Unique experiment: one method, one datafile

import numpy as np
import pandas as pd
import math
import uuid
import warnings
from time import perf_counter
import time
import datetime
from pathlib import Path
import subprocess
import yaml
import sqlite3
import json
import argparse

from model.Method_Parameters import Univariate_Methods_Parameters
from model.alt_model_wrapper import Metrics
from model.alt_model_wrapper import run_Unsupervise_AD, run_Semisupervise_AD
from model.alt_model_wrapper import Unsupervised, Semisupervised

## Dataset related
DATASET_DIR         = '/mnt/FFL/datasets/TSB-AD-U'
DATASET_SUMMARY     = pd.read_csv('/mnt/FFL/code/fred/docker/Summary.csv',sep=';')

#DATASET_DIR     = 'D:/Project/Datasets/TSB-AD-U/TSB-AD-U'
#DATASET_SUMMARY = pd.read_csv('D:/Project/Datasets/TSB-AD-U/Summary.csv',sep=';')

## Methods related


## Metric related

Metrics = ['AUC-PR','AUC-ROC','VUS-PR','VUS-ROC','Standard-F1','PA-F1','Event-based-F1','R-based-F1','Affiliation-F']

## db records 
DB_RECORD = [('expe_id','TEXT PRIMARY KEY'),
             ('comment','TEXT'),
             ('db','TEXT'),
             ('start_expe','TEXT'),
             ('end_expe','TEXT'),
             ('docker_status', 'TEXT'),
             ('computer','TEXT'),
             ('cpu_limit','TEXT'),
             ('ram_limit','TEXT'),
             ('swap_limit','TEXT'),
             ('time_limit','TEXT'),
             ('method','TEXT'),
             ('method_params','TEXT'),
             ('metrics','TEXT'),
             ('metrics_params','TEXT'),
             ('dataset','TEXT'),
             ('init_duration','REAL'),
             ('train_duration','REAL'),
             ('test_duration','REAL'),
             ('metrics_perf','TEXT'),
             ('score','TEXT'),
             ('expe_status','TEXT')]

def string_to_dict(the_string):
    json_acceptable_string = the_string.replace("'", "\"")
    return(json.loads(json_acceptable_string))
    



class Unit_Pipeline:
    """ A class to implement a simple experiment for one method and one dataset"""

    def __init__(self, 
                 config_file        = 'config.yaml',
                 method             = 'LOF', 
                 dataset            = '001_NAB_id_1_Facility_tr_1007_1st_2014',
                 datadir            = DATASET_DIR,
                 metrics            = 'all',
                 method_parameters  = {},
                 metrics_parameters = {},
                 docker_config      = {},
                 db                 = 'test_db.db',
                 who_am_i           = 'fred',
                 comment            = 'Test',
                 host               = 'Test_Host'
                 ):
        self._id                 = uuid.uuid4()
        self._config_file        = config_file 
        self._read_config() 
        
        self._dataset            = self._get_dataset()
        self._check_method_parameters()
        
        if self._method not in Unsupervised+Semisupervised:
            raise NotImplementedError("Method {} is not implemented".format(method))
        

        self._open_db()

    def _read_config(self):
        
        try:
            with open(self._config_file,"r") as file:
                self._config = yaml.safe_load(file)
        except:
            raise Exception("Impossible to read {} file".format(self._config_file))

        # Construct the configuration
        self._comment = self._config.get('comment','')
        self._runner  = self._config.get('user','unknown')
        self._host    = self._config.get('host','unknown')

        temp = self._config.get('db','')
        if temp == '':
            raise Exception("No database file provided in configuration file")
        
        self._db = temp.get('file','')
        if self._db == '':
            raise Exception("No database file provided in configutration file")
        self._db_name = temp.get('name','expe')


        self._docker_config = {}
        
        cpu_limit = self._config.get('docker_cpu_limit','')
        
        self._docker_config['cpu_limit'] = cpu_limit

        ram_limit = self._config.get('docker_ram_limit','')
        self._docker_config['ram_limit'] = ram_limit

        swap_limit = self._config.get('docker_swap_limit','')
        self._docker_config['swap_limit'] = swap_limit

        time_limit = self._config.get('docker_time_limit','')
        self._docker_config['time_limit'] = time_limit

        if self._config.get('method','') == '':
            raise Exception("Missing method in configuration file")

        temp = self._config.get('method','')
        
        self._method = temp['name']
        self._method_parameters = {}
        params = temp.get('parameters',{})
        for k in params.keys():
            self._method_parameters[k] = params[k]

        temp = self._config.get('dataset','')
        if temp == '':
            raise Exception("No dataset in configuration file")
        
        self._datadir = temp.get('dir',DATASET_DIR)
        self._dataset_name    = temp.get('data','001_NAB_id_1_Facility_tr_1007_1st_2014')
        
        self._metrics = 'all'
        self._metrics_parameters = {}

    def configuration(self):
        print("#############################################################################")
        print("{}: {}".format('id',self._id))
        print("{}: {}".format('method',self._method))
        print("{}: {}".format('method parameters',self._method_parameters))
        print("{}: {}".format('datadir',self._datadir))
        print("{}: {}".format('dataset name',self._dataset_name))
        print("{}: {}".format('dataset',self._dataset))
        print("{}: {}".format('metrics',self._metrics))
        print("{}: {}".format('metric parameters',self._metrics_parameters))
        print("{}: {}".format('docker_config',self._docker_config))
        print("{}: {}".format('db',self._db))
        print("{}: {}".format('db_name',self._db_name))
        print("#############################################################################")
    
    def _open_db(self):
        try:
            self._connection = sqlite3.connect(self._db)
            self._cursor = self._connection.cursor()
            rows = ','.join(["{} {}".format(DB_RECORD[i][0],DB_RECORD[i][1]) for i in range(len(DB_RECORD))])
            request = "CREATE TABLE IF NOT EXISTS {} ({})".format(self._db_name,rows)
            self._cursor.execute(request)
            
        except:
            raise Exception("db as not been created")
            

    def _check_method_parameters(self):
        for k in self._method_parameters:
            if k not in Univariate_Methods_Parameters[self._method]['expe']['opt'].keys():
                raise ValueError("Parameter {} is not among experience parameters  for method {}".format(k,self._method))

    def _check_metrics(self):
        if self._metrics == 'all':
            pass
        else:
            raise NotImplementedError("Using individual metrics is not yet implemented")
        
    def _check_metrics__parameters(self):
        if self._metrics_parameters is not None:
            raise NotImplementedError("Using individual metrics is not yet implemented")
        
    def _get_dataset(self):
        return(pd.read_csv("{}/{}.csv".format(self._datadir,self._dataset_name),sep=","))
    
    def dataset_info(self):
        return(DATASET_SUMMARY[DATASET_SUMMARY['name']==self._dataset_name][['name','dataset','size','train_index','anomalous','events','anomaly_rate','first']].iloc[0])
    
    def _make_command(self):
        command = ['python']
        command.append('/mnt/FFL/code/fred/docker/run_unit_method.py')
        command.append('--config')
        command.append(self._config_file)
        
        return(command)

    def _save_results(self,result):

        try:
            columns = "({})".format(','.join(DB_RECORD[i][0] for i in range(len(DB_RECORD))))
        

            row =[
                        str(self._id),
                        self._comment,
                        self._db,
                        self._start_time,
                        self._end_time,
                        self._computer_status,
                        self._host,
                        self._docker_config.get('cpu_limit',''),
                        self._docker_config.get('ram_limit',''),
                        self._docker_config.get('swap_limit',''),
                        self._docker_config.get('time_limit',''),
                        self._method,
                        json.dumps(self._method_parameters),
                        self._metrics,
                        json.dumps(self._metrics_parameters),
                        self._dataset_name,
                        str(result['init']),
                        str(result['training']),
                        str(result['test']),
                        json.dumps(result['performance']),
                        json.dumps(result['score']),
                        result['status']
                        ]
            values = '('+','.join(['?' for i in range(len(DB_RECORD))])+')'
            request = "INSERT INTO {} {} VALUES {}".format(self._db_name,columns,values)

            self._cursor.execute(request,row)
            self._connection.commit()

        except:
            raise Exception("Impossible to save the results in database")


    def run(self):
        command = self._make_command()
         
        try:
            st = time.time()
            self._start_time = datetime.datetime.fromtimestamp(st).strftime('%Y-%m-%d %H:%M:%S')
            result = subprocess.run(command, capture_output=True, text=True)
            et = time.time()
            self._end_time =  datetime.datetime.fromtimestamp(et).strftime('%Y-%m-%d %H:%M:%S')
            self._computer_status = 'success'
        except:
            result = "Subprocess Failed"
            self._computer_status = 'failed'
        
        if self._computer_status == 'success':
            with open('/mnt/FFL/code/fred/docker/trash/Temp_Out.json', 'r') as file:
                result = json.load(file)

            self._save_results(result)
        return(result)
        
if __name__ == '__main__':
    
    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    parser.add_argument('--config',type=str,default=None)
    args = parser.parse_args()

    T = Unit_Pipeline(config_file=args.config)
    warnings.filterwarnings("ignore")
    #T.configuration()
    result = T.run()  


    connection = sqlite3.connect(T._db)
    cursor = connection.cursor()  
    cursor.execute("SELECT * FROM expe")
    rows = cursor.fetchall()
    
    #count = 1
    records = [l for l in rows]
    count = len(records)
    print("\n ---------- start record {}----------- \n".format(count))
    print("{}".format(records[-1]))
    print("\n ---------- end record {}------------- \n".format(count))

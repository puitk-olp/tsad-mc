#!/usr/bin/python3 
import os
from pathlib import Path
import yaml
import json
import warnings
import sqlite3
import argparse

def get_features(list,suppressed_elements):
    index = [i for i in range(len(list))]
    for k in suppressed_elements:
        if not k in list:
            raise Exception(f"Feature '{k}' not found in {list}")
    suppressed = [list.index(k) for k in suppressed_elements]
    return([(list[k],k) for k in index if k not in suppressed])

def list_tables(db):
    if not os.path.isfile(db):
        raise Exception(f"db file {db} not found")
    con = sqlite3.connect(db)
    cursor = con.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for k in tables:
        print(k)

def list_table_columns(db,expe):
    try:
        connection = sqlite3.connect(db)
        columns = [fields[1] for fields in connection.execute(f"PRAGMA table_info({args.expe})").fetchall()]
    except Exception as err:
        print(f"Exception in reading {db}:{expe}: ({str(err)}) ")
    finally:
        connection.close()
    return(columns)

def dump_table(db,expe,features):
    try:
        connection = sqlite3.connect(db)
        cursor = connection.cursor()
        request = f"select * from {expe}"
        cursor.execute(request)
        rows = cursor.fetchall()
        for k in range(len(rows)):
            print(f"------------------- record {k} -------------------")
            
            print([rows[k][features[i][1]] for i in range(len(features))])
    except Exception as err:
        print(f"Exception in reading {db}:{expe}: ({str(err)}) ")
    finally:
        connection.close()

if __name__ == '__main__':
    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    parser.add_argument('--db',type=str,default=None)
    parser.add_argument('--expe',type=str,default=None)
    parser.add_argument('--list_col',action='store_true')
    parser.add_argument('-s','--suppress', nargs='+', help='<Required> Set flag', required=False, default=[])
    args = parser.parse_args()

    if args.db is None:
        raise Exception(f"Missing db filename")
    elif (args.db is not None) and (args.expe is None):
        list_tables(args.db)
    elif (args.db is not None) and (args.expe is not None):
        if args.list_col: 
            print(list_table_columns(args.db,args.expe))
        else:
            features = list_table_columns(args.db,args.expe)
            print(f"suppressed: {args.suppress}")
            features = get_features(features,args.suppress)
            dump_table(args.db,args.expe,features)
            
        
    else:
        print("Nothing to do")

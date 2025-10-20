import os
import sys
import time
import json
import sqlite3
import local_utils.defaults as defaults

## db records 
DB_RECORD = [
    ('expe_id','TEXT PRIMARY KEY'),
    ('expe_start','TEXT'),
    ('expe_end','TEXT'),
    ('runner_type','TEXT'),
    ('hostname','TEXT'),
    ('user','TEXT'),
    ('comment','TEXT'),
    ('db_file','TEXT'),
    ('db_name','TEXT'),
    ('process_status', 'TEXT'),
    ('cpu_limit','TEXT'),
    ('ram_limit','TEXT'),
    ('swap_limit','TEXT'),
    ('timeout','REAL'),
    ('expe_status','TEXT'),
    ('expe_fail_reason','TEXT'),
    ('method','TEXT'),
    ('method_params','TEXT'),
    ('metrics','TEXT'),
    # ('metrics_params','TEXT'),
    ('dataset','TEXT'),
    ('dataset_file_size','INTEGER'),
    ('dataset_memory_size','INTEGER'),
    ('no_train_points','INTEGER'),
    ('no_test_points','INTEGER'),
    ('init_duration','REAL'),
    ('train_duration','REAL'),
    ('test_duration','REAL'),
    ('metrics_perf','TEXT'),
    ('score','TEXT')
]

# def string_to_dict(the_string):
#     json_acceptable_string = the_string.replace("'", "\"")
#     return(json.loads(json_acceptable_string))


class SqliteWrapper:
    def __init__(self, config: dict, logger = None):
        self._db_config = config
        self._logger = logger
        self._db = None

        self._check_config()
        # self._open_db()

    def _check_config(self):
        self._db_config.setdefault("file", defaults.DB_FILE)
        self._db_config.setdefault("name", defaults.DB_NAME)
        if self._logger is not None:
            self._logger.debug(f"using sqlite3 db: file={self._db_config['file']}, name={self._db_config['name']}")

    def _open_db(self):
        try:
            if self._db is None or len(self._db)==0:
                os.makedirs(os.path.dirname(self._db_config["file"]), exist_ok=True)
                self._db = {}
                self._db["connection"] = sqlite3.connect(self._db_config["file"])
                self._db["cursor"] = self._db["connection"].cursor()
        except Exception as e:
            # raise Exception("db has not been created")
            if self._logger is not None:
                self._logger.warning(f"Error while opening database: {repr(e)}")
            self._db = None

    def _create_table(self, table_name : str = None):
        try:
            # create table if requested
            rows = ','.join(["{} {}".format(DB_RECORD[i][0],DB_RECORD[i][1]) for i in range(len(DB_RECORD))])
            if table_name is None:
                table_name = self._db_config["name"]
            request = f"CREATE TABLE IF NOT EXISTS {table_name} ({rows})"
            self._db["cursor"].execute(request)
        except Exception as e:
            # raise Exception("db has not been created")
            if self._logger is not None:
                self._logger.warning(f"Error while creating db table: {repr(e)}")

    def save_results(self, run_id: str,  config: dict, status: dict, results: dict, table_name : str = None):
        # config - input config to the runner
        # status - data come from runner
        # results - data come from unit-test
        if table_name is None:
            table_name = self._db_config["name"]
        self._open_db()
        self._create_table(table_name)

        try:
            columns = "({})".format(','.join(DB_RECORD[i][0] for i in range(len(DB_RECORD))))
            globals = config.get("globals", {})
            runner = config.get("runner",{})
            limits = runner.get("limits", {})

            row = [
                str(run_id),
                time.strftime(defaults.TIME_FORMAT,time.localtime(status.get("st"))),
                time.strftime(defaults.TIME_FORMAT,time.localtime(status.get("et"))),
                runner.get("type", ""),
                globals.get("hostname"),
                globals.get("user"),
                globals.get("comment"),
                self._db_config.get("file"),
                self._db_config.get("name"),
                status.get("StatusCode"),
                limits.get('cpu',''),
                limits.get('memory',''),
                limits.get('swap',''),
                config["runner"].get('timeout',0),
                results.get('expe_status', "failed"),
                status.get('expe_fail_reason', results.get('expe_fail_reason','')),
                config["method"]["name"],
                json.dumps(config["method"].get("parameters",{})),
                json.dumps(config["metrics"]),
                # json.dumps(self._config["metrics"].get("parameters",{})),
                config["dataset"]["name"],
                results.get('dataset_file_size', -1),
                results.get('dataset_memory_size', -1),
                results.get('no_train_points', 0),
                results.get('no_test_points', 0),
                str(results.get('init', float('NaN'))),
                str(results.get('train', float('NaN'))),
                str(results.get('test', float('NaN'))),
                json.dumps(results.get('perf', {})),
                json.dumps(results.get('score', []))
            ]
            values = '('+','.join(['?' for i in range(len(DB_RECORD))])+')'
            request = f"INSERT INTO {table_name} {columns} VALUES {values}"

            self._db["cursor"].execute(request,row)
            self._db["connection"].commit()

        except Exception as e:
            raise Exception(f"Error while saving results in database: {repr(e)}")
    
    def _get_tables(self):
        self._open_db()
        tables = [ t[0] for t in self._db["cursor"].execute("SELECT name FROM sqlite_master WHERE type='table';") ]
        return tables
    
    def _get_table_columns(self, table_name : str = None):
        if table_name is None:
            table_name = self._db_config["name"]

        try:
            self._open_db()
            self._db["cursor"].execute(f"PRAGMA table_info({table_name})")
            columns = [ f[1] for f in self._db["cursor"].fetchall() ]
        except Exception as e:
            print(f"Exception in reading '{table_name}': ({str(e)}) ")

        return columns
    
    def get_results(self, columns : list = None, table_name : str = None, where_clause : dict = None):
        results = []
        if table_name is None:
            table_name = self._db_config["name"]
        
        try:
            self._open_db()
            table_columns = self._get_table_columns(table_name)
            if type(columns) == list:
                columns = [ i for i in columns if i in table_columns ]
            else:
                columns = table_columns

            select_str = f"SELECT {','.join(columns)} FROM {table_name}"
            if type(where_clause) == dict and len(where_clause) > 0:
                where_str = " WHERE "
                for i, k in enumerate(where_clause.keys()):
                    if i != 0:
                        where_str += " AND "
                    where_str += f"{k}='{where_clause[k]}'"
                select_str += where_str

            print(select_str)
            self._db["cursor"].execute(select_str)
            rows = self._db["cursor"].fetchall()
            for r in rows:
                rec = {}
                for i, v in enumerate(r):
                    rec[columns[i]] = v
                results.append(rec)
        except Exception as e:
            print(f"Error while retiving results: {repr(e)}")

        return results

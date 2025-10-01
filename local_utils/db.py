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
        self._open_db()

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
                rows = ','.join(["{} {}".format(DB_RECORD[i][0],DB_RECORD[i][1]) for i in range(len(DB_RECORD))])
                request = "CREATE TABLE IF NOT EXISTS {} ({})".format(self._db_config["name"],rows)
                self._db["cursor"].execute(request)
        except:
            # raise Exception("db has not been created")
            if self._logger is not None:
                self._logger.warning("Error while opening database: results will not be stored in DB !!!")
            self._db = None

    def save_results(self, config: dict, status: dict, results: dict):
        # config - input config to the runner
        # status - data come from runner
        # results - data come from unit-test
        self._open_db()

        try:
            columns = "({})".format(','.join(DB_RECORD[i][0] for i in range(len(DB_RECORD))))
            globals = config.get("globals", {})
            runner = config.get("runner",{})
            limits = runner.get("limits", {})

            row = [
                str(config["unit_test"].get("id")),
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
            request = "INSERT INTO {} {} VALUES {}".format(self._db_config["name"],columns,values)

            self._db["cursor"].execute(request,row)
            self._db["connection"].commit()

        except:
            raise Exception("Impossible to save the results in database")
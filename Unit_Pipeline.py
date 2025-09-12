#!/usr/local/bin/python

## Simple pipeline to run a unit experiment
# Unique experiment: one method, one datafile

import sys
import signal

import pandas as pd

import uuid

import logging
import logging.config
import warnings
import time

import argparse
import traceback

from TSB_AD.evaluation.metrics import get_metrics
from model.alt_model_wrapper import Metrics
from model.alt_model_wrapper import run_Unsupervise_AD, run_Semisupervise_AD
from model.alt_model_wrapper import Unsupervised, Semisupervised
from model.Method_Parameters import Univariate_Methods_Parameters

from sklearn.preprocessing import MinMaxScaler

import defaults
from local_utils.config import read_file, write_file

logger = logging.getLogger("unit_pipeline")

class Unit_Pipeline:
    """ A class to implement a simple experiment for one method and one dataset"""

    def __init__(
            self, 
            config: dict        = None, 
        ):
        self._config: dict      = config

        # series of checks
        self.check_unit_config()


    def check_unit_config(self):
        # check if all sections are properly configured, and if not correct them if 
        unit_config = self._config.setdefault("unit_config", {})
        unit_config.setdefault("id", str(uuid.uuid4()))
        unit_config.setdefault("result_file", f"{defaults.RESULT_DIR}/{unit_config['id']}.yaml")
        unit_config.setdefault("save_config", False)

        self._check_dataset_config()
        self._check_method_config()
        self._check_metrics_config()  
        
    def _check_dataset_config(self):
            if self._config.get('dataset', None) is None:
                logger.warn("missing dataset config. using default one.")
                self._config["dataset"] = {}
            
            self._config["dataset"].setdefault('dir', defaults.DATASET_DIR)
            self._config["dataset"].setdefault('name', defaults.DATASET_NAME)

    def _check_method_config(self):
        method = self._config.setdefault("method",{})
        if method.get("name",None) not in Unsupervised + Semisupervised:
            raise NotImplementedError(f"Method {method.get("name")} is not implemented")
        
        if method.get("parameters", None):
            for k in method["parameters"]:
                if k not in Univariate_Methods_Parameters[method["name"]]['expe']['opt'].keys():
                    raise ValueError(f"Parameter {k} is not among experience parameters for method {method["name"]}")

    def _check_metrics_config(self):
        metrics = self._config.setdefault("metrics",defaults.METRICS_NAME)
        if metrics == "all":
            self._config["metrics"] = Metrics
        elif type(metrics)==str:
            self._config["metrics"] = [ metrics ]
        elif type(metrics)!=list:
            raise ValueError("Unknown definition of metrics")
        for m in self._config["metrics"]:
            if m not in Metrics:
                raise NotImplementedError("Unknown metric")
        # metrics params, even if set, will be ignored
        # if not self._config["metrics"].get("parameters", None):
        #     raise NotImplementedError("Using individual metrics is not yet implemented")
    
    def _get_dataset(self):
        df = pd.read_csv(f"{self._config["dataset"]["dir"]}/{self._config["dataset"]["name"]}.csv",sep=",")
        data = df.iloc[:, 0:-1].values.astype(float)
        labels = df['Label'].astype(int).to_numpy()
        train_index = int(self._config["dataset"]["name"].split("_")[6])

        return (data, labels, train_index)
    
    def save_results(self, results):
        # save results to result file
        results_to_save = {
            "unit_test": { "id": self._config["unit_test"]["id"] },
            "results": results
        }
        if self._config["unit_test"]["save_config"]:
            for k in [ "method", "dataset", "metrics" ]:
                results_to_save[k] = self._config[k]
        write_file(results_to_save, self._config["unit_test"]["result_file"])


    def run(self):
        try:
            # i throw away subprocess and call methods directly
            # result = subprocess.run(command, capture_output=True, text=True)
            method = self._config["method"]
            data, labels, train_index = self._get_dataset()
            
            if method["name"] in Unsupervised:
                result = run_Unsupervise_AD(method["name"], data, **method.get("parameters",{}))
            else:
                train_data = data[0:train_index]
                test_data  = data[train_index:-1]
                labels = labels[train_index:-1]
                result = run_Semisupervise_AD(method, train_data, test_data, **method.get("parameters",{}))
        
            score = MinMaxScaler(feature_range=(0,1)).fit_transform(result['score'].reshape(-1,1)).ravel()

            # get all metrics and filter them to store only those required
            perf = get_metrics(result['score'], labels)
            result["perf"] = {m:perf[m] for m in self._config["metrics"]}
            result["score"] = score.tolist()

        except Exception as e:
            # logger.warning(traceback.format_exc())
            logger.warning("exception during main function exec")
            result = {
                    "expe_status": "failed",
                    "expe_fail_reason": str(e),
                    "score": [],
                    "init": float('NaN'),
                    "train": float('NaN'),
                    "test": float('NaN'),
                    "perf": {}
                }

        return result

def alarm_handler(signum, frame):
    logger.warning(f"received signal: {signum}")
    raise TimeoutError(f"Process timeout expired (signal={signum})")


if __name__ == '__main__':
    warnings.filterwarnings("ignore")

    old_alarm_handler = signal.signal(signal.SIGALRM, alarm_handler)

    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    parser.add_argument('-c','--config-file', type=str, default=f"{defaults.TEMP_CONFIG_FILE}")
    parser.add_argument('-l','--log-config-file', type=str, default=f"{defaults.LOG_CONFIG_FILE}")
    args = parser.parse_args()

    try:
        log_config = read_file(input_file=args.log_config_file)
        logging.config.dictConfig(log_config)
        logger.debug(f"----------------------------------------------")
        logger.debug(f"reading logging config: {args.log_config_file}")
    except Exception as e:
        logger.warning(f"could not process log config file: {repr(e)}")
    
    try:
        logger.debug(f"reading configuration file: {args.config_file}")
        config = read_file(input_file=args.config_file)
    except:
        logger.critical(f"could not process main config file")
        sys.exit(1)
    try:
        logger.info(f"initialization of Unit_Pipeline")
        T = Unit_Pipeline(config=config)
        logger.info(f"running main pipeline function")
        results = T.run()

        # save results
        logger.info(f"saving results")
        T.save_results(results)
    except Exception as e:
        logger.error(repr(e))

    logger.debug("process end")

    signal.signal(signal.SIGALRM, old_alarm_handler)


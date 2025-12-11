import os
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

import argparse
import warnings
import logging
import logging.config
import re
import yaml
import json
import numpy as np
import pandas as pd
import local_utils.defaults as defaults
from local_utils.config import read_file, check_metrics_config
from local_utils.db import SqliteWrapper
from model.alt_model_wrapper import Metrics, Unsupervised, Semisupervised
from local_utils.metrics import get_metrics


logger = logging.getLogger("metrics")

def examine_result_config(result_config: dict = None):
    # result file list
    result_files = result_config.get("files", [])
    # results from dir
    result_dir = result_config.get("dir", {})
    if "path" in result_dir and os.path.isdir(result_dir.get("path")):
        # we have dir to search for results
        re_filter = result_dir.get("re", "[^/]*\.db")
        for e in os.listdir(result_dir.get("path")):
            f = f"{result_dir.get('path')}/{e}"
            if re.match(re_filter, e) and os.path.isfile( f ):
                rf = {'file':f,'name':result_dir.get("table", defaults.DB_NAME)}
                try:
                    result_files.index(rf)
                except ValueError:
                    result_files.append(rf)
    return result_files

# def get_dataset_labels(dataset_name : str, dataset_dir : str = defaults.DATASET_DIR):
def get_dataset_labels(dataset_name : str, dataset_dir : str):
    ds_file_name = f'{dataset_dir}/{dataset_name}.csv'
    logger.debug(f"loading dataset from: {ds_file_name}")
    df = pd.read_csv(ds_file_name, sep=',')
    labels = df['Label'].astype(int).to_numpy()
    train_index = int(dataset_name.split("_")[6])
    return (labels, train_index)

DATASET_LABELS = {}

if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Calculating metrics of TSB-AD test serie')
    conf_env = f"({os.environ.get('CONFIG_FILE')}) " if os.environ.get("CONFIG_FILE", None) is not None else ""
    parser.add_argument(
        '-c',
        '--config-file',
        help=f"Path to 'config-file'. If ommited, CONFIG_FILE env var {conf_env}is used, then default value ({defaults.CONFIG_FILE})",
        type=str,
        default=os.environ.get("CONFIG_FILE", defaults.CONFIG_FILE)
    )
    parser.add_argument('-l','--log-config-file', type=str, default=f"{SCRIPT_DIR}/{defaults.LOG_CONFIG_FILE}")
    args = parser.parse_args()

    try:
        log_config = read_file(input_file=args.log_config_file)
        logging.config.dictConfig(log_config)
        logger.debug(f"----------------------------------------------")
        logger.debug(f"reading logging config: {args.log_config_file}")
    except Exception as e:
        logger.warning(f"could not process log config file: {repr(e)}")

    # read config and run main function
    config = read_file(input_file=args.config_file)
    config['metrics'] = check_metrics_config(config.get("metrics", None), metrics_allowed=Metrics)
    config['results'] = examine_result_config(config.get("results", {}))
    # dataset config
    config.setdefault('dataset', {})
    # config['dataset'].setdefault('dir',defaults.DATASET_DIR)
    # processes config
    logger.debug(f"Processed config ({len(config.get('results'))}):\n{yaml.dump(config)}")

    no_res_item = len(config.get("results",[]))

    serie_calc_status = {
        'result_files_processed': 0,
        'unit_tests_processed': 0,
        'unit_tests_failed': 0
    }

    try:
        for r_idx, res_item in enumerate(config.get("results",[])):
            logger.debug(f"##############################################")
            logger.info(f"Processing ({r_idx+1}/{no_res_item}): {res_item.get('file')}({res_item.get('name')})")
            r_wrapper = SqliteWrapper(res_item, logger)
            unprocessed_results = r_wrapper.get_results(['expe_id','dataset'], where_clause={"metrics":'"none"',"expe_status": "success"})
            no_ur = len(unprocessed_results)
            logger.info(f"Found {no_ur} unprocessed unit tests")

            # we process only when unprocessed results found
            if no_ur > 0:
                dataset_names = { f['dataset'] for f in unprocessed_results }
                logger.debug(f"Found following datasets: {dataset_names}")
                for ds in dataset_names:
                    if ds not in DATASET_LABELS:
                        DATASET_LABELS[ds] = get_dataset_labels(ds, config["dataset"].get('dir'))
                # iterate through all selected unit tests
                for u_idx, ur in enumerate(unprocessed_results):
                    try:
                        logger.debug(f"----------------------------------------------")
                        logger.info(f"Calculating metrics {u_idx+1}/{no_ur} from file {r_idx+1}/{no_res_item}")
                        # should be only 1
                        result = r_wrapper.get_results(["expe_id", "dataset", "method", "score"], where_clause={"expe_id": ur.get('expe_id')})[0]
                        logger.debug(f"Expe ID: {result.get('expe_id')}, Method: {result.get('method')}, Dataset: {result.get('dataset')}")
                        result['score'] = np.array(json.loads(result["score"]))
                        # reteive labels
                        labels, train_idx = DATASET_LABELS[result.get("dataset")]
                        if result.get("method") in Semisupervised:
                            labels = labels[train_idx:-1]
                        # calculate metrics
                        metrics_perf = get_metrics(result['score'], labels, config.get("metrics"))
                        # stroe results
                        r_update = {
                            "expe_id": ur.get('expe_id'),
                            "metrics": str(config.get('metrics')),
                            "metrics_perf": str(metrics_perf)
                        }
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Results to be updated: {r_update}")
                        r_wrapper.update_result(r_update, commit=True)
                        logger.info(f"Results have been updated")
                        serie_calc_status["unit_tests_processed"] += 1
                    except KeyboardInterrupt as err:
                        # user's interrupt by keyboard: clean up and (re)raise exception
                        r_wrapper.close()
                        raise err
                    except Exception as err:
                        logger.warning(f"Processing unit test failed: {repr(err)}")
                        serie_calc_status["unit_tests_failed"] += 1
                # cleanup: close wrapper and report status
                r_wrapper.close()
                serie_calc_status["result_files_processed"] += 1
                    
    except KeyboardInterrupt as err:
        logger.info(f"User interrupted process: {repr(err)}")
    finally:
        logger.debug(f"##############################################")
        logger.info(f"Serie calculation status: {serie_calc_status}")            



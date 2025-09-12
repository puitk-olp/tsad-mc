import os
import sys
import warnings
import logging
import logging.config
import defaults
import argparse
import requests
from local_utils.config import read_file, write_file, examine_multi_config, check_globals
from local_utils.db import SqliteWrapper

import uuid
import time
import yaml
import docker

logger = logging.getLogger("runner")

def get_runner(runner_config: dict):
    rtype = runner_config.get("type", defaults.RUNNER_TYPE)

    if rtype == "docker":
        return DockerRunner(runner_config)

    raise NotImplementedError("unknown runner type.")

class DockerRunner:
    def __init__(self, runner_config: dict = None):
        self._client = docker.from_env()
        self._params = runner_config.get("params",{})
        self._limits = runner_config.get("limits", {})
        self._timeout = float(runner_config.get("timeout", 0))

        # try to get container
        self._container = None
        container_id_name = self._params.get("name", None)
        if container_id_name is not None:
            try:
                self._container = self._client.containers.get(container_id_name)
                logger.debug(f"### reusing container: {self._container.name} ({self._container.short_id})")
            except docker.error.NotFound:
                logger.info(f"### no container ({container_id_name}) found")
            except docker.errors.APIError:
                logger.error(f"### docker API error")

        if self._container is None:
            # no container, create one
            run_args = {
                "detach": True,
                "volumes": {
                    defaults.BASE_DIR: {
                        "bind": defaults.BASE_DIR,
                        "mode": "rw"
                    } 
                },
                "working_dir": defaults.WORKING_DIR
            }
            self._params.setdefault("image", defaults.DOCKER_IMAGE)
            self._params.setdefault("command",defaults.CMD)
            if "name" in self._params:
                del self._params["name"]
            run_args.update(self._params)

            # create container
            self._container = self._client.containers.create(
                **run_args
            )
            print(f"### new container created: {self._container.name} ({self._container.short_id})")

        # apply limits (it should be defined as python docker API)
        logger.debug(f"### setting up container limits: {self._limits}")
        self._container.update(**self._limits)
        self._params["name"]=self._container.short_id

    def run(self):
        # wait for the container to end (or timeout)
        try:
            self._container.start()
            wait_args = {}
            if self._timeout > 0:
                wait_args["timeout"] = self._timeout
            status = self._container.wait(**wait_args)
        # except requests.exceptions.ReadTimeout:
        # except TimeoutError:
        # it does not follow "docker" package docs (ReadTimeout)
        except requests.exceptions.ConnectionError:
            logger.warning("### runtime timeout for the container exceeded: sending SIGALRM")
            self._container.kill("SIGALRM")
            logger.info("### waiting for the container to stop")
            status = self._container.wait()
        # dict: it should contain at least {'StatusCode': int }
        return status

def get_unit_test(incl_config: bool = False):
    run_id = str(uuid.uuid4())        
    unit_test = {
        "id": run_id,
        "result_file": f"{defaults.RESULT_DIR}/{run_id}.json",
        "save_config": incl_config
    }
    return unit_test

def run(config: dict, save: bool = True):

    logger.info(f"## generating unit_config")
    config["unit_test"] = get_unit_test()
    logger.debug(f"{yaml.dump(config)}")

    logger.debug(f"## saving unit_config file for runner: {defaults.TEMP_CONFIG_FILE}")
    unit_config = { k: config[k] for k in [ "unit_test", "dataset", "method", "metrics" ] }
    write_file(unit_config, defaults.TEMP_CONFIG_FILE)

    # prepare unit_test
    st = time.time()

    try:
        logger.info(f"## configuring runner")
        R = get_runner(runner_config=config.get("runner",{}))
        logger.info(f"## performing run: {config['unit_test'].get('id')}")
        status = R.run()
        logger.info(f"## run ended")
    except docker.errors.APIError as e:
        logger.error(f"## docker API error: {str(e)}")
        status = { "StatusCode": 125, "expe_fail_reason": str(e) }

    et = time.time()

    # process result, e.g. save, hook
    status.setdefault("st", st)
    status.setdefault("et", et)
    
    if save:
        db = config["globals"].get("db")
        logger.debug(f"## saving results to sqlite db: {db.get('file')} ({db.get('name')})")
        results = read_file(config["unit_test"].get("result_file")).get("results") if status.get("StatusCode") == 0 else {}
        writer = SqliteWrapper(db)
        writer.save_results(config, status, results)

    # return stats higher
    status.setdefault("expe_status", results.get("expe_status", "failed"))
    status.setdefault("expe_fail_reason", results.get("expe_fail_reason", "unknown"))

    return status

if __name__ == '__main__':

    
    warnings.filterwarnings("ignore")

    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    conf_env = f"({os.environ.get('CONFIG_FILE')}) " if os.environ.get("CONFIG_FILE", None) is not None else ""
    parser.add_argument(
        '-c',
        '--config-file',
        help=f"Path to 'config-file'. If ommited, CONFIG_FILE env var {conf_env}is used, then default value ({defaults.CONFIG_FILE})",
        type=str,
        default=os.environ.get("CONFIG_FILE", defaults.CONFIG_FILE)
    )
    parser.add_argument('-l','--log-config-file', type=str, default=f"{defaults.LOG_CONFIG_FILE}")
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
    check_globals(config)

    multi_config = examine_multi_config(config)
    logger.info(f"# Detected {len(multi_config)} configs")
    # here we will have a loop of multiple tests
    for i, rolling_config in enumerate(multi_config):
        logger.debug(f"#################################################")
        logger.info(f"# Performing unit test {i+1}/{len(multi_config)}:")
        status = run(config=rolling_config)
        logger.info(f"# test status: {status}")

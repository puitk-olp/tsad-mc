import os
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
import sys

import warnings
import logging
import logging.config
import local_utils.defaults as defaults
import argparse
import requests
from local_utils.config import read_file, write_file, examine_multi_config, check_globals, hr2bytes, bytes2hr
from local_utils.db import SqliteWrapper
from local_utils.watcher import ResultWatchdog

import uuid
import time
import yaml
import docker
import psutil
import signal

logger = logging.getLogger("runner")

class Runner:
    EXIT_TIMEOUT = 5
    EXIT_SIGNAL = signal.SIGKILL

    def __init__(self, runner_config: dict = None, config_file: str = None):
        global SCRIPT_DIR

        self._params = runner_config.get("params",{})
        self._limits = runner_config.get("limits", {})
        self._timeout = float(runner_config.get("timeout", 0))
        self._params["command"] = defaults.get_unit_cmd(script_dir=SCRIPT_DIR, config_file=config_file)

    def _process_limits(self):
        limits : dict = {}
        for l,v in self._limits.items():
            if l not in self.LIMITS_MAP.keys():
                continue
            limits[self.LIMITS_MAP[l]] = v
        return limits

    def run(self, clean: bool = False):
        raise NotImplementedError("abstract method")
    def completed(self):
        raise NotImplementedError("abstract method")
    def get_logger(self):
        return logger


class DockerRunner(Runner):

    LIMITS_MAP = {
        "cpu": "cpus",
        "memory": "mem_limit",
        "swap": "memswap_limit",
    }

    def __init__(self, runner_config: dict = None, config_file: str = None):
        super().__init__(runner_config, config_file)

        self._client = docker.from_env()
        # try to get container
        self._container = None
        container_id_name = self._params.get("name", None)
        if container_id_name is not None:
            try:
                self._container = self._client.containers.get(container_id_name)
                logger.debug(f"reusing container: {self._container.name} ({self._container.short_id})")
            except docker.errors.NotFound:
                logger.info(f"no container ({container_id_name}) found")
            except docker.errors.APIError:
                logger.error(f"docker API error")

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
                "working_dir": defaults.WORKING_DIR,
                "auto_remove": True,        # as we want to use different commands (config_file) for every unit test
            }
            self._params.setdefault("image", defaults.DOCKER_IMAGE)

            if "name" in self._params:
                del self._params["name"]
            run_args.update(self._params)

            # apply limits (it should be defined as python docker API)
            logger.debug(f"limits from config: {self._limits}")
            processed_limits = self._process_limits()
            logger.debug(f"processed limits to be applied: {processed_limits}")
            run_args.update(processed_limits)
            self._run_args = run_args

            # # create container
            # self._container = self._client.containers.create(
            #     **run_args
            # )
            # logger.info(f"new container created: {self._container.name} ({self._container.short_id})")

        # apply limits (it should be defined as python docker API)
        # logger.debug(f"limits from config: {self._limits}")
        # processed_limits = self._process_limits()
        # logger.debug(f"processed limits to be applied: {processed_limits}")
        # self._container.update(**processed_limits)
        # self._params["name"] = self._container.short_id

    def _process_limits(self):
        limits = super()._process_limits()
        if limits.get("mem_limit") not in [ None, "None" ]:
            # memswap_limit isn't None, mem_limit should also be configured, so add them
            mem = hr2bytes(limits.get("mem_limit"))
            limits["memswap_limit"] = -1 if limits.get("memswap_limit") in [ None, "None" ] else bytes2hr(mem + hr2bytes(limits.get("memswap_limit")))
        return limits


    def run(self, clean: bool = False):
        # wait for the container to end (or timeout)
        try:
            logger.debug(f"running container: {self._run_args}")
            # self._container.start()
            self._container = self._client.containers.run(**self._run_args)
            wait_args = {}
            if self._timeout > 0:
                wait_args["timeout"] = self._timeout
            logger.debug("waiting for the container to terminate")
            status = self._container.wait(**wait_args)
            logger.debug(f"container terminated")
        # except requests.exceptions.ReadTimeout:
        # except TimeoutError:
        # it does not follow "docker" package docs (ReadTimeout)
        except requests.exceptions.ConnectionError:
            logger.warning("runtime timeout for the container exceeded: sending SIGALRM")
            self._container.kill("SIGALRM")
            logger.info("waiting for the container to terminate, after sending SIGALRM")
            status = self._container.wait()
            logger.debug(f"container terminated")
        # dict: it should contain at least {'StatusCode': int }
        if clean and not self._run_args.get('auto_remove', False):
            # final cleaning
            logger.info(f"removing container: {self._container.name}")
            # self._container.remove()

        return status
    
    def completed(self):
        logger.debug(f"calling runner due to worker job completion")
        if self._container is not None:
            # logger.debug("received info that worker completed its computation")
            try:
                self._container.wait(timeout=self.EXIT_TIMEOUT)
            except requests.exceptions.ConnectionError:
                logger.warning(f"container didn't exit in {self.EXIT_TIMEOUT} sec. sending {self.EXIT_SIGNAL} signal")
                self._container.kill(self.EXIT_SIGNAL)


class SystemdRunner(Runner):

    LIMITS_MAP = {
        "cpu": "CPUQuota",
        "memory": "MemoryMax",
        "swap": "MemorySwapMax",
    }

    def __init__(self, runner_config: dict = None, config_file: str = None):
        super().__init__(runner_config, config_file)

    def _process_limits(self):
        limits = super()._process_limits()
        for k in list(limits.keys()):
            if limits.get(k, None) in [ -1, None, "None" ]:
                del limits[k]
            elif type(limits[k])==str:
                limits[k] = limits[k].upper() 
        return limits

    def _prepare_cmd(self):
        limits = self._process_limits()
        cmd = [ "systemd-run", "--scope", "--user" ]
        for l in limits:
            cmd += [ "-p", f"{l}={limits[l]}" ]
        cmd += self._params.get("command")
        return cmd

    def run(self, clean: bool = False):
        try:
            logger.debug(f"preparing systemd-run command to be executed")
            exec_cmd = self._prepare_cmd()
            logger.debug(f"starting subprocess: {exec_cmd}")
            self._process = psutil.Popen(exec_cmd)
            wait_args = {}
            if self._timeout > 0:
                wait_args["timeout"] = self._timeout
            logger.debug(f"waiting for the subprocess to terminate: pid={self._process.pid}")
            status_code = self._process.wait(**wait_args)
            logger.debug(f"subprocess terminated: {int(status_code)}")
        except psutil.TimeoutExpired:
            logger.warning("runtime timeout for the subprocess exceeded: sending SIGALRM")
            self._process.send_signal(signal.SIGALRM)
            logger.info("waiting for the subprocess to terminate, after sending SIGALRM")
            status_code = self._process.wait()
            logger.debug(f"subprocess terminated: {int(status_code)}")
        # dict: it should contain at least {'StatusCode': int }
        status = {'StatusCode': int(status_code) }
        return status

    def completed(self):
        logger.debug(f"calling runner due to worker job completion")
        if self._process is not None:
            # logger.debug("received info that worker completed its computation")
            try:
                self._process.wait(timeout=self.EXIT_TIMEOUT)
            except psutil.TimeoutExpired:
                logger.warning(f"process didn't exit in {self.EXIT_TIMEOUT} sec. sending {self.EXIT_SIGNAL} signal")
                self._process.send_signal(self.EXIT_SIGNAL)


def get_runner(runner_config: dict, config_file: str = None) -> Runner:
    rtype = runner_config.get("type", defaults.RUNNER_TYPE)

    if rtype == "docker":
        return DockerRunner(runner_config, config_file)
    if rtype == "systemd":
        return SystemdRunner(runner_config, config_file)

    raise NotImplementedError("unknown runner type.")

def get_unit_test(temp_dir: str = defaults.TEMP_DIR, incl_config: bool = False):
    run_id = str(uuid.uuid4())        
    unit_test = {
        "id": run_id,
        "config_file": f"{temp_dir}/config_{run_id}.yaml",
        "result_file": f"{temp_dir}/result_{run_id}.pkl",
        "save_config": incl_config,
    }
    return unit_test


RUNNER = None

def run(config: dict, save: bool = True, clean: bool = False):

    global RUNNER

    # get unit test basic config
    temp_dir = config["globals"].get("temp_dir")
    logger.info(f"generating unit_config:")
    config["unit_test"] = get_unit_test(temp_dir=temp_dir)
    logger.debug(f"\n{yaml.dump(config)}")

    # write config necessary for unit test to temp config file
    unit_config = { k: config[k] for k in [ "unit_test", "dataset", "method", "metrics" ] }
    temp_config_file = config['unit_test'].get("config_file")
    logger.debug(f"saving unit_config (id={unit_config['unit_test'].get('id')}) file for runner: {temp_config_file}")
    write_file(unit_config, temp_config_file)

    # record start time of a run()
    st = time.time()

    try:
        # get appropriate runner depending on the config
        logger.info(f"configuring runner")
        RUNNER = get_runner(runner_config=config.get("runner",{}), config_file=temp_config_file)
        # get and start a watchdog for result file, in order to recognize moment for finished computation of Unit_Pipeline
        logger.debug(f"preparing and starting result file watchdog: {config['unit_test'].get('result_file')}")
        watchdog = ResultWatchdog(config['unit_test'].get('result_file'), RUNNER)
        watchdog.start()
        # perform run() with chosen runner
        logger.info(f"performing run: {config['unit_test'].get('id')}")
        status = RUNNER.run(clean=clean)
        RUNNER = None
        # release watchdog
        logger.debug(f"stopping watchdog")
        watchdog.stop()
        logger.info(f"run ended")
    except docker.errors.APIError as e:
        logger.error(f"docker API error: {str(e)}")
        status = { "StatusCode": 125, "expe_fail_reason": str(e) }

    # record end time of a run()
    et = time.time()

    # save start, end timestamps
    status.setdefault("st", st)
    status.setdefault("et", et)
    
    if save:
        db = config["globals"].get("db")
        logger.debug(f"saving results to sqlite db: {db.get('file')} ({db.get('name')})")
        try:
            results = {}        # we don't know if we'll succeed
            if os.path.isfile(config["unit_test"].get("result_file")):
                results = read_file(config["unit_test"].get("result_file")).get("results")
                
                logger.debug(f'removing temp config ({config["unit_test"].get("config_file")}) and result ({config["unit_test"].get("result_file")}) files.')
                os.remove(config["unit_test"].get("config_file"))
                os.remove(config["unit_test"].get("result_file"))
            # get dataset file size
            ds_file = f'{config["dataset"].get("dir")}/{config["dataset"].get("name")}.csv'
            results["dataset_file_size"] = os.path.getsize(ds_file)
        except:
            logger.warning(f"cannot process results file: {config['unit_test'].get('result_file')}")
            status.setdefault("expe_fail_reason", "cannot process result file")
        writer = SqliteWrapper(db, logger)
        writer.save_results(config, status, results)

    # return stats higher
    status.setdefault("expe_status", results.get("expe_status", "failed"))
    status.setdefault("expe_fail_reason", results.get("expe_fail_reason", "unknown"))

    return status


# probably unused anymore, while watchdog implemented
def signal_handler(signum, frame):
    global RUNNER
    logger.debug(f"received signal: {signum}")
    if signum == signal.SIGUSR1:
        # we agreed that SIGUSR1 means Unit_Pipeline completed computation, so we can try to kill it if necessary.
        logger.debug(f"RUNNER: {RUNNER is not None}")
        if RUNNER is not None:
            RUNNER.completed()


if __name__ == '__main__':
    # registering our own signal handler function
    # old_alarm_handler = signal.signal(signal.SIGCHLD, signal_handler)
    # old_sigusr1_handler = signal.signal(signal.SIGUSR1, signal_handler)

    # runner_id = str(uuid.uuid4())

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
    parser.add_argument('-l','--log-config-file', type=str, default=f"{SCRIPT_DIR}/{defaults.LOG_CONFIG_FILE}")
    # parser.add_argument('-p','--pid-file', type=str, default=f"{defaults.RUNNER_PID_FILE}")
    args = parser.parse_args()

    # write runner process PID to file
    # write_file(os.getpid(), args.pid_file)

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
    logger.info(f"Detected {len(multi_config)} configs")
    # here we will have a loop of multiple tests
    for i, rolling_config in enumerate(multi_config):
        logger.debug(f"#################################################")
        logger.info(f"performing unit test {i+1}/{len(multi_config)}:")
        # call run() - main mgmt function for unit_test run
        # if last call -> clean=True
        status = run(config=rolling_config, clean=((i+1)==len(multi_config)) )
        logger.info(f"unit test status: {status}")

    # resoring the original signal handlers
    # signal.signal(signal.SIGCHLD, old_alarm_handler)
    # signal.signal(signal.SIGUSR1, old_sigusr1_handler)

    # logger.debug(f"removing runner's pid file: {args.pid_file}")
    # os.remove(args.pid_file)
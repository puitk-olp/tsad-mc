import os
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
import sys

import warnings
import logging
import logging.config
import local_utils.defaults as defaults
import argparse
import requests
from local_utils.config import read_file, write_file, examine_multi_config, check_globals, check_run_mode, hr2bytes, bytes2hr
from local_utils.db import SqliteWrapper
from local_utils.watcher import ResultWatchdog
from local_utils.status import SerieStatus
from local_utils.cgroups import CGroupsMonitor

import uuid
import time
import yaml
import docker
import psutil
import signal
import threading
import pandas as pd

logger = logging.getLogger("runner")

class Runner:
    EXIT_TIMEOUT = 5
    EXIT_SIGNAL = signal.SIGKILL

    def __init__(self, runner_config: dict = None, config_file: str = None):
        global SCRIPT_DIR

        self._params = runner_config.get("params") if runner_config.get("params") else {}
        self._limits = runner_config.get("limits") if runner_config.get("limits") else {}
        self._timeout = float(runner_config.get("timeout", 0))
        self._monitoring = { "enabled": runner_config.get("monitor",False) }
        logger.debug(f"params: {self._params}, limits: {self._limits}")
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


        # create a new container
        if self._container is None:
            # check if docker image is configured and present
            if self._params.get("image") is None:
                raise ValueError(f"no docker image provided")
            try:
                _ = self._client.images.get(self._params.get("image"))
            except docker.errors.ImageNotFound as e:
                logger.error(f'docker image: {self._params.get("image")} not found')
                raise e
            except docker.errors.APIError as e:
                logger.error(f"docker API error")
                raise e

            # need to rethink volumes: host->container
            # SCRIPT_DIR -> /app (?)
            # dataset_dir -> dataset_dir
            dataset_dir = read_file(config_file).get("dataset",{}).get("dir")
            # no container, create one
            run_args = {
                "volumes": {
                    SCRIPT_DIR: {
                        "bind": SCRIPT_DIR,
                        "mode": "rw"
                    },
                    dataset_dir: {
                        "bind": dataset_dir,
                        "mode": "ro"
                    }
                },
                "working_dir": SCRIPT_DIR,
                "detach": True,
                "auto_remove": True,        # as we want to use different commands (config_file) for every unit test
            }
            # self._params.setdefault("image", defaults.DOCKER_IMAGE)

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

            if self._monitoring.get("enabled", False):
                top = self._container.top()
                pid_idx = top.get("Titles").index("PID")
                pid = top.get("Processes")[0][pid_idx]  # we get first process
                logger.debug(f"starting monitoring thread")
                self._monitoring["ctrl"] = CGroupsMonitor(pid)
                self._monitoring["ctrl"].start()

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
        finally:
            if self._monitoring.get("ctrl") is not None:
                logger.debug(f"waiting for monitoring thread to finish")
                self._monitoring.get("ctrl").stop()

        # dict: it should contain at least {'StatusCode': int }
        if clean and not self._run_args.get('auto_remove', False):
            # final cleaning
            logger.info(f"removing container: {self._container.name}")
            # self._container.remove()

        # rewrite monitor data
        if self._monitoring.get("ctrl") is not None:
            status["monitoring_data"] = self._monitoring.get("ctrl").get_values()

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

            # start monitoring thread if requested
            if self._monitoring.get("enabled", False):
                logger.debug(f"starting monitoring thread")
                # self._monitoring["alive"] = True
                # self._monitoring["thread"] = threading.Thread(target=self.monitor)
                # self._monitoring["thread"].start()
                self._monitoring["ctrl"] = CGroupsMonitor(self._process.pid)
                self._monitoring["ctrl"].start()
            
            wait_args = {}
            if self._timeout > 0:
                wait_args["timeout"] = self._timeout
            logger.debug(f"waiting for the subprocess to terminate: pid={self._process.pid}")
            status_code = self._process.wait(**wait_args)
            # we should take into consideration that "status_code" can be None (NoneType):
            # - PID is not a child of current process,
            # - PID does not exist (?)
            logger.debug(f"subprocess terminated: {status_code}")
        except psutil.TimeoutExpired:
            logger.warning("runtime timeout for the subprocess exceeded: sending SIGALRM")
            self._process.send_signal(signal.SIGALRM)
            logger.info("waiting for the subprocess to terminate, after sending SIGALRM")
            status_code = self._process.wait()
            logger.debug(f"subprocess terminated: {status_code}")
            # self._monitoring["alive"] = False
        finally:
            if self._monitoring.get("ctrl") is not None:
                logger.debug(f"waiting for monitoring thread to finish")
                self._monitoring.get("ctrl").stop()

        # dict: it should contain at least {'StatusCode': int }
        status = {'StatusCode': int(status_code) if status_code != None else None }
        # rewrite monitor data
        if self._monitoring.get("ctrl") is not None:
            status["monitoring_data"] = self._monitoring.get("ctrl").get_values()
        return status
    
    # def monitor(self):
    #     # feat_to_monitor = [ "rss", "uss", "pss", "swap" ]
    #     feat_to_monitor = [ "rss", "vms", "shared", "text", "lib", "data", "dirty", "uss", "pss", "swap"]
    #     data = { }
    #     try:
    #         while self._monitoring.get("alive", False):
    #             meminfo = self._process.memory_full_info()
    #             cpu_percent = self._process.cpu_percent(interval=None)
    #             logger.debug(f"{meminfo=}, {cpu_percent=}")
    #             for f in feat_to_monitor:
    #                 if hasattr(meminfo, f) and getattr(meminfo, f) > data.get(f,-1):
    #                     data[f] = getattr(meminfo, f)
    #             if cpu_percent > data.get("cpu",0):
    #                 data["cpu"] = cpu_percent
    #             time.sleep(1)
    #     except psutil.NoSuchProcess as e:
    #         logger.debug("no process to monitor - probably ended")
    #     for f in feat_to_monitor:
    #         if f in data:
    #             data[f] /= (1024 * 1024)
    #     self._monitoring["data"] = data

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
    unit_header = get_unit_test(temp_dir=temp_dir)

    # write config necessary for unit test to temp config file
    unit_config = { k: config[k] for k in [ "dataset", "method", "metrics" ] }
    unit_config["unit_test"] = unit_header
    logger.debug(f"\n{yaml.dump(unit_config)}")

    temp_config_file = unit_header.get("config_file")
    logger.debug(f"saving unit_config (id={unit_header.get('id')}) file for runner: {temp_config_file}")
    write_file(unit_config, temp_config_file)

    # record start time of a run()
    st = time.time()

    try:
        # get appropriate runner depending on the config
        logger.info(f"configuring runner")
        RUNNER = get_runner(runner_config=config.get("runner",{}), config_file=temp_config_file)
        # get and start a watchdog for result file, in order to recognize moment for finished computation of Unit_Pipeline
        logger.debug(f"preparing and starting result file watchdog: {unit_header.get('result_file')}")
        watchdog = ResultWatchdog(unit_header.get('result_file'), RUNNER)
        watchdog.start()
        # perform run() with chosen runner
        logger.info(f"performing run: {unit_header.get('id')}")
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
            if os.path.isfile(unit_header.get("result_file")):
                results = read_file(unit_header.get("result_file")).get("results")
            # get dataset file size
            ds_file = f'{unit_config["dataset"].get("dir")}/{unit_config["dataset"].get("name")}.csv'
            results["dataset_file_size"] = os.path.getsize(ds_file)
        except Exception as e:
            logger.warning(f"cannot process results file: {unit_header.get('result_file')}")
            status.setdefault("expe_fail_reason", f"cannot process result file: {repr(e)}")
        finally:
            # cleanup after unit test
            logger.debug(f'removing temp config ({unit_header.get("config_file")}) and result ({unit_header.get("result_file")}) files.')
            try:
                os.remove(unit_header.get("config_file"))
            except FileNotFoundError as e:
                logger.warning(f'config file to remove not found: {unit_header.get("config_file")}')
            try:
                os.remove(unit_header.get("result_file"))
            except FileNotFoundError as e:
                logger.warning(f'result file to remove not found: {unit_header.get("result_file")}')
    
        writer = SqliteWrapper(db, logger)
        writer.save_results(unit_header.get("id"), config, status, results)

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
    # parser.add_argument('-n','--n-loops', help="repeat set of configs N-times", type=int, default=1)
    # parser.add_argument('-m','--run-mode', help="mode of runner", type=str, choices=["normal","finder","finder2"], default="normal")
    parser.add_argument('-s','--status-file', help="file where runner puts status of test serie", type=str, default=None)
    # parser.add_argument('-d','--dns-failed', help="do not start next expe in loop when previous one failed", action="store_true")
    args = parser.parse_args()

    # n_loops = args.n_loops if args.n_loops >= 1 else 1
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
    check_run_mode(config)

    multi_config, no_failed_configs = examine_multi_config(config, run_mode=config["run_mode"].get("name"))
    logger.info(f"Detected {len(multi_config)} valid configs, {no_failed_configs} failed one(s).")
    
    serie_status = SerieStatus(args.status_file)
    finder_report_list = []
    
    RUN_MODE = config.get("run_mode")
    sys_phy_memory = psutil.virtual_memory().total/1024**2

    # here we will have a loop of multiple tests
    len_multi_config = len(multi_config)
    for c_idx, rolling_config in enumerate(multi_config):
        logger.debug(f"#################################################")

        temp_run_mode_trace = []
        NEXT_RUN_MODE = RUN_MODE.copy()
        # temp_run_mode = args.run_mode
        # temp_dns_failed = args.dns_failed
        # temp_loop = True

        temp_finder_report = {
            "method": rolling_config['method'].get('name'),
            "dataset": rolling_config['dataset'].get('name'),
            "hostname": config["globals"].get("hostname"),
            "runner_type": rolling_config["runner"].get("type"),
            "init_algo": RUN_MODE.get("name"),
            "mem_min": None,
            "walker_steps": 0,
        }

        # we introduce control for looping test for the same config
        while NEXT_RUN_MODE not in [ None, False ] and NEXT_RUN_MODE.get("name") not in [ None, False ]:
            temp_run_mode = NEXT_RUN_MODE.copy()
            temp_run_mode_trace.append(temp_run_mode)
            NEXT_RUN_MODE["name"] = None       # if explicitly set by others, it will be performed once more    
        
            if temp_run_mode.get("name") in [ "normal", "tester" ]:
                n_dns = 0
                for l_idx in range(temp_run_mode.get("nloops")):
                    logger.debug(f"--------------------------------------------------")
                    logger.info(f'performing unit test {c_idx+1}/{len_multi_config}: iteration {l_idx+1}/{temp_run_mode.get("nloops")}, walker_steps: {temp_finder_report.get("walker_steps")}')
                    # if last call -> clean=True
                    status = run(config=rolling_config, clean=((c_idx+1)==len_multi_config and (l_idx+1)==temp_run_mode.get("nloops")) )
                    # logger.debug(f"unit test status: {status}")
                    logger.info(f"unit test completed: {status['expe_status']}")
                    serie_status.report_test(status, rolling_config)
                    # chcek, if we continue at expe_status='failed'
                    if status.get("expe_status") == "failed" and temp_run_mode.get("dns"):
                        n_dns = temp_run_mode.get("nloops") - l_idx - 1
                        if n_dns > 0:
                            logger.warning(f'we ommit remaining {n_dns}/{temp_run_mode.get("nloops")} iterations, due to failed expe in {l_idx+1} iteration')
                            serie_status.report_dns_tests(n_dns, temp_run_mode.get("nloops"), rolling_config)
                            break
                # we need to consider if it is the end or we should return to further iterations
                if temp_run_mode_trace[0].get("name") in [ "finder", "finder2" ]:
                    if n_dns > 0:   # some of tests failed
                        logger.info(f"switching back to 'walker'")
                        NEXT_RUN_MODE.update( { "name": "walker" } )
                    else:           # all tests passed
                        # we finally found the proper memory limit. we have to decide what to do with the result
                        # should we store finder results ???
                        temp_finder_report["mem_min"] = hr2bytes( rolling_config["runner"]["limits"]["memory"] ) // 1024**2
                        logger.info(f'found minimum memory limit for method={rolling_config["method"].get("name")} and dataset={rolling_config["dataset"].get("name")}: {temp_finder_report["mem_min"]}m (rounded up)')
                        finder_report_list.append(temp_finder_report.copy())

                        # save findings to external csv file
                        finder_db_file = config["globals"].get("finder_db", None)
                        if finder_db_file not in [ None, "" ]:
                            try:
                                logger.debug(f"trying to store finder report in: {finder_db_file}")
                                temp_df = pd.DataFrame.from_records( [ temp_finder_report ] )
                                finder_db_exists = os.path.isfile(finder_db_file) and os.path.getsize(finder_db_file)!=0
                                temp_df[['method','dataset','hostname','runner_type','init_algo','mem_min']].to_csv(
                                    finder_db_file, sep=';', mode='a', index=False, header=(not finder_db_exists)
                                )
                                # temp_df.to_csv(finder_db_file, sep=';', mode='a', index=False, header=(not finder_db_exists))
                                logger.info(f"finder report written to: {finder_db_file}")
                            except:
                                logger.warning(f"error while writing finder report to: {finder_db_file}")
                        pass
            
            elif temp_run_mode.get("name") in [ "finder" ]:
                # finder based on limiting the process and checking if it fails or succeeds
                logger.debug(f"==================================================")
                logger.info(f"finding memory limit for config {c_idx+1}/{len_multi_config}: method={rolling_config['method'].get('name')}, dataset={rolling_config['dataset'].get('name')}")
                # find memory limit for the method. we operate in MB

                min_mem = 0
                diff_min = 1
                max_mem = None
                limits = rolling_config["runner"].get("limits")
                cur_mem = 100
                f_idx = 0
                while True:
                    if cur_mem > sys_phy_memory:    # we exceeded physical memory of the machine
                        logger.warning(f"finder: physical memory of the machine exceeded")
                        break
                    f_idx += 1
                    limits["memory"] = f"{cur_mem}m"
                    status = run(config=rolling_config, clean=False)
                    # logger.info(f"unit test status: {status}")
                    serie_status.report_test(status, rolling_config)
                    logger.info(f"finder (config {c_idx+1}/{len_multi_config}): iteration {f_idx} ({cur_mem}m): {status.get('expe_status')}")
                    prev_mem = cur_mem
                    if status.get("expe_status") == "success":
                        max_mem = prev_mem
                    else:   # expe failed                    
                        min_mem = prev_mem
                    # memory limit for next iteration
                    cur_mem = prev_mem * 2 if max_mem is None else ( min_mem + max_mem )/2
                    # examine difference between max_mem and min_mem, and if lower than 1MB, end iteration
                    diff_mem = min_mem if max_mem is None else max_mem - min_mem
                    if diff_mem <= diff_min:
                        max_mem = round( max_mem + 0.5)
                        # logger.info(f"found minimum memory limit for method={rolling_config['method'].get('name')} and dataset={rolling_config['dataset'].get('name')}: {max_mem}m (rounded up)")
                        temp_finder_report["mem_min"] = max_mem
                        break
                    if f_idx >= 20:
                        logger.warning(f"finder: maximum number of iteration ({f_idx}) reached")
                        break
                # should we store finder results ??? not now, we'll test the found value first
                if temp_finder_report.get("mem_min") is not None:
                    logger.info(f'finder: found initial memory value: {temp_finder_report.get("mem_min")}m. switching to testing')
                    rolling_config["runner"]["limits"]["memory"] = f'{temp_finder_report.get("mem_min")}m'
                    NEXT_RUN_MODE.update( { "name": "tester", "dns": True } )
                else:
                    logger.warning(f'finder: aborting')
                    finder_report_list.append(temp_finder_report.copy())

            elif temp_run_mode.get("name") in [ "finder2" ]:
                logger.debug(f"==================================================")
                # finder algorithm based on cgroups monitoring
                logger.info(f"finding memory limit for config {c_idx+1}/{len_multi_config}: method={rolling_config['method'].get('name')}, dataset={rolling_config['dataset'].get('name')}")
                # do not set memory limit, switch on monitor
                rolling_config["runner"]["monitor"] = True
                rolling_config["runner"]["limits"]["memory"] = None
                max_memory_usage = []
                
                for l_idx in range(temp_run_mode.get("nloops")):
                    status = run(config=rolling_config, clean=False )
                    # logger.info(f"unit test status: {status}")
                    serie_status.report_test(status, rolling_config)
                    l_mem_usage = status.get("monitoring_data").get("memory.current")
                    l_mem_usage = l_mem_usage / 1024**2 if l_mem_usage is not None else None
                    max_memory_usage.append(l_mem_usage)
                    logger.info(f'finder2 (config: {c_idx+1}/{len_multi_config}): iteration {l_idx+1}/{temp_run_mode.get("nloops")}: {status.get("expe_status")}, max_mem_usage={l_mem_usage}m')
                
                temp_mem_min = round( max(max_memory_usage) + 0.5 )
                temp_finder_report["mem_min"] = temp_mem_min
                temp_finder_report["mem_usage_iter"] = max_memory_usage
                # finder_report_list.append(temp_finder_report)

                # now, let's decide if we temporairly switch to "normal" mode for testing found mem_min
                # logger.debug(f"switching temporairly to 'tester' run-mode for testing found limit: {temp_mem_min}M")
                logger.info(f'finder2: found initial memory value: {temp_finder_report.get("mem_min")}m. switching to testing')
                rolling_config["runner"]["monitor"] = False
                rolling_config["runner"]["limits"]["memory"] = f"{temp_mem_min}m"
                NEXT_RUN_MODE.update( { "name": "tester", "dns": True } )

            elif temp_run_mode.get("name") in [ "walker" ]:
                logger.debug(f"--------------------------------------------------")
                temp_finder_report["walker_steps"] += 1
                if temp_finder_report.get("walker_steps") <= temp_run_mode.get("max_inc_steps"):
                    # increase memory limit 
                    logger.info(f'walker (step: {temp_finder_report["walker_steps"]}): increasing memory limit {rolling_config["runner"]["limits"]["memory"]} by {temp_run_mode.get("mem_inc_step")}')
                    cur_mem_limit = hr2bytes(rolling_config["runner"]["limits"]["memory"])
                    mem_inc_step = hr2bytes(temp_run_mode.get("mem_inc_step"))
                    rolling_config["runner"]["limits"]["memory"] = bytes2hr( cur_mem_limit + mem_inc_step )
                    NEXT_RUN_MODE.update( { "name": "tester" } )
                else:
                    # we reached maximum number of inc. steps
                    logger.warning(f'walker: reached maximum number of increment steps ({temp_run_mode.get("max_inc_steps")}). aborting')
                    temp_finder_report["mem_min"] = None
                    finder_report_list.append(temp_finder_report.copy())
            else:
                logger.warning(f'unknown run-mode: {temp_run_mode.get("name")}')
        # end temporal looping
    # end config iteration


    logger.debug(f"#################################################")
    logger.info(f"test serie has been completed !")
    serie_status_dict = serie_status.get_status()
    logger.info(f"no of unit tests: completed={serie_status_dict.get('completed_tests')}, process_ok={serie_status_dict.get('process_ok')}, expe_ok={serie_status_dict.get('expe_ok')}")

    # if args.run_mode in [ "finder", "finder2" ]:
    if len(finder_report_list) > 0:
        logger.info(f"FINDER REPORT:")
        for r in finder_report_list:
            logger.info(r)
    # elif args.run_mode == "normal":
    # did not started tests report
    if len(serie_status_dict.get("dns_tests")) > 0:
        logger.info(f"did not started unit tests:")
        for ss in serie_status_dict.get("dns_tests",[]):
            logger.info(f"{ss}")
    # failed test report
    if len(serie_status_dict.get("failed_tests")) > 0:
        logger.info(f"failed unit tests:")
        for ss in serie_status_dict.get("failed_tests",[]):
            logger.info(f"{ss}")
    # resoring the original signal handlers
    # signal.signal(signal.SIGCHLD, old_alarm_handler)
    # signal.signal(signal.SIGUSR1, old_sigusr1_handler)

    # logger.debug(f"removing runner's pid file: {args.pid_file}")
    # os.remove(args.pid_file)
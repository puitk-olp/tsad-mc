import os
import fcntl
import yaml
import json
import pickle
import pandas as pd
import itertools
import local_utils.defaults as defaults
import re
# import logging

# logger = logging.getLogger("runner")

def _get_ext(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext[1:] if len(ext)>0 else ""

def _get_mode(ext: str) -> str:
    return "b" if ext in [ "pkl", "pickle" ] else ""

def read_file(input_file: str = defaults.CONFIG_FILE):
    try:
        ext = _get_ext(input_file).lower()
        mode = "r" + _get_mode(ext)
        with open(input_file, mode) as file:
            if ext in [ "yaml", "yml" ]:
                data = yaml.safe_load(file)
            elif ext == "json":
                data = json.load(file)
            elif ext in [ "pkl", "pickle" ]:
                data = pickle.load(file)
            else:
                data = file.read()
    except:
        raise IOError(f'Error while rerading "{input_file}" file')
    return data

def write_file(data: dict|str, output_file: str, append: bool = False):
    file = None
    try:
        # make dirs
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # choose proper file format writer
        ext = _get_ext(output_file).lower()
        mode = ("a" if append else "w") + _get_mode(ext)
        with open(output_file, mode) as file:
            # Acquire exclusive lock on the file
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            if ext in [ "yaml", "yml" ]:
                yaml.dump(data, file)
            elif ext == "json":
                json.dump(data, file, ensure_ascii=False)
            elif ext in [ "pkl", "pickle" ]:
                pickle.dump(data, file)
            else:
                file.write(str(data))
            # immediate write to file
            file.flush()
            # Release the lock
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    except:
        raise IOError(f"Error during writing to '{output_file}' file")

def check_globals(config: dict):
    config.setdefault("globals", {})
    config["globals"].setdefault('comment',defaults.COMMENT)
    config["globals"].setdefault('user',os.getlogin())
    config["globals"].setdefault('hostname',os.uname().nodename)
    config["globals"].setdefault("temp_dir", f"{defaults.TEMP_DIR}")

def check_run_mode(config: dict):
    config.setdefault("run_mode", {})
    config["run_mode"].setdefault('name', defaults.RUN_MODE)
    config["run_mode"].setdefault('dns', defaults.DNS_FAILED)
    config["run_mode"].setdefault('nloops', defaults.NLOOPS)
    config["run_mode"].setdefault("mem_inc_step", defaults.MEM_INC_STEP)
    config["run_mode"].setdefault("max_inc_steps", defaults.MAX_INC_STEPS)

def check_metrics_config(metrics_config : str|list, metrics_allowed : list = []):
    # metrics_config = self._config.setdefault("metrics",defaults.METRICS_NAME)
    if metrics_config == "all":
        metrics_config = metrics_allowed
    elif type(metrics_config)==str:
        metrics_config = [] if metrics_config.lower() == "none" else [ metrics_allowed ]
    elif type(metrics_config)!=list:
        raise ValueError("Unknown definition of metrics")
    for m in metrics_config:
        if m not in metrics_allowed:
            raise NotImplementedError("Unknown metric")
    return metrics_config



def _get_ds_list(ds_dir: str = None):
    dir_list = []
    for p in os.listdir(ds_dir):
        p_split = os.path.splitext(p)
        if p_split[1] in [ ".csv" ]:
            dir_list.append(p_split[0])
    dir_list.sort()
    return dir_list

def check_dataset_config(ds_config: str):
    ds_set = set()
    if ds_config is None or ds_config.get("dir") is None:
        raise ValueError('No or invalid dataset config provided')
    ds_config["dir"] = os.path.expanduser(ds_config.get("dir"))
    if not os.path.isdir(ds_config.get("dir")):
        raise NotADirectoryError(f'no such dir: {ds_config.get("dir")}')
    ds_list = _get_ds_list(ds_config.get("dir"))
    # select ds by names
    if ds_config.get("name", None) is not None:
        if type(ds_config.get("name"))!=list:
            ds_config["name"] = [ ds_config.get("name") ]
        for d in ds_config.get("name"):
            if d in ds_list:
                ds_set.add(d)
    # select ds by indexes
    if ds_config.get("index") is not None:
        if type(ds_config.get("index"))!=list:
            ds_config["index"] = [ ds_config.get("index") ]
        for d in ds_config["index"]:
            ds_set.add(ds_list[d])
        del ds_config["index"]
    # select ds by regular expression
    if type(ds_config.get("re"))==str:         # regexp for name
        for d in ds_list:
            if re.match(ds_config.get("re"),d) is not None:
                ds_set.add(d)
        del ds_config["re"]
    ds_config["name"] = list(ds_set)


def examine_multi_config(multi_config: dict, run_mode: str = "normal"): # -> list[dict]:
    # prepare config lists for permutations
    runner_config = multi_config.setdefault("runner", {})
    
    # examine limits and timeouts
    if run_mode in [ "finder", "finder2" ]:
        # in "finder(2)" modes, do not set timeout nor limits
        timeout = [ 0 ]
        limits = {
            "cpu": [ None ],
            "memory": [ None ],     # memory limit will be set by finder algorithm
            "swap": [ "0m" ]
        }
    else:
        # timeout
        timeout = runner_config.setdefault("timeout", [0])
        if type(timeout)!=list:
            timeout = [ timeout ]
        # limits
        limits = runner_config.setdefault("limits",{})
        for l in [ "cpu", "memory", "swap" ]:
            limits.setdefault(l,[None])
            if type(limits[l])!=list:
                limits[l] = [ limits[l] ]
    
    # common for both modes
    # examine dataset
    # # ds_config = multi_config.setdefault("dataset", {})
    ds_config = multi_config.get("dataset")
    # if ds_config is None or ds_config.get("dir") is None:
    #     raise ValueError("No or invalid dataset config provided")
    # # ds_config.setdefault("dir", defaults.DATASET_DIR)
    # if ds_config.get("name", None) is not None:
    #     if type(ds_config.get("name"))!=list:
    #         ds_config["name"] = [ ds_config.get("name") ]
    # # examine additional conditions for dataset selection
    # df = pd.read_csv(ds_config.get("summary", defaults.DATASET_SUMMARY_FILE), sep=";")
    # t = df.index.isna()     # select no rows
    # if ds_config.get("index") is not None:      # index
    #     t = t | df.index.isin( ds_config.get("index") if type(ds_config.get("index"))==list else [ ds_config.get("index") ] )
    # if ds_config.get("group") is not None:      # dataset group
    #     t = t | df["dataset"].isin( ds_config.get("group") if type(ds_config.get("group"))==list else [ ds_config.get("group") ] )
    # if ds_config.get("re") is not None:         # regexp for name
    #     t = t | df["name"].str.match( ds_config.get("re") )
    # ds_filtered = set(df[t]["name"])
    # for n in ds_config.get("name", []):
    #     ds_filtered.add(n)
    # ds_config["name"] = list(ds_filtered)
    check_dataset_config(ds_config)

    # examine method
    m_config = multi_config.get("method", {})
    if m_config.get("name") is None:
        raise ValueError("No method name provided")
    if type(m_config.get("name"))!=list:
        m_config["name"] = [ m_config.get("name") ]

    # permutations of: cpu, mem, memswap, timeout, dataset, method
    config_to_permute = [ limits["cpu"], limits["memory"], limits["swap"], timeout, ds_config["name"], m_config.get("name") ]
    config_permutations = list(itertools.product(*config_to_permute))
    unit_configs = []
    no_failed_configs = 0
    finder_db_df = None

    for cp in config_permutations:
        # print(f"examine config permutation: {cp}")
        c = {
            "globals": multi_config.get("globals"),
            "runner": {
                "type": runner_config.get("type"),
                "params": runner_config.get("params"),
                "timeout": cp[3],
                "monitor": runner_config.get("monitor", False)
            },
            "dataset": {
                "dir": ds_config.get("dir"),
                "name": cp[4]
            },
            "method": {
                "name": cp[5]
            },
            "metrics": multi_config.get("metrics", defaults.METRICS_NAME)
        }
        for l in [("cpu",cp[0]),("memory",cp[1]),("swap",cp[2])]:
            # print(f"examine limits: {l}")
            if l[1] not in ["None", None]:
                c["runner"].setdefault("limits",{})[l[0]] = l[1]

        # examine "X" value for memory limit -> then get limit from finder db
        if run_mode in ["normal","tester"] and c["runner"]["limits"].get("memory",None)=="X":
            finder_db_file = multi_config["globals"].get("finder_db")
            if finder_db_df is None:
                if os.path.isfile(finder_db_file):
                    finder_db_df = pd.read_csv(finder_db_file, sep=";")
            if finder_db_df is not None:
                # logger.debug(f"m={cp[5]}, ds={cp[4]}, h={multi_config['globals'].get('hostname')}, rt={runner_config.get('type')}")
                df_limit = finder_db_df.loc[finder_db_df.method.eq(cp[5]) & finder_db_df.dataset.eq(cp[4]) & finder_db_df.hostname.eq(multi_config['globals'].get('hostname')) & finder_db_df.runner_type.eq(runner_config.get("type"))]
                mem_min = f"{df_limit['mem_min'].max()}m"
                c["runner"]["limits"]["memory"] = mem_min
            # if memory limit is still 'X' -> discard config
            if c["runner"]["limits"].get("memory",None)=="X":
                no_failed_configs += 1
                continue            
        # place unit config on the list
        unit_configs.append(c)
        # yield (c, no_unit_configs)
    
    return unit_configs, no_failed_configs


BYTE_UNITS = [ "b", "k", "m", "g", "t" ]

def hr2bytes(hr_str: str) -> int:
    hr_str = hr_str.lower()
    end = len(hr_str)
    if hr_str[-1].isdigit():
        unit = "b"
    elif hr_str[-1] in BYTE_UNITS:
        unit = hr_str[-1]
        end -= 1
    else:
        raise ValueError(f"unknown byte value: {hr_str}")
    value = float(hr_str[0:end])
    value *= 1024**BYTE_UNITS.index(unit)
    return int(value)    # in bytes

def bytes2hr(value: int) -> str:
    for i in range(len(BYTE_UNITS)):
        if i < len(BYTE_UNITS)-1 and value > 1024**(i+1):
            continue
        value /= 1024**i
        return f"{value}"+(BYTE_UNITS[i] if i > 0 else "")






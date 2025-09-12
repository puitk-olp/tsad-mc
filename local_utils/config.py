import os
import sys
import yaml
import json
import pickle
import pandas as pd
import itertools
import defaults

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
        raise IOError(f"Error while rerading '{input_file}' file")
    return data

def write_file(data: dict|str, output_file: str):
    try:
        ext = _get_ext(output_file).lower()
        mode = "w" + _get_mode(ext)
        with open(output_file, mode) as file:
            if ext in [ "yaml", "yml" ]:
                yaml.dump(data, file)
            elif ext == "json":
                json.dump(data, file, ensure_ascii=False)
            elif ext in [ "pkl", "pickle" ]:
                pickle.dump(data, file)
            else:
                file.write(data)
    except:
        raise IOError(f"Error during writing to '{output_file}' file")

def check_globals(config: dict):
    config.setdefault("globals", {})
    config["globals"].setdefault('comment',defaults.COMMENT)
    config["globals"].setdefault('user',os.getlogin())
    config["globals"].setdefault('hostname',os.uname().nodename)
    # paths = config["globals"].setdefault('paths', {})


def examine_multi_config(multi_config: dict) -> list[dict]:
    # prepare config lists for permutations
    runner_config = multi_config.setdefault("runner", {})
    
    # examine limits
    limits = runner_config.setdefault("limits",{})
    for l in [ "cpus", "mem_limit", "memswap_limit" ]:
        limits.setdefault(l,[-1])
        if type(limits[l])!=list:
            limits[l] = [ limits[l] ]
    
    # examine timeouts
    timeout = runner_config.setdefault("timeout", [0])
    if type(timeout)!=list:
        timeout = [ timeout ]
    
    # examine dataset
    ds_config = multi_config.setdefault("dataset", {})
    ds_config.setdefault("dir", defaults.DATASET_DIR)
    if ds_config.get("name", None) is not None:
        if type(ds_config.get("name"))!=list:
            ds_config["name"] = [ ds_config.get("name") ]
    # examine additional conditions for dataset selection
    df = pd.read_csv(ds_config.get("summary", defaults.DATASET_SUMMARY_FILE), sep=";")
    t = df.index.isna()     # select no rows
    if ds_config.get("index") is not None:      # index
        t = t | df.index.isin( ds_config.get("index") if type(ds_config.get("index"))==list else [ ds_config.get("index") ] )
    if ds_config.get("group") is not None:      # dataset group
        t = t | df["dataset"].isin( ds_config.get("group") if type(ds_config.get("group"))==list else [ ds_config.get("group") ] )
    if ds_config.get("re") is not None:         # regexp for name
        t = t | df["name"].str.match( ds_config.get("re") )
    ds_filtered = set(df[t]["name"])
    for n in ds_config.get("name", []):
        ds_filtered.add(n)
    ds_config["name"] = list(ds_filtered)

    # examine method
    m_config = multi_config.get("method", {})
    if m_config.get("name") is None:
        raise ValueError("No method name provided")
    if type(m_config.get("name"))!=list:
        m_config["name"] = [ m_config.get("name") ]

    # permutations of: cpu, mem, memswap, timeout, dataset, method
    config_to_permute = [ limits["cpus"], limits["mem_limit"], limits["memswap_limit"], timeout, ds_config["name"], m_config.get("name") ]
    config_permutations = itertools.product(*config_to_permute)
    unit_configs = []

    for cp in config_permutations:
        # print(f"examine config permutation: {cp}")
        c = {
            "globals": multi_config.get("globals"),
            "runner": {
                "type": runner_config.get("type"),
                "params": runner_config.get("params"),
                "timeout": cp[3],
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
        for l in [("cpus",cp[0]),("mem_limit",cp[1]),("memswap_limit",cp[2])]:
            # print(f"examine limits: {l}")
            if l[1] not in [-1, "None", None]:
                c["runner"].setdefault("limits",{})[l[0]] = l[1]
        
        unit_configs.append(c)
    
    return unit_configs






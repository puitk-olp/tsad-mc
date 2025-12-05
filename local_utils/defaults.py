import os

# BASE_DIR="/vol/FFL"
# WORKING_DIR=f"{os.getcwd()}"
WORKING_DIR=f"."
CONFIG_FILE="config.yaml"
LOG_CONFIG_FILE=f"log.yaml"

TEMP_DIR=f"{WORKING_DIR}/temp"
RESULT_DIR=f"{WORKING_DIR}/results"

DATASET_DIR="/vol/FFL/datasets/TSB-AD-U"
DATASET_SUMMARY_FILE=f"{DATASET_DIR}/Summary.csv"

COMMENT=""

DB_FILE=f"{RESULT_DIR}/results.db"
DB_NAME="expe"

TIME_FORMAT="%Y-%m-%d %H:%M:%S %Z"

METRICS_NAME="all"

RUNNER_TYPE="systemd"
# DOCKER_IMAGE="tsbad:0.0.5-cpu"
TEMP_CONFIG_FILE=f"{TEMP_DIR}/{CONFIG_FILE}"

### run mode params
RUN_MODE="tester"
DNS_FAILED=False
NLOOPS=10
MEM_INC_STEP="1m"
MAX_INC_STEPS=20


# METRICS_CMD=["python3",f"{WORKING_DIR}/metrics.py","--config",f"{TEMP_CONFIG_FILE}"]

def get_unit_cmd(script_dir: str = None, config_file: str = None):
    run_dir = script_dir if script_dir is not None else WORKING_DIR
    run_config_file = config_file if config_file is not None else f'{TEMP_DIR}/{CONFIG_FILE}'
    unit_cmd = [
        "python3",
        f"{run_dir}/Unit_Pipeline.py",
        "--config-file",
        f"{run_config_file}"
    ]
    return unit_cmd

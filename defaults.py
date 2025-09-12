BASE_DIR="/vol/FFL"
WORKING_DIR=f"{BASE_DIR}/code/pablo"
CONFIG_FILE="config.yaml"

TEMP_DIR=f"{WORKING_DIR}/temp"
RESULT_DIR=f"{WORKING_DIR}/results"

DATASET_DIR="/vol/FFL/datasets/TSB-AD-U"
DATASET_SUMMARY_FILE=f"{WORKING_DIR}/Summary.csv"
DATASET_NAME="001_NAB_id_1_Facility_tr_1007_1st_2014"

METHOD="FFT"

USER="unknown"
HOST="unknown"
COMMENT=""

DB_FILE=f"{RESULT_DIR}/results.db"
DB_NAME="expe"

TIME_FORMAT="%Y-%m-%d %H:%M:%S %Z"

METRICS_NAME="all"

RUNNER_TYPE="docker"
DOCKER_IMAGE="tsbad:0.0.4-cpu"
TEMP_CONFIG_FILE=f"{TEMP_DIR}/{CONFIG_FILE}"
LOG_CONFIG_FILE=f"{WORKING_DIR}/log.yaml"

CMD=["python3",f"{WORKING_DIR}/Unit_Pipeline.py","--config",f"{TEMP_CONFIG_FILE}"]

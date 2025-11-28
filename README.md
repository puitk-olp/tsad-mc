TSAD-MC: Time Series Anomaly Detection - Memory Constraints
===========================================================

Authors: F. Guyard, P. Piotrowski \
Version: 0.5 (document edition is still in progress) \
Last update: 2025.11.26

I. Overview
-----------

The aims of the project are:

- to provide a tools for studying resource constraints in Time Series Anomaly Detection algorithms,
- to enable automatization to the process of finding minimal resources necessary for each TS-AD method.

Our source code is built on top of [TSB-AD](https://github.com/TheDatumOrg/TSB-AD) project's code.


II. General Structure
--------------------

The architecture of our code is divided into two main parts:

- [Unit_Pipeline.py](Unit_Pipeline.py) script and its dependencies - it is responsible for running unit test with one selected config: method (TSB-AD model), dataset, metrics set. \
It can be run manually or instantiated by `runner.py` script (see below). If run manually:
  ```
  (tsbad) tsad-mc/ $ python3 Unit_Pipeline.py --config-file <unit-test-config-file.yaml>
  ```
  Note: Usually, there is no necessity to run it manually. Use `runner.py` script instead.

- [runner.py](runner.py) script and its dependencies - it manages serie of unit tests depending on configuration file: examine multiconfig, follow run mode (strategy), instantiation of `Unit_Pipeline.py` script, storing results if necessary, creating reports, etc. \
It is also responsible for applying limits (cpu, memory, swap, timeout) for the unit test script, if necessary. \
We run it manually:
  ```
  (tsbad) tsad-mc/ $ python3 runner.py --config-file <runner-config-file.yaml>
  ```

### Config file structure for `runner.py` script

The structure of the config file consists of several sections:

- `globals` - defines the places where results (sqlite3 file) and finder reports (CSV file) will be stored as well as additional info that will be added to result records.
- `run_mode` - defines `runner.py` algorithm and its parameters, which will be performed on each config (see [next subsection](#run-modes) for details).
- `runner` - defines the runtime (`systemd` or `docker`) and its arguments, which will be instantiating unit test script, as well as limits that will be applied to it,
- `dataset` - defines list of datasets on which tests will be performed
- `method` - defines method list and their parameters 
- `metrics` - defines list of metrics that will be calculated over the score of a method in each case (config permutation)

We use `YAML` format for config files, but if preferred, you can use equivalent config file in `JSON` format.

*Note: Please, refer to [example config file](config/config.yaml) for detailed information of each config section and key.*


Below, there are short explanations of selected sections of config file.

#### Run modes

There are 3 main run modes for `runner.py` script:

- `tester` (or `normal`) mode - it takes `limits` values (cpu, memory, swap, timeout), method, dataset lists, makes permutation, and create unit test config list based on permutation set. Than, each config is run as a unit test requested number of times (`nloops` param).

- `finder` mode - the goal of this mode is to find minimal memory required by `Unit_Pipeline.py` script to succeed requested number of times in a row with particular config (method, datatset). The algorithm is composed of couple steps:

	* `find init value` step - where runner tries to find init value of memory limit where unit test succeeds at least once, by oscilating with minimum and maximum memory limit values, narrowing them depending on unit test results, until the difference is smaller then requested.
	* `tester` step - runner tries to run serie of unit tests (requested number of times), and if fails, moves to the next step, and if succeeds, reports found value!
	* `walker` step - increases memory limit value by reuested margin, and moves back to `tester` step; if `walker` steps number exceeds configured limit, the algorithm gives up and reports that memory limit value was not found.

- `finder2` mode - works similar to `finder` mode, but uses different approach to `find init value` step, by observing memory usage of `cgroup` used by a process in several tests (without applying the memory limit). The rest works the same.

Note: `finder` and `finder2` modes can also work with multiconfig (multiple methods and dataset), but they do not take `limits` from config file, and establish them by theirselves instead.


#### Runner type

We provide two methods of instantiating unit test script (`Unit_Pipeline.py`) that enable the tools for resource limitation of launched process:

- `docker` - the test script is launched inside a docker container, run with previously built docker image. \
  We manage this type of runner with Python's `docker` module, where process' launching is equivalent to `docker run` command line,
- `systemd` - it's another way of launching unit test script, here with `systemd-run` command.

Both runner types use the same mechanism for applying and enforcing process limits (here `CGroups`).

The runner type can be configured in [main config file](config/config.yaml) in `runner.type` subsection:
```
runner:
  type: docker               # type of a runner docker, systemd
  params:
    image: tsbad:0.0.5-cpu   # image for docker runner
```
*Note: the only required `param` is `image` for `docker` type, which describes a docker image from which container will be started.*


#### Resource limits
The runner can apply the resource limits for a launched unit test script. Those are:

- `cpu` - cpu core limit,
- `memory` - memory limit that a process can consume,
- `swap` - swap limit that process is allowed to use,
- `timeout` - maximum allowed duration of a process, if exceeded, a process will be killed. By default it is 0 - no timeout.

Those are configured in `runner.limits` and `runner.timeout` subsections.
```
runner:
  ...
  limits:
    # cpus: 1
    memory : [ X ]     # it stands for memory only limit
    swap : [ "0m" ]    # it stands for swap only limit
  timeout: 0
```
*Note: `limits` configured here will be applied only in `tester` (`normal`) [run mode](#run-modes). Other run modes will apply their own limits. `timeout` works in all run modes.*


#### Results saving

By default, each unit test result (succeeded or failed) as well as many additional data (including config and limits) are stored into `sqlite3` database file (configured in `globals.db` subsection).
```
globals:
  db: 
    file: results/results.db    # path for sqlite db file (result store)
    name: expe					# sql table to which results will be inserted
```


#### Finder report saving

When in `finder` or `finder2` mode, a report of the minimal memory value finding result may be writter to external `CSV` file. In order to do that, please configure `globals.finder_db` key (path to `CSV` file).
```
globals:
  ...
  finder_db: results/tsbad-report.csv
```
After some finding runs, content of that `CSV` file may look like the following:
```
(tsbad) <repo-dir>$ cat results/tsbad-report.csv
method;dataset;hostname;runner_type;init_algo;mem_min
FFT;295_TODS_id_9_Synthetic_tr_1250_1st_2046;nuc-i7-1;docker;finder2;209
FFT;295_TODS_id_9_Synthetic_tr_1250_1st_2046;nuc-i7-1;docker;finder;203
NORMA;295_TODS_id_9_Synthetic_tr_1250_1st_2046;nuc-i7-1;docker;finder;357
NORMA;357_UCR_id_55_Facility_tr_12500_1st_46600;nuc-i7-1;docker;finder;389
```



III. Environment preparation
----------------------------

#### Prerequisites

As we use typical Linux tools, like: `docker`, `systemd-run` or `cgroups` mechanism, all the code is supposed to be run on Linux machines.

Please, setup a Linux machine with minimal necessary software.
Here is an example of the procedure for Debian-like Linux machine:
```
~$ sudo apt-get update
~$ sudo apt-get install python3 python3-venv git wget unzip
```

#### Download and unarchive TSB-AD-U dataset package
All tests we performed used TSB-AD-U datasets. They can be downloaded as a ZIP archive.
```
~$ mkdir datasets && cd datasets
~$ wget https://www.thedatum.org/datasets/TSB-AD-U.zip
~$ unzip TSB-AD-U.zip
```
*Note: You can choose other dir for dataset storage. In both cases, write it down. The path will be necessary later.*

#### Prepare Python virtual environment
Although it is not mandatory, we highly recommend configuration of Python virtual environment and performing any test under it. \
*Note: Some OSes may enforce you to do that, if you do not have `root` or `sudo` rights.*

Here is an example with `venv`:
```
~$ python3 -m venv tsbad
~$ source tsbad/bin/activate
(tsbad) ~$ 
```

#### Clone our repo
```
(tsbad) ~$ git clone https://github.com/puitk-olp/tsad-mc.git
(tsbad) ~$ cd tsad-mc
```

#### Install dependencies for `runner.py` script
```
(tsbad) tsad-mc/ $ pip install -r requirements/runner.txt
```

#### (optional) Install dependencies for `Unit_Pipeline.py` script
Necessary, if you will be running it manually or through `runner.py` script via `systemd` runtime.
```
(tsbad) tsad-mc/ $ pip install -r requirements/unit.txt
```

#### (optional) Build docker image
Necessary, if you'll be running `Unit_Pipeline.py` script via `docker` container.
```
(tsbad) tsad-mc/ $ docker build -t tsbad:0.0.5-cpu -f docker/Dockerfile .
```
By default, our image is built from `python:3.12-slim` image. If required, this can be adjusted in very first line of [Dockerfile](docker/Dockerfile). \
*Note: Edit it only if you know what you do!*


Verify if the docker image is present in the system:
```
(tsbad) tsad-mc/ $ docker image ls
REPOSITORY           TAG         IMAGE ID       CREATED        SIZE
tsbad                0.0.5-cpu   28d1871943ca   2 months ago   1.52GB
```


The environment is now ready to perform `TSB-AD` tests.


IV. Running experiments
------------------------
While we have runtime environment installed and configured, we can start performing tests.

### Config file preparation
First, we need to prepare config file - we can base on example config file provided by repo or directly adjust it to fulfill our requirements.

We have to determine several things:

- whether we want to store results in `sqlite3` db, finder reports in `csv` file,
- which runner we want to use: `docker` or `systemd`,
- in what `run_mode` we want to launch `runner.py`,
- for which methods we'd like to run testing,
- what datasets will be used,
- what metrics we want to calculate over scores produced by methods, if any.

An example config file (`config/config.yaml`) may look like this:
```
globals:
  comment: "nloops"
  # user: pablo           # if ommited, username from OS is taken
  # hostname: generic     # if ommited, hostname from OS is taken

  db: 
    file: results/results.db     # path for sqlite db file (result store).
    name: expe                   # name of the table to store results.

  finder_db: results/tsbad-mins.csv		# memory limit finder report place

run_mode:             # whole section for run-mode config
  name: finder        # run_mode to be launched: tester, finder, finder2
  dns: True           # do not start next unit test run when previous failed
  nloops: 10          # how many tests in a row we expect to be success
  mem_inc_step: 1m    # value by the which we increase memory limit (in walker step) 
  max_inc_steps: 10   # maximum number of steps walker will perform before giving up.

runner:
  type: docker               # type of a runner. currently implemented: docker, systemd
  params:
    image: tsbad:0.0.5-cpu    # image for docker runner
  limits:
    memory : [ X ]     # it stands for memory only limit
    swap : [ "0m" ]    # it stands for swap only limit
  timeout: 0

dataset:
  dir: ~/datasets/TSB-AD-U		# (optional) dir where datasets are stored.
  
  # name/index/group/re - keys to select datasets for testing. one of them has to be configured (may be all). 
  # name: 001_NAB_id_1_Facility_tr_1007_1st_2014	# name or list of ds names 
  index: [ 294, 356, 224 ]						# index of sorted list of dataset names
  # group: [ WSD, NAB ]							# chooses all datasets within selected group(s)
  # re: "filter: "^295_|^357_|^225_""			# regular expression on ds name

method:
  # possible values for name: [ FFT, SR, Sub_IForest, IForest, LOF, Sub_LOF, POLY, MatrixProfile, Sub_PCA, Sub_KNN, KMeansAD, KMeansAD_U, KShapeAD, COPOD, COF, EIF, RobustPCA, Left_STAMPi, SAND, OCSVM, Sub_OCSVM, AutoEncoder, CNN, LSTMAD, TranAD, TimesNet, FITS, Donut ]
  name: [ Sub_LOF, NORMA ]
  
# metrics used for test. possible values: 'all', 'AUC-PR','AUC-ROC','VUS-PR','VUS-ROC','Standard-F1','PA-F1','Event-based-F1','R-based-F1','Affiliation-F' + special value: 'none' -> do not calculate metrics at all, store only 'score'
metrics: none
```
*Note: adjust `dataset.dir` key if needed, with the value memorized in [step above](#download-and-unarchive-tsb-ad-u-dataset-package)!*

### Log config file adjustment
If you want to adjust logging config, e.g. severity of loggers, handlers, places where logs have to land, or their format, please review [log.yaml](log.yaml) file. 

### Launching serie of tests
Once everything is ready, we launch serie of tests with:
```
(tsbad) tsad-mc/ $ python3 runner.py --config-file config/config.yaml
```


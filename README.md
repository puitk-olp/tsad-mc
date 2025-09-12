HOWTO TSB-AD
F. Guyard + P.Piotrowski
2025.08.18

-I. General Structure

When connected on the management platform or on other computers of the platform all codes are located in the shared volume /vol/FFL.

	- /vol/FFL/datasets: directory containing the various datasets

	- /vol/FFL/datasets/TSB-AD-U: univariate timeseries provided by TSB-AD

	- /vol/FFL/code: repository for various code. You can create your own directory to store your code (or data) and access them from any computer of the platform.

	- /vol/FFL/code/pablo : all the code to run the (modified) TSB-AD anomaly detection framework. Among the provided modifications, I add timing for the
                                initialization of (python) anomaly detection method, for the training part (0.0 when the method is unsupervised) and for the 
								test on the dataset
Currently the code can be run for one method and one dataset at the time. The config.yaml file indicates what is performed.

- /vol/FFL/code/pablo/docker/dockerfile: the docker file allowing to generate docker container. In this container, the shared volume /vol/FFL is mounted
  on /mnt/FFL. It means that each time you want to acces to a file F in the shared volume you have to read it in/mnt/FFL. For instance the docker file /vol/FFL/code/fred/docker/dockerfile can be access inside a running docker as
  /mnt/FFL/code/fred/docker/dockerfile

  - /vol/FFL/code/pablo/config.yaml: the configuration of the experiment. It contains all the parameters for running the docker (image, limitations),
    the databases to store the results, the anomaly detection method to be used,
    the method experimental parameters, the dataset, the metrics (currently I just allows to compute all methods available in
    TSB-AD. But the computation cost is not incorporated in the timing evaluation of the method. So the computation of all metrics do not
    add some time in the time evaluation (initialization, training and test) of a method.

    TO DO: if necessary modify to use only one metric. But I'm not sure it is necessary at all

    ```
    : 
    						     - since I initially made a bash script to run an experiment, I wrote the docker parameters on single yaml lines
    							which was easier to manage with bash (I wanted avoiding writing a yaml parser in bash :-)).For instance: 

    							docker_image: tsbad:0.0.3-cpu-pablo

    							docker_cpu_limit: "0.1"

    							##ram limit 200m for 200MB, 1g for 1GB etc..
    							docker_ram_limit: 200m
    							#docker_swap_limit: 500MB
    							#docker_time_limit: 1h

    						Here for example, the experiment is runned with just the cpu and the ram limits. The other are commented meaning they
                              will not be taken into account. 

    						TODO: Now that I wrote python script to execute the experiments (make_expe.py), we could make the config file cleaner
    						      by grouping parameters like


    							docker:
    								image: tsbad:0.0.3-cpu-pablo
    								cpu_limit: "0.1"
    								ram_limit: 200m

    							etc..
    							Of course the parameters have to be extracted adequately in the make_expe.py
    ```

    - /vol/FFL/code/pablo/make_expe.py: the script launching one experiment (one method and one dataset)
    - /vol/FFL/code/pablo/Unit_Pipeline.py: a python script executed INSIDE the docker and managing the process of anomaly detection
      and saving the results in the sqlite3 database.
    - /vol/FFL/code/pablo/run_unit_method.py: performs an anomaly detection on one dataset. This script is launched by
      Unit_Pipeline.py
    - /vol/FFL/code/pablo/local_utils/: contains simple useful python code (Timer, Logger) used in run_unit_method.py
    - /vol/FFL/code/pablo/results/: currently the directory where are stored the databases. You can change this by changing
      the following key in config.yaml
      db:
      file: /vol/FFL/code/pablo/results/results_db.db
    - /vol/FFL/code/pablo/trash/: directory where temporary files are stored during the process. Nothing useful after the experiment.
    - /vol/FFL/code/pablo/model/: contains the process of anomaly detection.
    - /vol/FFL/code/pablo/model/alt_model_wrapper.py : a modification of the file TSB-AD/model_wrapper.py in order to be able to track timing
      of the initialization, training and test phases of anomaly detection methods.
    - /vol/FFL/code/pablo/model/Method_Parameters.py: provide details on the parameters available in each method. For instance for the method
      autoencoder:
      'AutoEncoder':{
      'method':{
      'no-opt':[],
      'opt':{'slidingWindow':100,
      'hidden_neurons':None,
      'hidden_activation':'relu',
      'batch_norm':True,
      'learning_rate':1e-3,
      'epochs':100,
      'batch_size':32,
      'dropout_rate':0.2,
      'weight_decay':1e-5,# validation_size=0.1,

      'preprocessing':True,
      'loss_fn':None,
      'verbose':False,# random_state=None,

      'contamination':0.1,
      'device':None
      }
      },
      'expe':{
      'no-opt':[],
      'opt':{
      'window_size':100,
      'hidden_neurons':[64, 32],
      'n_jobs':1
      }
      }
      },
      The first part 'method' provides the parameters (no optional 'no-opt') or optional 'opt' for launching the base implementation of the method
      (the base implementation of the AutoEncoder method in the file old_model/AE.py). Currently you can not modify these parameters

    TODO: allow to modify these parameters

    The second part 'expe' are the parameters (optional or not) that can be modified when running the anomaly detection. For instance
    if you want to use a window size of 200 in the experiment, then you should indicate this parameter in the config.yaml file:

    method:
    name: AutoEncoder
    parameters:
    window_size: 200

    This will just modify the value of window_size (but you can modify hidden_neurons as well, or n_jobs..

    REMARK: I'm not sure that the code will not fail correctly if you include incorrect parameters, that is parameters not in the
    Method_Parameters.py file. I think I forgot to check the validity of the parameters

-II. How to run an experiment

The method that can be used are specified in the file /vol/FFL/code/pablo/model/alt_model_wrapper.py

Unsupervised = ['FFT', 'SR', 'NORMA', 'Series2Graph', 'Sub_IForest', 'IForest', 'LOF', 'Sub_LOF', 'POLY', 'MatrixProfile', 'Sub_PCA', 'PCA', 'HBOS',
'Sub_HBOS', 'KNN', 'Sub_KNN','KMeansAD', 'KMeansAD_U', 'KShapeAD', 'COPOD', 'CBLOF', 'COF', 'EIF', 'RobustPCA', 'Lag_Llama', 'TimesFM', 'Chronos', 'MOM
ENT_ZS']

Semisupervised = ['Left_STAMPi', 'SAND', 'MCD', 'Sub_MCD', 'OCSVM', 'Sub_OCSVM', 'AutoEncoder', 'CNN', 'LSTMAD', 'TranAD', 'USAD', 'OmniAnomaly',
'AnomalyTransformer', 'TimesNet', 'FITS', 'Donut', 'OFA', 'MOMENT_FT', 'M2N2']

-II.0 Building docker image

This command will build a docker image based on TSB-AD local repo. You can customize image tag (tsbad:0.0.3-cpu-pablo), but you have to remember to change it also in other scripts

pablo@nuc-celeron-6:/vol/FFL/code/pablo$ docker build -t tsbad:0.0.3-cpu-pablo -f docker/Dockerfile .

- image has unified shared storage with host machine, so on both sides (host and docker container) we can use /vol/FFL as our shared storage.
- checking presence of image

$ docker image ls

-II.1 Basic process with non interactive docker

First you have to be logged in to a computer that is not the management one (for instance nuc-celeron-1).

Modify the config.yaml file. For instance to run FFT with the file 564_YAHOO_id_14_Synthetic_tr_500_1st_658 with a RAM limit of 200m
a database toto.db without any modification of the experiment parameters, the config file reads

comment: "Just a test"

user: Tamara

host: generic

db:
	file: /vol/FFL/code/pablo/results/results_db.db
	name: expe

docker_image: tsbad:0.0.3-cpu-pablo

#docker_cpu_limit: "0.1"

##ram limit 200m for 200MB, 1g for 1GB etc..
docker_ram_limit: 200m

#docker_swap_limit: 500MB

#docker_time_limit: 1h


method:
	name: FFT
	#parameters:
	#	ifft_parameters:5
	#	local_neighbor_window:21
	#   local_outlier_threshold:0.6
 	#   max_region_size:50
	#   max_sign_change_distance:10

dataset:
	dir:     /vol/FFL/datasets/TSB-AD-U
	summary: /vol/FFL/code/pablo/Summary.csv
	#!! no csv at the end of the dataset name
	data: 001_NAB_id_1_Facility_tr_1007_1st_2014   

metrics:
	name: all
	parameters: ''


Recal that lines with # in front are not interpreted (they can be suppressed). The full block with FFT parameters can be suppressed.
If you want to modify ifft_parameters to 15 uncomment parameters, ifft_parameters and set the value 15 to ifft-parameters

REMARK:
- the sqlite3 database expe (name) is stored in the file /mnt/FFL/code/fred/docker/results/results_db.db (file)
- For the moment, do not modify the entries of the metrics. 

Now run

guyarfre@nuc-celeron-1:~$> ./make_expe --config config.yaml

This will launch docker, i.e. it runs

	docker run --rm -v /vol/FFL:/vol/FFL -m 200m tsbad:0.0.3-cpu-pablo python /vol/FFL/code/pablo/Unit_Pipeline.py --config /vol/FFL/code/pablo/config.yaml

This create the docker with the limitation of the ram, using the docker image 	tsbad:0.0.3-cpu-pablo. When the docker is created, 
the following is runned inside the docker

python /vol/FFL/code/pablo/Unit_Pipeline.py --config /mnt/FFL/code/pablo/config.yaml

Remark both Unit_Pipeline.py and config.yaml are indeed located on the share directory /vol/FFL/code/pablo/ mounting
/vol/FFL/code/pablo/Unit_Pipeline.py


The Unit_Pipeline, manage the launching of run_unit_method.py using the configuration file /vol/FFL/code/pablo/config.yaml,
capture the results of run_unit_method.py, save everything in the databases and leaves. Then the docker stop.
-II.2 Using the interactive docker

Launch the docker:

guyarfre@nuc-celeron-1:~$> docker run --rm -v /vol/FFL:/vol/FFL -m 200m -it tsbad:0.0.3-cpu-pablo bash

Here you have to include the ram limitation if you want it to be active.
Then you are running an interactive session in the docker:

root@4c462ceed669:/= /vol/FFL#

To run the experiment specified in the configuration file:

root@4c462ceed669:/= /vol/FFL# python /vol/FFL/code/pablo/Unit_Pipeline.py --config /vol/FFL/code/pablo/config.yaml

It should work!..

By default at the end of the process (for the interactive or non interactive case), you should see at the end the record that is
stored in the databases.

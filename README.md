HOWTO TSB-AD
F. Guyard, P.Piotrowski
Last update: 2025.09.30


I. General Structure
--------------------

When connected on the management platform or on other computers of the platform all codes are located in the shared volume /vol/FFL. 

		- /vol/FFL/datasets: directory containing the various datasets
		
		- /vol/FFL/datasets/TSB-AD-U: univariate timeseries provided by TSB-AD
		
		-/vol/FFL/code: repository for various code. You can create your own directory to store your code (or data) and access them from any computer of the platform.
		
		-/vol/FFL/code/V0.2: all the code to run the (modified) TSB-AD anomaly detection framework. Among the provided modifications, I add timing for the
                                    initialization of (python) anomaly detection method, for the training part (0.0 when the method is unsupervised) and for the 
									test on the dataset


II. Environment preparation
---------------------------

Ther are two types of runner of Unit Test: docker, systemd


					
-II. How to run an experiment

The method that can be used are specified in the file /vol/FFL/code/fred/docker/model/alt_model_wrapper.py


Unsupervised = ['FFT', 'SR', 'NORMA', 'Series2Graph', 'Sub_IForest', 'IForest', 'LOF', 'Sub_LOF', 'POLY', 'MatrixProfile', 'Sub_PCA', 'PCA', 'HBOS',
                        'Sub_HBOS', 'KNN', 'Sub_KNN','KMeansAD', 'KMeansAD_U', 'KShapeAD', 'COPOD', 'CBLOF', 'COF', 'EIF', 'RobustPCA', 'Lag_Llama', 'TimesFM', 'Chronos', 'MOM
ENT_ZS']

Semisupervised = ['Left_STAMPi', 'SAND', 'MCD', 'Sub_MCD', 'OCSVM', 'Sub_OCSVM', 'AutoEncoder', 'CNN', 'LSTMAD', 'TranAD', 'USAD', 'OmniAnomaly',
                        'AnomalyTransformer', 'TimesNet', 'FITS', 'Donut', 'OFA', 'MOMENT_FT', 'M2N2']
						
						
-II.1 Basic process with non interactive docker

	First you have to be logged in to a computer that is not the management one (for instance nuc-celeron-1).
	
	Modify the config.yaml file. For instance to run FFT with the file 564_YAHOO_id_14_Synthetic_tr_500_1st_658 with a RAM limit of 200m
	a database toto.db without any modification of the experiment parameters, the config file reads
	
	comment: "Just a test"

	user: Tamara

	host: generic

	db:
		file: /mnt/FFL/code/fred/docker/results/results_db.db
		name: expe

	docker_image: tsbad:0.0.2

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
		dir:     /mnt/FFL/datasets/TSB-AD-U
		summary: /mnt/FFL/code/fred/Summary.csv
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

		docker run -v /vol/FFL:/mnt/FFL -m 200m tsbad:0.0.2 python /mnt/FFL/code/fred/docker/Unit_Pipeline.py --config /mnt/FFL/code/fred/docker/config.yaml
		
	This create the docker with the limitation of the ram, using the docker image 	tsbad:0.0.2. When the docker is created, 
	the following is runned inside the docker
	
	python /mnt/FFL/code/fred/docker/Unit_Pipeline.py --config /mnt/FFL/code/fred/docker/config.yaml
	
	Remark both Unit_Pipeline.py and config.yaml are indeed located on the share directory /mnt/FFL/code/fred/docker/ mounting
	/vol/FFL/code/fred/docker/Unit_Pipeline.py
	
	
	The Unit_Pipeline, manage the launching of run_unit_method.py using the configuration file /mnt/FFL/code/fred/docker/config.yaml,
	capture the results of run_unit_method.py, save everything in the databases and leaves. Then the docker stop.
	
	
-II.2 Using the interactive docker

Launch the docker:

guyarfre@nuc-celeron-1:~$> docker run -v /vol/FFL:/mnt/FFL -m 200m -it tsbad:0.0.2 bash

Here you have to include the ram limitation if you want it to be active.
Then you are running an interactive session in the docker:

root@4c462ceed669:/= /home/guyarfre#

To run the experiment specified in the configuration file:

root@4c462ceed669:/= /home/guyarfre# python /mnt/FFL/code/fred/docker/Unit_Pipeline.py --config /mnt/FFL/code/fred/docker/config.yaml

It should work!..


By default at the end of the process (for the interactive or non interactive case), you should see at the end the record that is 
stored in the databases.


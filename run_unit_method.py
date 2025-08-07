import argparse
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import json
import yaml

from TSB_AD.evaluation.metrics import get_metrics
from local_utils.Logger import Logger
from model.alt_model_wrapper import run_Unsupervise_AD, run_Semisupervise_AD
from model.alt_model_wrapper import Unsupervised, Semisupervised

# Parsing dictionnary
class ParseKwargs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        for value in values:
            key, value = value.split(':')
            getattr(namespace, self.dest)[key] = value

def read_config(config_file):

        try:
            with open(config_file,"r") as file:
                config = yaml.safe_load(file)
        except:
            raise Exception("Impossible to read {} file".format(config_file))

		
        if config.get('method','') == '':
            raise Exception("Missing method in configuration file")

        temp = config.get('method','')

        method = temp['name']
        method_parameters = {}
        params = temp.get('parameters',{})
        for k in params.keys():
            method_parameters[k] = params[k]

        temp = config['dataset']
        if temp == '':
            raise Exception("No dataset in configuration file")

        datadir = temp['dir']
        dataset_name    = temp['data']

        metrics = 'all'
        metrics_parameters = {}
        
        arguments = {
            'datadir': datadir,
            'dataset_name': dataset_name,
            'method': method,
            'method_parameters': method_parameters,
            'metrics': metrics,
            'metrics_parameters': metrics_parameters
        }
        return(arguments)

def run_method(method,train_data=None,test_data=None,labels=None,reduced_labels=None,**method_parameters):
    logger = Logger()
    logger.log('method',method)
    if method in Unsupervised:
        try:
            result = run_Unsupervise_AD(method,data,**method_parameters)
            score = MinMaxScaler(feature_range=(0,1)).fit_transform(result['score'].reshape(-1,1)).ravel()
            init_duration     = result['init']
            training_duration = result['train']
            test_duration     = result['test']
            status            = result['status']
            perf = get_metrics(result['score'],labels)
            score = score.tolist()
        except:
            score             = []
            init_duration     = float('NaN')
            training_duration = float('NaN')
            test_duration     = float('NaN')
            status            = 'failed'
            perf = {}
    else:  
        try:
            result = run_Semisupervise_AD(method, train_data, test_data,**method_parameters)
            score = MinMaxScaler(feature_range=(0,1)).fit_transform(result['score'].reshape(-1,1)).ravel()
            init_duration     = result['init']
            training_duration = result['train']
            test_duration     = result['test']
            status            = result['status']
            perf = get_metrics(result['score'],reduced_labels)
            score = score.tolist()
        except:
            score             = []
            init_duration     = float('NaN')
            training_duration = float('NaN')
            test_duration     = float('NaN')
            status            = 'failed'
            perf = {}
    logger.log('score',score)
    logger.log('init',init_duration)
    logger.log('training',training_duration)
    logger.log('test',test_duration)
    logger.log('performance',perf)
    logger.log('status',status)
    return(logger._logs)

if __name__ == '__main__':
    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    parser.add_argument('--config',type=str,default=None)
    args = parser.parse_args()

    #print("\n#############################")
    #print("ARGS: {}".format(args))
    #print("#############################\n")

    configuration = read_config(args.config)


    df = pd.read_csv("{}/{}.csv".format(configuration['datadir'],
                                        configuration['dataset_name'],sep=","))

    data = df.iloc[:, 0:-1].values.astype(float)
    
    labels = df['Label'].astype(int).to_numpy()
    train_index = int(configuration['dataset_name'].split("_")[6])
    train_data = data[0:train_index]
    test_data  = data[train_index:-1]
    reduced_labels = labels[train_index:-1]
    logs = run_method(configuration['method'],
                      train_data=train_data,
                      test_data=test_data,
                      labels=labels,
                      reduced_labels=reduced_labels,
                      **configuration['method_parameters'])
    
    with open("/mnt/FFL/code/fred/docker/trash/Temp_Out.json",'w') as f:
        json.dump(logs,f, ensure_ascii=False)

    print(json.dumps(logs))
        

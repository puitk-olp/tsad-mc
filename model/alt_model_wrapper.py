import numpy as np
import math
from TSB_AD.utils.slidingWindows import find_length_rank
from local_utils.Timer import Timer
from local_utils.Logger import Logger


Unsupervised = ['FFT', 'SR', 'NORMA', 'Series2Graph', 'Sub_IForest', 'IForest', 'LOF', 'Sub_LOF', 'POLY', 'MatrixProfile', 'Sub_PCA', 'PCA', 'HBOS', 
                        'Sub_HBOS', 'KNN', 'Sub_KNN','KMeansAD', 'KMeansAD_U', 'KShapeAD', 'COPOD', 'CBLOF', 'COF', 'EIF', 'RobustPCA', 'Lag_Llama', 'TimesFM', 'Chronos', 'MOMENT_ZS']

Semisupervised = ['Left_STAMPi', 'SAND', 'MCD', 'Sub_MCD', 'OCSVM', 'Sub_OCSVM', 'AutoEncoder', 'CNN', 'LSTMAD', 'TranAD', 'USAD', 'OmniAnomaly', 
                        'AnomalyTransformer', 'TimesNet', 'FITS', 'Donut', 'OFA', 'MOMENT_FT', 'M2N2']


Metrics = ['AUC-PR','AUC-ROC','VUS-PR','VUS-ROC','Standard-F1','PA-F1','Event-based-F1','R-based-F1','Affiliation-F']
Empty_Perf = {'AUC-PR':None,
              'AUC-ROC':None,
              'VUS-PR':None,
              'VUS-ROC':None,
              'Standard-F1': None,
              'PA-F1': None,
              'Event-based-F1': None,
              'R-based-F1': None,
              'Affiliation-F':None}
Unsupervise_AD_Pool = ['FFT', 'SR', 'NORMA', 'Series2Graph', 'Sub_IForest', 'IForest', 'LOF', 'Sub_LOF', 'POLY', 'MatrixProfile', 'Sub_PCA', 'PCA', 'HBOS', 
                        'Sub_HBOS', 'KNN', 'Sub_KNN','KMeansAD', 'KMeansAD_U', 'KShapeAD', 'COPOD', 'CBLOF', 'COF', 'EIF', 'RobustPCA', 'Lag_Llama', 'TimesFM', 'Chronos', 'MOMENT_ZS']
Semisupervise_AD_Pool = ['Left_STAMPi', 'SAND', 'MCD', 'Sub_MCD', 'OCSVM', 'Sub_OCSVM', 'AutoEncoder', 'CNN', 'LSTMAD', 'TranAD', 'USAD', 'OmniAnomaly', 
                        'AnomalyTransformer', 'TimesNet', 'FITS', 'Donut', 'OFA', 'MOMENT_FT', 'M2N2']

def run_Unsupervise_AD(model_name, data,**kwargs):
    
    # Reinitialize the timers
    Timer.timers = {}

    status = 'failed'
    INIT_FAILED = False
    TEST_FAILED = False
    score  = {}

    init_function_name = f'run_{model_name}_init'
    init_function_to_call = globals()[init_function_name]
    eval_function_name = f'run_{model_name}_eval'
    eval_function_to_call = globals()[eval_function_name]
    
    # Initialization
    try:
        with Timer("init"):
            clf = init_function_to_call(data, **kwargs)
    except KeyError:
        error_message = f"Model function '{model_name}' is not defined."
        print(error_message)
        return error_message
    except Exception as e:
        INIT_FAILED = True
        TEST_FAILED = True

    
    # Test
 
    try:
        with Timer("test"):
            score = eval_function_to_call(clf,data)
        status = 'success'
        
    except Exception as e:
        TEST_FAILED = True

    result = {'init'  : Timer.timers.get('init',float('NaN')),
                'train' : Timer.timers.get('train',0.0),
                'test'  : Timer.timers.get('test',float('NaN')),
                'score' : score,
                'status':status}
    
    if INIT_FAILED:
        result['init'] = float('NaN')
    if TEST_FAILED:
        result['test'] = float('NaN')
    
    return(result)

def run_Semisupervise_AD(model_name, data_train, data_test,**kwargs):

    # Reinitialize the timers
    Timer.timers = {}

    status       = 'success'
    INIT_FAILED  = False
    TRAIN_FAILED = False
    TEST_FAILED  = False
    score  = {}

    init_function_name = f'run_{model_name}_init'
    init_function_to_call = globals()[init_function_name]
    train_function_name = f'run_{model_name}_train'
    train_function_to_call = globals()[train_function_name]
    eval_function_name = f'run_{model_name}_eval'
    eval_function_to_call = globals()[eval_function_name]

    # Initialization
    try:
        with Timer("init"):
            clf = init_function_to_call(data_train, data_test,**kwargs)
    except KeyError:
        error_message = f"Model function '{model_name}' is not defined."
        print(error_message)
        return error_message
    except Exception as e:
        INIT_FAILED     = True
        TRAIN_FAILED = True
        TEST_FAILED     = True
        status = 'failed'

    # Training
    try:
        with Timer("train"):
            clf = train_function_to_call(clf, data_train, data_test)
    except Exception as e:
        TRAIN_FAILED = True
        TEST_FAILED     = True
        status = 'failed'
    
    # Test
    try:
        with Timer("test"):
            score = eval_function_to_call(clf, data_train, data_test)
    except Exception as e:
        TEST_FAILED = True
        status = 'failed'
    
    # results formating
    result = {'init'  : Timer.timers.get('init',float('NaN')),
              'train' : Timer.timers.get('train',float('NaN')),
              'test'  : Timer.timers.get('test',float('NaN')),
              'score' : score,
              'status': status}

    if INIT_FAILED:
        result['init'] = float('NaN')
    if TRAIN_FAILED:
        result['train'] = float('NaN')
    if TEST_FAILED:
        result['test'] = float('NaN')
    
    return(result)

## FFT

def run_FFT_init(data,**parameters): 
    from TSB_AD.models.FFT import FFT
    ifft_parameters               = int(parameters.get('ifft_parameters',5))
    local_neighbor_window         = int(parameters.get('local_neighbor_window',21))
    local_outlier_threshold       = float(parameters.get('local_outlier_threshold',0.6))
    max_region_size               = int(parameters.get('max_region_size',50))
    max_sign_change_distance      = int(parameters.get('max_sign_change_distance',10))
     
    clf = FFT(ifft_parameters=ifft_parameters, local_neighbor_window=local_neighbor_window, local_outlier_threshold=local_outlier_threshold, max_region_size=max_region_size, max_sign_change_distance=max_sign_change_distance)
    return(clf)

def run_FFT_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## Sub_IForest


def run_Sub_IForest_init(data, **parameters):
    from TSB_AD.models.IForest import IForest
    periodicity     = int(parameters.get('periodicity',1))
    n_estimators    = int(parameters.get('n_estimators',100)) 
    max_features    = int(parameters.get('max_features',1))
    n_jobs          = int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = IForest(slidingWindow=slidingWindow, n_estimators=n_estimators, max_features=max_features, n_jobs=n_jobs)
    return clf

def run_Sub_IForest_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## IForest

def run_IForest_init(data, **parameters):
    from TSB_AD.models.IForest import IForest
    slidingWindow  =  int(parameters.get('slidingWindow',100))
    n_estimators   =  int(parameters.get('n_estimators',100)) 
    max_features   =  int(parameters.get('max_features',1)) 
    n_jobs         =  int(parameters.get('n_jobs',1)) 
    clf = IForest(slidingWindow=slidingWindow, n_estimators=n_estimators, max_features=max_features, n_jobs=n_jobs)
    return clf

def run_IForest_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## Sub_LOF

def run_Sub_LOF_init(data, **parameters):
    from TSB_AD.models.LOF import LOF
    periodicity    =  int(parameters.get('periodicity',1))
    n_neighbors    =  int(parameters.get('n_neighbors',30)) 
    metric         =  int(parameters.get('metric','minkowski')) 
    n_jobs         =  int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = LOF(slidingWindow=slidingWindow, n_neighbors=n_neighbors, metric=metric, n_jobs=n_jobs)
    return clf

def run_Sub_LOF_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## LOF

def run_LOF_init(data, **parameters):
    from TSB_AD.models.LOF import LOF
    slidingWindow    =  int(parameters.get('slidingWindow',1))
    n_neighbors      =  int(parameters.get('n_neighbors',30)) 
    metric           =  str(parameters.get('metric','minkowski')) 
    n_jobs           =  int(parameters.get('n_jobs',1))


    clf = LOF(slidingWindow=slidingWindow, n_neighbors=n_neighbors, metric=metric, n_jobs=n_jobs)
    return clf

def run_LOF_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

##POLY

def run_POLY_init(data, **parameters):
    from TSB_AD.models.POLY import POLY
    periodicity  = int(parameters.get('periodicity',1))
    power        = int(parameters.get('power',3))
    n_jobs       = int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = POLY(power=power, window = slidingWindow)
    return clf

def run_POLY_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## MatrixProfile

def run_MatrixProfile_init(data, **parameters):
    from TSB_AD.models.MatrixProfile import MatrixProfile
    periodicity  = int(parameters.get('periodicity',1))
    n_jobs       = int(parameters.get('n_jobs',1))


    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = MatrixProfile(window=slidingWindow)
    return clf

def run_MatrixProfile_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## Left_STAMPi

def run_Left_STAMPi_init(data_train, data_test,**parameters):
    from TSB_AD.models.Left_STAMPi import Left_STAMPi
    window_size = int(parameters.get('window_size',100))
    clf = Left_STAMPi(n_init_train=len(data_train), window_size=window_size)
    return(clf)

def run_Left_STAMPi_train(clf,data_train, data_test):
    clf.fit(data_test)
    return(clf)
    
def run_Left_STAMPi_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## SAND

def run_SAND_init(data_train, data_test, **parameters):
    from TSB_AD.models.SAND import SAND 
    periodicity  = int(parameters.get('periodicity',1))

    slidingWindow = find_length_rank(data_test, rank=periodicity)
    clf = SAND(pattern_length=slidingWindow, subsequence_length=4*(slidingWindow))
    return {'model':clf,'window':slidingWindow}
    
def run_SAND_train(clf,data_train, data_test):
    clf['model'].fit(data_test.squeeze(), online=True, overlaping_rate=int(1.5*clf['window']), init_length=len(data_train), alpha=0.5, batch_size=max(5*clf['window'], int(0.1*len(data_test))))
    return(clf['model'])

def run_SAND_eval(clf,data_train, data_test):
    return clf.decision_scores_.ravel()

## KShapeAD

def run_KShapeAD_init(data, **parameters):
    from TSB_AD.models.SAND import SAND
    periodicity  =int(parameters.get('periodicity',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = SAND(pattern_length=slidingWindow, subsequence_length=4*(slidingWindow))
    return {'model':clf,'window':slidingWindow}

def run_KShapeAD_eval(clf,data):
    clf['model'].fit(data.squeeze(), overlaping_rate=int(1.5*clf['window']))
    return(clf['model'].decision_scores_.ravel())

## Series2Graph

def run_Series2Graph_init(data, **parameters):
    from TSB_AD.models.Series2Graph import Series2Graph
    periodicity  = int(parameters.get('periodicity',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    data = data.squeeze()
    s2g = Series2Graph(pattern_length=slidingWindow)
    clf={'model':s2g,'window':slidingWindow}
    return(clf)


def run_Series2Graph_eval(clf,data):
    clf['model'].fit(data)
    query_length = 2*clf['window']
    clf['model'].score(query_length=query_length,dataset=data)
    score = clf['model'].decision_scores_
    score = np.array([score[0]]*math.ceil(query_length//2) + list(score) + [score[-1]]*(query_length//2))
    return score.ravel()

## Sub_PCA

def run_Sub_PCA_init(data, **parameters):
    from TSB_AD.models.PCA import PCA
    periodicity  = int(parameters.get('periodicity',1))
    n_components = int(parameters.get('n_components',-1))
    if n_components == -1:
        n_components = None
    n_jobs       = int(parameters.get('n_job',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = PCA(slidingWindow = slidingWindow, n_components=n_components)
    return(clf)

def run_Sub_PCA_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## PCA

def run_PCA_init(data, **parameters):
    from TSB_AD.models.PCA import PCA
    slidingWindow  = int(parameters.get('slidingWindow',100))
    n_components   = int(parameters.get('n_components',-1))
    if n_components == -1:
        n_components = None
    n_jobs         = int(parameters.get('n_job',1))

    clf = PCA(slidingWindow = slidingWindow, n_components=n_components)
    return(clf)

def run_PCA_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## NORMA

def run_NORMA_init(data, **parameters):
    from TSB_AD.models.NormA import NORMA
    periodicity   = int(parameters.get('periodicity',1))
    clustering    = str(parameters.get('clustering','hierarchical'))
    n_jobs        = int(parameters.get('n_jobs',1))
    
    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = NORMA(pattern_length=slidingWindow, nm_size=3*slidingWindow, clustering=clustering)
    return({'model':clf,'window':slidingWindow})
    
def run_NORMA_eval(clf,data):
    clf['model'].fit(data)
    score = clf['model'].decision_scores_
    score = np.array([score[0]]*math.ceil((clf['window']-1)/2) + list(score) + [score[-1]]*((clf['window']-1)//2))
    if len(score) > len(data):
        start = len(score) - len(data)
        score = score[start:]
    return score.ravel()

## Sub_HBOS

def run_Sub_HBOS_init(data, **parameters):
    from TSB_AD.models.HBOS import HBOS
    periodicity  = int(parameters.get('periodicity',1))
    n_bins       = int(parameters.get('n_bins',10))
    tol          = float(parameters.get('tol',0.5))
    n_jobs       = int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = HBOS(slidingWindow=slidingWindow, n_bins=n_bins, tol=tol)
    return(clf)

def run_Sub_HBOS_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## HBOS

def run_HBOS_init(data, **parameters):
    from TSB_AD.models.HBOS import HBOS
    slidingWindow  = int(parameters.get('slidingWindow',1))
    n_bins         = int(parameters.get('n_bins',10))
    tol            = int(parameters.get('tol',0.5))
    n_jobs         = int(parameters.get('n_jobs',1))

    clf = HBOS(slidingWindow=slidingWindow, n_bins=n_bins, tol=tol)
    return(clf)

def run_HBOS_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())


## Sub_OCSVM

def run_Sub_OCSVM_init(data_train, data_test, **parameters):
    from TSB_AD.models.OCSVM import OCSVM
    kernel      =   str(parameters.get('kernel','rbf'))
    nu          =   float(parameters.get('nu',0.5))
    periodicity =   int(parameters.get('periodicity',1))
    n_jobs      =   int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data_test, rank=periodicity)
    clf = OCSVM(slidingWindow=slidingWindow, kernel=kernel, nu=nu)
    return(clf)
    
def run_Sub_OCSVM_train(clf,data_train, data_test):
    clf.fit(data_train)
    return(clf)

def run_Sub_OCSVM_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## OCSVM

def run_OCSVM_init(data_train, data_test, **parameters):
    from TSB_AD.models.OCSVM import OCSVM
    kernel        =   str(parameters.get('kernel','rbf'))
    nu            =   float(parameters.get('nu',0.5))
    slidingWindow =   int(parameters.get('slidingWindow',1))
    n_jobs        =   int(parameters.get('n_jobs',1))

    clf = OCSVM(slidingWindow=slidingWindow, kernel=kernel, nu=nu)
    return(clf)

def run_OCSVM_train(clf,data_train, data_test):
    clf.fit(data_train)
    return(clf)

def run_OCSVM_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

 
## Sub_MCD

def run_Sub_MCD_init(data_train, data_test, **parameters):
    from TSB_AD.models.MCD import MCD
    support_fraction  = float(parameters.get('support_fraction',-1))
    if support_fraction == -1:
        support_function = None
    periodicity       =  int(parameters.get('periodicity',1))
    n_jobs            =  int(parameters.get('n_jobs',1))
  

    slidingWindow = find_length_rank(data_test, rank=periodicity)
    clf = MCD(slidingWindow=slidingWindow, support_fraction=support_fraction)
    return(clf)

def run_Sub_MCD_train(clf,data_train, data_test):
    clf.fit(data_train)
    return(clf)

def run_Sub_MCD_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## Sub_MCD

def run_MCD_init(data_train, data_test, **parameters):
    from TSB_AD.models.MCD import MCD
    support_fraction  =  float(parameters.get('support_fraction',-1))
    if support_fraction == -1:
        support_function = None
    slidingWindow     =  int(parameters.get('slidingWindow',10))
    n_jobs            =  int(parameters.get('n_jobs',1))

    clf = MCD(slidingWindow=slidingWindow, support_fraction=support_fraction)
    return(clf)
    
def run_MCD_train(clf,data_train, data_test):
    clf.fit(data_train)
    return(clf)

def run_MCD_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## Sub_KNN

def run_Sub_KNN_init(data,**parameters):
    from TSB_AD.models.KNN import KNN
    n_neighbors  = int(parameters.get('n_neighbors',10))
    method       = str(parameters.get('method','largest'))
    periodicity  = int(parameters.get('periodicity',1))
    n_jobs       = int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = KNN(slidingWindow=slidingWindow, n_neighbors=n_neighbors,method=method, n_jobs=n_jobs)
    return(clf)

def run_Sub_KNN_eval(clf,data):
    from TSB_AD.models.KNN import KNN
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## KNN 

def run_KNN_init(data, **parameters):
    from TSB_AD.models.KNN import KNN
    slidingWindow  = int(parameters.get('slidingWindow',1))
    n_neighbors    = int(parameters.get('n_neighbors',10))
    method         = str(parameters.get('method','largest'))
    n_jobs         = int(parameters.get('n_jobs',1))

    clf = KNN(slidingWindow=slidingWindow, n_neighbors=n_neighbors, method=method, n_jobs=n_jobs)
    return(clf)

def run_KNN_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## KMeansAD

def run_KMeansAD_init(data, **parameters):
    from TSB_AD.models.KMeansAD import KMeansAD
    n_clusters     = int(parameters.get('n_clusters',20))
    window_size    = int(parameters.get('window_size',20))
    n_jobs         = int(parameters.get('n_jobs',1))

    clf = KMeansAD(k=n_clusters, window_size=window_size, stride=1, n_jobs=n_jobs)
    return(clf)

def run_KMeansAD_eval(clf,data):
    return(clf.fit_predict(data).ravel())

## KMeansAD_U

def run_KMeansAD_U_init(data, **parameters):
    from TSB_AD.models.KMeansAD import KMeansAD
    n_clusters  = int(parameters.get('n_clusters',20))
    periodicity = int(parameters.get('periodicity',1))
    n_jobs      = int(parameters.get('n_jobs',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    clf = KMeansAD(k=n_clusters, window_size=slidingWindow, stride=1, n_jobs=n_jobs)
    return(clf)

def run_KMeansAD_U_eval(clf,data):
    return(clf.fit_predict(data).ravel())

## COPOD
def run_COPOD_init(data, **parameters):
    from TSB_AD.models.COPOD import COPOD
    n_jobs      = int(parameters.get('n_jobs',1))

    clf = COPOD(n_jobs=n_jobs)
    return(clf)

def run_COPOD_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())


## CBLOF
def run_CBLOF_init(data, **parameters):
    from TSB_AD.models.CBLOF import CBLOF
    n_clusters  = int(parameters.get('n_clusters',8))
    alpha       = float(parameters.get('alpha',0.9))
    n_jobs      = int(parameters.get('n_jobs',1))

    clf = CBLOF(n_clusters=n_clusters, alpha=alpha, n_jobs=n_jobs)
    return(clf)

def run_CBLOF_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## COF
def run_COF_init(data, **parameters):
    from TSB_AD.models.COF import COF
    n_neighbors  = int(parameters.get('n_neighbors',30))

    clf = COF(n_neighbors=n_neighbors)
    return(clf)

def run_COF_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## EIF
def run_EIF_init(data, **parameters):
    from TSB_AD.models.EIF import EIF
    n_trees = int(parameters.get('n_trees',100))

    clf = EIF(n_trees=n_trees)
    return(clf)

def run_EIF_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## RobustPCA
def run_RobustPCA_init(data, **parameters):
    from TSB_AD.models.RobustPCA import RobustPCA
    max_iter = int(parameters.get('max_iter',1000))

    clf = RobustPCA(max_iter=max_iter)
    return(clf)

def run_RobustPCA_eval(clf,data):
    clf.fit(data)
    return(clf.decision_scores_.ravel())

## SR
def run_SR_init(data, **parameters): 
    from TSB_AD.models.SR import SR
    periodicity = int(parameters.get('periodicity',1))

    slidingWindow = find_length_rank(data, rank=periodicity)
    return({'window':slidingWindow})

def run_SR_eval(clf,data):
    from TSB_AD.models.SR import SR
    return(SR(data,window_size=clf['window']).ravel())

## AutoEncoder
def run_AutoEncoder_init(data_train, data_test, **parameters):
    from TSB_AD.models.AE import AutoEncoder
    window_size      = int(parameters.get('window_size',100))
    hidden_neurons   = parameters.get('hidden_neurons',[64, 32])
    n_jobs           = int(parameters.get('n_jobs',1))

    clf = AutoEncoder(slidingWindow=window_size, hidden_neurons=hidden_neurons, batch_size=128, epochs=50)
    return(clf)
    
def run_AutoEncoder_train(clf,data_train, data_test):
    clf.fit(data_train)
    return(clf)

def run_AutoEncoder_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()
    

## CNN
def run_CNN_init(data_train, data_test, **parameters):
    from TSB_AD.models.CNN import CNN
    window_size = int(parameters.get('window_size',100))
    num_channel = parameters.get('num_channel',[32, 32, 40])
    lr          = float(parameters.get('lr',0.0008))
    n_jobs      = int(parameters.get('n_jobs',1))

    clf = CNN(window_size=window_size, num_channel=num_channel, feats=data_test.shape[1], lr=lr, batch_size=128)
    return(clf)

def run_CNN_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_CNN_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()
    
## LSTMAD
def run_LSTMAD_init(data_train, data_test, **parameters):
    from TSB_AD.models.LSTMAD import LSTMAD
    window_size = int(parameters.get('window_size',100))
    lr          = float(parameters.get('lr', 0.0008))
    clf = LSTMAD(window_size=window_size, pred_len=1, lr=lr, feats=data_test.shape[1], batch_size=128)
    return clf

def run_LSTMAD_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_LSTMAD_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## TranAD
def run_TranAD_init(data_train, data_test, **parameters):
    from TSB_AD.models.TranAD import TranAD
    win_size = int(parameters.get('win_size',10))
    lr       = float(parameters.get('lr',1e-3))

    clf = TranAD(win_size=win_size, feats=data_test.shape[1], lr=lr)
    return(clf)

def run_TranAD_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_TranAD_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## AnomalyTransformer
def run_AnomalyTransformer_init(data_train, data_test, **parameters):
    from TSB_AD.models.AnomalyTransformer import AnomalyTransformer
    win_size   = int(parameters.get('win_size',100))
    lr         = float(parameters.get('lr',1e-4))
    batch_size = int(parameters.get('batch_size',128))
    clf = AnomalyTransformer(win_size=win_size, input_c=data_test.shape[1], lr=lr, batch_size=batch_size)
    return clf
 
def run_AnomalyTransformer_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_AnomalyTransformer_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## OmniAnomaly
def run_OmniAnomaly_init(data_train, data_test, **parameters):
    from TSB_AD.models.OmniAnomaly import OmniAnomaly
    win_size  = int(parameters.get('win_size',100))
    lr        = float(parameters.get('lr',0.002))

    clf = OmniAnomaly(win_size=win_size, feats=data_test.shape[1], lr=lr)
    return clf

def run_OmniAnomaly_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_OmniAnomaly_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()


## USAD
def run_USAD_init(data_train, data_test, **parameters):
    from TSB_AD.models.USAD import USAD
    win_size  = int(parameters.get('win_size',5))
    lr        = float(parameters.get('lr',1e-4))

    clf = USAD(win_size=win_size, feats=data_test.shape[1], lr=lr)
    return clf
    
def run_USAD_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_USAD_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## Donut
def run_Donut_init(data_train, data_test, **parameters):
    from TSB_AD.models.Donut import Donut
    win_size  =  int(parameters.get('win_size',120))
    lr        =  float(parameters.get('lr',1e-4))
    batch_size=  int(parameters.get('batch_size',128))
    

    clf = Donut(win_size=win_size, input_c=data_test.shape[1], lr=lr, batch_size=batch_size)
    return clf
      
def run_Donut_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_Donut_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()
  
    
## TimeNet
def run_TimesNet_init(data_train, data_test, **parameters):
    from TSB_AD.models.TimesNet import TimesNet
    win_size  =  int(parameters.get('win_size',96))
    lr        =  float(parameters.get('lr',1e-4))

    clf = TimesNet(win_size=win_size, enc_in=data_test.shape[1], lr=lr, epochs=50)
    return clf

def run_TimesNet_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_TimesNet_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()
  

## FITS
def run_FITS_init(data_train, data_test, **parameters):
    from TSB_AD.models.FITS import FITS
    win_size  =  int(parameters.get('win_size',100))
    lr        =  float(parameters.get('lr',1e-3))

    clf = FITS(win_size=win_size, input_c=data_test.shape[1], lr=lr, batch_size=128)
    return clf

def run_FITS_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_FITS_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## OFA
def run_OFA_init(data_train, data_test, **parameters):
    from TSB_AD.models.OFA import OFA
    win_size          =  int(parameters.get('win_size',100))
    batch_size        =  int(parameters.get('batch_size',64))

    clf = OFA(win_size=win_size, enc_in=data_test.shape[1], epochs=10, batch_size=batch_size)
    return clf

def run_OFA_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_OFA_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## Lag_Llama
def run_Lag_Llama_init(data, **parameters):
    from TSB_AD.models.Lag_Llama import Lag_Llama
    win_size          =  int(parameters.get('win_size',96))
    batch_size        =  int(parameters.get('lr',64))

    clf = Lag_Llama(win_size=win_size, input_c=data.shape[1], batch_size=batch_size)
    
def run_Lag_Llama_eval(clf,data):
    clf.fit(data)
    return clf.decision_scores_.ravel()

## Chronos
def run_Chronos_init(data, **parameters):
    from TSB_AD.models.Chronos import Chronos
    win_size          =  int(parameters.get('win_size',50))
    batch_size        =  int(parameters.get('lr',64))


    clf = Chronos(win_size=win_size, prediction_length=1, input_c=data.shape[1], model_size='base', batch_size=batch_size)
    return(clf)

def run_Chronos_eval(clf,data):
    clf.fit(data)
    return clf.decision_scores_.ravel()

## TimesFM
def run_TimesFM_init(data, **parameters):
    from TSB_AD.models.TimesFM import TimesFM
    win_size          =  int(parameters.get('win_size',96))

    clf = TimesFM(win_size=win_size)
    return(clf)

def run_TimesFM_eval(clf,data):
    clf.fit(data)
    return clf.decision_scores_.ravel()

## MOMENT_ZS
def run_MOMENT_ZS_init(data, **parameters):
    from TSB_AD.models.MOMENT import MOMENT 
    win_size          =  int(parameters.get('win_size',256))
    
    clf = MOMENT(win_size=win_size, input_c=data.shape[1])
    return(clf)

def run_MOMENT_ZS_eval(clf, win_size=256):
    # Zero shot
    clf.zero_shot(data)
    return clf.decision_scores_.ravel()

## MOMENT_FT
def run_MOMENT_FT_init(data_train, data_test, **parameters):
    from TSB_AD.models.MOMENT import MOMENT
    win_size          =  int(parameters.get('win_size',256))
    clf = MOMENT(win_size=win_size, input_c=data_test.shape[1])
    return clf


def run_MOMENT_FT_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_MOMENT_FT_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

## M2N2
def run_M2N2_init(data_train, data_test, **parameters):
    from TSB_AD.models.M2N2 import M2N2
    win_size     =  int(parameters.get('win_size',12))
    stride       =  int(parameters.get('stride',12))
    batch_size   =  int(parameters.get('batch_size',64))
    epochs       =  int(parameters.get('epochs',100))
    latent_dim   =  int(parameters.get('latent_dim',16))
    lr           =  float(parameters.get('lr',1e-3))
    ttlr         =  float(parameters.get('ttlr',1e-3))
    normalization=  str(parameters.get('normalization','Detrend'))
    gamma        =  float(parameters.get('gamma',0.99))
    th           =  float(parameters.get('th',0.9))
    valid_size   =  float(parameters.get('valid_size',0.2))
    infer_mode   =  str(parameters.get('infer_mode','online'))

    clf = M2N2(
            win_size=win_size, stride=stride,
            num_channels=data_test.shape[1],
            batch_size=batch_size, epochs=epochs,
            latent_dim=latent_dim,
            lr=lr, ttlr=ttlr,
            normalization=normalization,
            gamma=gamma, th=th, valid_size=valid_size,
            infer_mode=infer_mode
    )
    return clf

def run_M2N2_train(clf,data_train, data_test):
    clf.fit(data_train)
    return clf

def run_M2N2_eval(clf,data_train, data_test):
    return clf.decision_function(data_test).ravel()

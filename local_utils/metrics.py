from TSB_AD.evaluation.basic_metrics import basic_metricor, generate_curve

def get_metrics(score, labels, metrics_name_list, slidingWindow=100, pred=None, version='opt', thre=250):
    metrics = {}

    # PABLO: we filter metrics to be computed by a list

    '''
    Threshold Independent
    '''
    grader = basic_metricor()
    # AUC_ROC, Precision, Recall, PointF1, PointF1PA, Rrecall, ExistenceReward, OverlapReward, Rprecision, RF, Precision_at_k = grader.metric_new(labels, score, pred, plot_ROC=False)
    if 'AUC-PR' in metrics_name_list:
        metrics['AUC-PR'] = grader.metric_PR(labels, score)
    if 'AUC-ROC' in metrics_name_list:
        metrics['AUC-ROC'] = grader.metric_ROC(labels, score) 

    '''
    Threshold Dependent
    if pred is None --> use the oracle threshold
    '''
    if 'Standard-F1' in metrics_name_list:
        metrics['Standard-F1'] = grader.metric_PointF1(labels, score, preds=pred)
    if 'PA-F1' in metrics_name_list:
        metrics['PA-F1'] = grader.metric_PointF1PA(labels, score, preds=pred)
    if 'Event-based-F1' in metrics_name_list:
        metrics['Event-based-F1'] = grader.metric_EventF1PA(labels, score, preds=pred)
    if 'R-based-F1' in metrics_name_list:
        metrics['R-based-F1'] = grader.metric_RF1(labels, score, preds=pred)
    if 'Affiliation-F' in metrics_name_list:
        metrics['Affiliation-F'] = grader.metric_Affiliation(labels, score, preds=pred)

    '''
    Threshold Independent
    '''
    if 'VUS-PR' in metrics_name_list or 'VUS-ROC' in metrics_name_list:
        # R_AUC_ROC, R_AUC_PR, _, _, _ = grader.RangeAUC(labels=labels, score=score, window=slidingWindow, plot_ROC=True)
        _, _, _, _, _, _,VUS_ROC, VUS_PR = generate_curve(labels.astype(int), score, slidingWindow, version, thre)
        if 'VUS-PR' in metrics_name_list:
            metrics['VUS-PR'] = VUS_PR
        if 'VUS-ROC' in metrics_name_list:
            metrics['VUS-ROC'] = VUS_ROC

    return metrics
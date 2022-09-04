# -*- coding: utf-8 -*-
# @author: 丛戎
# @target: 预测模型，基于stl和arima预测算法

import time
import datetime

import json
import pandas as pd
import numpy as np

from ai_lib.time_series_prediction.algorithm.preprocess.tfPeriodCode.generalPeriodicity import GeneralPeriodicityDetector
from ai_lib.time_series_prediction.algorithm.preprocess.simpleRobustSTL.generalSTL import GeneralDecompEstimator
from ai_lib.time_series_prediction.algorithm.preprocess.data_preprocess_utils import DataPreprocessUtils
from sklearn.base import BaseEstimator


class TdataRobustPredModel(BaseEstimator):
    """
    调用达摩院自研预测算法，非周期部分运用分位数进行预测，超过一天同时不满足三天的数据也直接运用分位数进行预测
    """

    def __init__(self, period=1440, interval=60, colname='kpi', interval_sigma=2,
                 acf_peak_th=0.15, refine_tolerance=0.05, quantile=0.75, params=None, user_config=None,
                 forecast_horizon=0,
                 metric_id=None, ad_train_id=None):
        """
        Called when initializing the classifier
        """
        self.period = period
        self.interval = interval
        self.colname = colname
        self.interval_sigma = interval_sigma
        self.acf_peak_th = acf_peak_th
        self.refine_tolerance = refine_tolerance
        self.quantile = quantile
        self.forecast_horizon = forecast_horizon
        self.params = params
        self.user_config = user_config
        self.forecast_horizon = forecast_horizon
        self.metric_id = metric_id
        self.ad_train_id = ad_train_id
        self.training_end_ts_str = ''
        self.damo_input = ''
        self.damo_output = ''

    def _quantile_forecast(self, kpidata_train, quantile=0.75,
                           kpi_col='kpi', interval_sigma=2):
        """
        使用的数据不超过3天，利用分位数进行预测，同时计算上下界
        :param kpidata_train:
        :param quantile:
        :param kpi_col:
        :param split_hour:
        :return:
        """
        # 若数据超过3天则进行截断
        if len(kpidata_train) > 3 * self.period:
            kpidata_train = kpidata_train[-3 * self.period:]

        kpidata_train.index = range(-len(kpidata_train) + 1, 1)
        kpidata_train['hour'] = kpidata_train.index % self.period // self.interval

        future_predict = np.array([[i] * self.interval for i in
                                   kpidata_train.groupby('hour')[
                                       kpi_col].quantile(
                                       quantile).to_list()]).flatten()
        # 增加上下界
        try:
            # 如果数据大于两天，则进行周期分解后用remainder计算分时段的sigma
            decomp_result = DataPreprocessUtils().stl_decomp(kpidata_train, 'kpi', self.period)
            sigma = np.array([[i] * self.interval for i in
                              decomp_result.groupby('hour')[
                                  'remainder'].mad().to_list()]).flatten()
        except Exception:
            # 否则用原始值计算分时段sigma
            sigma = np.array([[i] * self.interval for i in
                              kpidata_train.groupby('hour')[
                                  kpi_col].mad().to_list()]).flatten()

        upper_interval = future_predict + interval_sigma * sigma
        lower_interval = future_predict - interval_sigma * sigma

        return (future_predict, upper_interval, lower_interval)

    def fit(self, X, y=None):
        """
        This should fit classifier. All the "work" should be done here.

        Note: assert is not a good choice here and you should rather
        use try/except blog with exceptions. This is just for short syntax.
        """
        """
        进行训练并直接进行预测，不保存模型，直接进行预测
        :param dataset:预处理后的数据，包含ts和预处理后的kpi值
        :param period:一周期有几个点
        :param interval:点和点之间的时间间隔,秒数
        :param colname:要预测的列名，'kpi'
        :param params:预测模型的一些参数，和预处理部分参数是分开的
        pd_detector = "ACF_Med"
        pd_params = {
            "period_candi": 1440, ## this is important
            "refinePeriod_toggle": True,
            "refine_tolerance": 0.05,
            "acf_peak_th": 0.15
        }
        stl_detector = "Robust_STL"
        interval_sigma = 2
        non_zero_lower_interval=True
        stl_params = {
            "data_T": None,
            "noise_toggle": True,
            "noise_sigma_i": .2,
            "noise_sigma_d": 5,
            "noise_truncate": 2,
            "trend_toggle": True,
            "trend_vlambda": 50,
            "trend_vlambda_diff": 5,
            "trend_solver_method": 'GADMM',
            "trend_solver_maxiters": 50,
            "trend_solver_show_progress": False,
            "trend_down_sample": 6,
            "season_bilateral_period_num": 2,
            "season_neighbour_wdw_size": 20,
            "season_sigma_i": .2,
            "season_sigma_d": 2,
            "latest_decomp_output": True,
            "latest_decomp_length": None
        }

        :param forecast_horizon: 往后预测的秒数
        :param metric_id:
        :param ad_train_id：
        :return:future_predict_df[['ts', 'pred', 'upper', 'lower']]
        """
        pd_detector = self.params['pd_detector']
        pd_params = self.params['pd_params']
        stl_detector = self.params['stl_detector']
        stl_params = self.params['stl_params']
        non_zero_lower_interval = self.params['non_zero_lower_interval']
        # 将预测的秒数转换为点数
        forecast_horizon_cnt = int(self.forecast_horizon / self.interval)
        self.forecast_horizon_cnt = forecast_horizon_cnt
        # 用单拎出来的自定义参数覆盖
        pd_params['acf_peak_th'] = self.acf_peak_th
        pd_params['refine_tolerance'] = self.refine_tolerance
        interval_sigma = self.interval_sigma

        # 同时更新params里面的对应字段
        self.params['pd_params'] = pd_params
        self.params['interval_sigma'] = interval_sigma
        self.params['quantile'] = self.quantile
        # 更新训练结束时间
        self.training_end_ts_str = str(X['ts'].max())

        # 首先判断数据是否小于三个周期，是则直接用分位数算法进行预测返回结果
        if len(X) < self.period * 3:
            (future_predict, upper_interval, lower_interval) = self._quantile_forecast(kpidata_train=X,
                                                                                       quantile=self.quantile,
                                                                                       kpi_col=self.colname,
                                                                                       interval_sigma=self.interval_sigma)

        else:
            # 当数据大于三天时，首先进行周期性的判别
            period_det = GeneralPeriodicityDetector(pd_params, pd_detector)
            try:
                passed_check_acf, period_output = period_det.fit_transform(X[self.colname].values)
            except Exception:
                passed_check_acf = False
                # raise Exception("周期性检测报错")
            # 将判别结果写回params中
            self.params['passed_check_acf'] = passed_check_acf

            if passed_check_acf:
                # 具有周期性，将判别结果写回params中
                self.params['period_output'] = period_output[0]
                # 具备周期性，则进行robust stl分解，再进行预测
                stl_params["data_T"] = period_output[0]
                stl_params["latest_decomp_length"] = forecast_horizon_cnt
                decomp = GeneralDecompEstimator(stl_params, stl_detector)
                self.damo_input = json.dumps(list(X[self.colname].values))
                decomp_result, latest_decomp_result = decomp.fit_transform(X[self.colname].values)
                self.damo_output = json.dumps(latest_decomp_result)
                future_predict = np.array(latest_decomp_result["season_plus_trend"])
                # 计算上下界
                std = pd.Series(decomp_result['residual']).mad()
                upper_interval = future_predict + interval_sigma * std
                lower_interval = future_predict - interval_sigma * std
                if non_zero_lower_interval:
                    lower_interval[lower_interval < 0] = 0
            else:
                # 不具备周期性，则同样使用分位数预测法
                (future_predict, upper_interval, lower_interval) = self._quantile_forecast(kpidata_train=X,
                                                                                           quantile=self.quantile,
                                                                                           kpi_col=self.colname,
                                                                                           interval_sigma=self.interval_sigma)

        if non_zero_lower_interval:
            lower_interval[lower_interval < 0] = 0

        self.future_predict = future_predict
        self.upper_interval = upper_interval
        self.lower_interval = lower_interval

        return self

    def predict(self, X=None, y=None):
        """
        :param X: 如果X不为None, 则按照X的ts来给出对应的预测结果;为None预测默认配置长度
        :param y: None
        :return:
        """
        future_predict_df = pd.DataFrame(self.future_predict, columns=['pred'])
        training_end_ts = datetime.datetime.strptime(self.training_end_ts_str, "%Y-%m-%d %H:%M:%S")
        # 计算预测时段的开始和结束时间
        pred_start_ts = training_end_ts + datetime.timedelta(seconds=self.interval)
        pred_end_ts = pred_start_ts + datetime.timedelta(seconds=self.forecast_horizon_cnt * self.interval)
        preprocessor = DataPreprocessUtils()
        freq = str(self.interval) + 'S'
        timeindex = preprocessor.get_complete_date_range(pred_start_ts, pred_end_ts, freq, 'ts')
        future_predict_df['ts'] = timeindex
        future_predict_df['upper'] = self.upper_interval
        future_predict_df['lower'] = self.lower_interval

        future_predict_df = future_predict_df[(future_predict_df['ts'].notna())]

        def ts_format(ts_str):
            return int(time.mktime(time.strptime(str(ts_str), "%Y-%m-%d %H:%M:%S")))
        future_predict_df['ts'] = future_predict_df['ts'].apply(ts_format)
        if X is not None:
            X.loc[:, "ts"] = X.loc[:, "ts"].astype("str")
            future_predict_df = future_predict_df.merge(X, how="inner", on='ts')[["ts", "upper", "pred"]]

        future_predict_df_dict = future_predict_df[['ts', 'upper', 'pred']].to_dict("records")
        return (future_predict_df_dict, self.params, self.damo_input, self.damo_output)

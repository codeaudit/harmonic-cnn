import logging
import numpy as np
import os
import pandas
import sklearn.metrics

import wcqtlib.common.utils as utils

logger = logging.getLogger(__name__)


def concat_dataset_column(predictions_df, features_df, test_set):
    """Joins the features and predictions on the index, and
    concatenates the "dataset" field from features_df to the
    predictions_df.

    Returns
    -------
    joined_predictions : pandas.DataFrame
        predictions_df including the dataset.
    """
    predictions_df = pandas.concat([
        predictions_df,
        features_df[features_df.index.isin(predictions_df.index)]['dataset']],
        axis=1)
    return predictions_df[predictions_df["dataset"] == test_set]


class PredictionAnalyzer(object):
    """Worker class which cretes analysis dataframes from
    the predictions.
    """

    def __init__(self, predictions_df, features_df=None, test_set=None):
        """
        Parameters
        ----------
        predictions_df : pandas.DataFrame
            DataFrame containing predictions generated by
            evaluate.evaluate_df. Indeces from the predictions_df
            should match indeces in the features_df.

        features_df : pandas.DataFrame or None
            DataFrame pointing to the original audio, features, and
            all associated metadata.

        test_set : str in ["rwc", "uiowa", "philharmonia"] or None
            Operates only on files from the dataset specified.
            Or, if None, operates on all files.
        """
        self.predictions_df = concat_dataset_column(
            predictions_df, features_df, test_set)
        self.test_set = test_set

    @classmethod
    def from_config(cls, config, experiment_name, model_name, test_set):
        features_path = os.path.join(
            os.path.expanduser(config["paths/extract_dir"]),
            config["dataframes/features"])
        experiment_dir = os.path.join(
            os.path.expanduser(config['paths/model_dir']),
            experiment_name)
        model_name = utils.iter_from_params_filepath(model_name)
        predictions_df_path = os.path.join(
            experiment_dir,
            config.get('experiment/predictions_format', None)
            .format(model_name))

        features_df = pandas.read_pickle(features_path)
        predictions_df = pandas.read_pickle(predictions_df_path)

        return cls(predictions_df, features_df, test_set)

    def save(self, write_path):
        pass

    def load(self, read_path):
        pass

    @property
    def y_true(self):
        return self.predictions_df["target"].tolist()

    @property
    def y_pred(self):
        return self.predictions_df["max_likelyhood"].tolist()

    @property
    def mean_loss(self):
        return self.predictions_df["mean_loss"].mean()

    @property
    def accuracy(self):
        return self.tps.sum().mean()

    @property
    def tps(self):
        return self.predictions_df["max_likelyhood"] == \
            self.predictions_df["target"]

    @property
    def support(self):
        return np.bincount(self.predictions_df["target"])

    @property
    def confusion_matrix(self):
        return sklearn.metrics.confusion_matrix(self.y_true, self.y_pred)

    @property
    def classification_report(self):
        return sklearn.metrics.classification_report(self.y_true, self.y_pred)

    def class_wise_scores(self):
        """
        Return a pandas DataFrame for scores for each class,
        where the scores are the columns, and the classes are the index.
        """
        precision = sklearn.metrics.precision_score(
            self.y_true, self.y_pred, average=None)
        recall = sklearn.metrics.recall_score(
            self.y_true, self.y_pred, average=None)
        f1score = sklearn.metrics.f1_score(
            self.y_true, self.y_pred, average=None)

        return pandas.DataFrame(
            [precision, recall, f1score, self.support],
            columns=["precision", "recall", "f1score", "support"])

    def summary_scores(self):
        """Return summary scores over the entire dataset."""
        precision = sklearn.metrics.precision_score(
            self.y_true, self.y_pred, average="weighted")
        recall = sklearn.metrics.recall_score(
            self.y_true, self.y_pred, average="weighted")
        f1score = sklearn.metrics.f1_score(
            self.y_true, self.y_pred, average="weighted")
        return pandas.Series([precision, recall, f1score],
                             index=["precision", "recall", "f1score"])

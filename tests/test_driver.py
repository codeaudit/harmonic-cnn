import copy
import logging
import logging.config
import numpy as np
import os
import pandas
import pytest

import wcqtlib.common.config as C
import wcqtlib.data.dataset as dataset
import wcqtlib.driver as driver

logger = logging.getLogger(__name__)
logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': "standard"
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'DEBUG',
                'propagate': True
            }
        }
    })

CONFIG_PATH = os.path.join(os.path.dirname(__file__), os.pardir,
                           "data", "master_config.yaml")
config = C.Config.from_yaml(CONFIG_PATH)


@pytest.fixture
def tinyds():
    return dataset.TinyDataset.load()


@pytest.fixture
def tiny_feats(workspace, tinyds):
    return driver.extract_features(tinyds, workspace)


@pytest.mark.runme
def test_extract_features(workspace, tiny_feats):
    for obs in tiny_feats.items():
        assert "cqt" in obs.features
        assert os.path.exists(obs.features['cqt'])


@pytest.mark.slowtest
def test_train_simple_model(workspace):
    thisconfig = copy.deepcopy(config)
    thisconfig.data['training']['max_iterations'] = 200
    thisconfig.data['training']['batch_size'] = 12
    thisconfig.data['paths']['model_dir'] = workspace
    experiment_name = "testexperiment"
    hold_out = "rwc"

    driver.train_model(thisconfig, 'cqt_iX_f1_oY',
                       experiment_name, hold_out,
                       max_files_per_class=1)

    # Expected files this should generate
    new_config = os.path.join(workspace, experiment_name, "config.yaml")
    final_params = os.path.join(workspace, experiment_name, "params",
                                "final.npz")
    train_loss_fp = os.path.join(workspace,
                                 experiment_name, "training_loss.pkl")
    assert os.path.exists(new_config) and os.path.exists(final_params)
    assert os.path.exists(train_loss_fp)

    # Also make sure the training & validation splits got written out
    train_fp = os.path.join(workspace, experiment_name,
                            "train_df_{}.pkl".format(hold_out))
    assert os.path.exists(train_fp)
    valid_fp = os.path.join(workspace, experiment_name,
                            "train_df_{}.pkl".format(hold_out))
    assert os.path.exists(valid_fp)


@pytest.mark.runme
@pytest.mark.slowtest
def test_find_best_model(workspace):
    thisconfig = copy.deepcopy(config)
    thisconfig.data['training']['iteration_write_frequency'] = 5
    thisconfig.data['training']['iteration_print_frequency'] = 10
    thisconfig.data['training']['max_iterations'] = 200
    thisconfig.data['training']['batch_size'] = 12
    thisconfig.data['paths']['model_dir'] = workspace
    thisconfig.data['experiment']['hold_out_set'] = "rwc"
    experiment_name = "testexperiment"
    hold_out = thisconfig['experiment/hold_out_set']

    valid_df_path = os.path.join(
        workspace, experiment_name,
        thisconfig['experiment/data_split_format'].format(
            "valid", hold_out))

    driver.train_model(thisconfig, 'cqt_iX_f1_oY',
                       experiment_name, hold_out,
                       max_files_per_class=3)
    # This should have been created by the training process.
    assert os.path.exists(valid_df_path)

    # Create a vastly reduced validation dataframe so it'll take less long.
    validation_size = 20
    valid_df = pandas.read_pickle(valid_df_path).sample(n=validation_size)
    assert len(valid_df) == validation_size

    results_df = driver.find_best_model(thisconfig, experiment_name, valid_df,
                                        plot_loss=False)
    # check that the results_df is ordered by iteration.
    assert all(results_df["model_iteration"] ==
               sorted(results_df["model_iteration"]))

    # Get the best param
    param_iter, best_param_file = driver.select_best_iteration(results_df)
    assert best_param_file is not None

    # load it again to test the reloading thing.
    #  Just making sure this runs through
    results_df2 = driver.find_best_model(thisconfig, experiment_name, valid_df,
                                         plot_loss=False)
    assert all(results_df == results_df2)

    predictions_df = driver.predict(
        thisconfig, experiment_name,
        best_param_file, features_df_override=valid_df)
    assert not predictions_df.empty
    predictions_df_path = os.path.join(
        workspace, experiment_name,
        "model_{}_predictions.pkl".format(param_iter))
    assert os.path.exists(predictions_df_path)

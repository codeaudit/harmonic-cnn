import lasagne
from lasagne.layers import get_all_layers
import logging
import numpy as np
import os
import pandas
import pytest

import hcnn.train.streams as streams
import hcnn.train.models as models
import hcnn.logger

logger = logging.getLogger(__name__)
hcnn.logger.init('DEBUG')


@pytest.fixture
def simple_network_def():
    input_shape = (None, 1, 5, 5)
    network_def = {
        "input_shape": input_shape,
        "layers": [{
            "type": "layers.Conv2DLayer",
            "num_filters": 4,
            "filter_size": (2, 2),
            "nonlinearity": "nonlin.rectify",
            "W": "init.glorot"
        }, {
            "type": "layers.MaxPool2DLayer",
            "pool_size": (2, 2)
        }, {
            "type": "layers.DropoutLayer",
            "p": 0.5
        }, {
            "type": "layers.DenseLayer",
            "num_units": 2,
            "nonlinearity": "nonlin.softmax"
        }],
        "loss": "loss.categorical_crossentropy"
    }
    return network_def


@pytest.fixture(
    scope="module",
    params=[models.cqt_MF_n16,
            models.cqt_MF_n32,
            models.cqt_MF_n64,
            models.cqt_M2_n8,
            models.cqt_M2_n16,
            models.cqt_M2_n32,
            models.cqt_M2_n64  #,
            # models.hcqt_MH_n8,
            # models.hcqt_MH_n16,
            # models.hcqt_MH_n32,
            # models.hcqt_MH_n64
            ],
    ids=['MF_16', 'MF_32', 'MF_64',
         'M2_8', 'M2_16', 'M2_32', 'M2_64'  #,
         # 'MH_8', 'MH_16', 'MH_32', 'MH_64'
         ])
def network_def_fn(request):
    return request.param


@pytest.fixture
def batch_norm_def(simple_network_def):
    simple_network_def["batch_norm"] = True
    return simple_network_def


@pytest.fixture
def batch_norm_no_last_layer_def(simple_network_def):
    simple_network_def["batch_norm"] = True
    simple_network_def['layers'][-1]["batch_norm"] = False
    return simple_network_def


def test_names_to_objects():
    test_dict = {
        "i'm_a_layer": "layers.Conv1DLayer",
        "i'm_a_list": [{
            "anotherlayer": "init.glorot"},
            {"yetanother": "i shouldn't work",
             "butishould": "nonlin.rectify"}
        ]
    }
    object_dict = models.names_to_objects(test_dict)
    assert object_dict["i'm_a_layer"] == lasagne.layers.Conv1DLayer
    assert isinstance(object_dict["i'm_a_list"][0]["anotherlayer"],
                      lasagne.init.GlorotUniform)
    assert object_dict["i'm_a_list"][1]["yetanother"] == \
        "i shouldn't work"
    assert object_dict["i'm_a_list"][1]["butishould"] == \
        lasagne.nonlinearities.rectify


def __test_network(network_def, input_shape):
    model = models.NetworkManager(network_def)
    assert model is not None

    batch_size = 8
    input_shape = (batch_size,) + input_shape[1:]
    test_batch = np.asarray(np.random.random(input_shape), dtype=np.float32)
    test_target = np.asarray(np.random.randint(2, size=batch_size),
                             dtype=np.int32)
    loss = model.train_fx(test_batch, test_target)
    assert np.isfinite(loss)

    probs = model.predict_fx(test_batch)
    assert np.all(np.isfinite(probs))

    loss, acc = model.eval_fx(test_batch, test_target)
    assert np.isfinite(loss) and np.isfinite(acc)


def test_networkmanager_buildnetwork():
    # 1c 1f
    input_shape = (None, 1, 5, 5)
    network_def = {
        "input_shape": input_shape,
        "layers": [{
            "type": "layers.Conv2DLayer",
            "num_filters": 4,
            "filter_size": (2, 2),
            "nonlinearity": "nonlin.rectify",
            "W": "init.glorot"
        },
        {
            "type": "layers.MaxPool2DLayer",
            "pool_size": (2, 2)
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 2,
            "nonlinearity": "nonlin.softmax"
        }],
        "loss": "loss.categorical_crossentropy"
    }
    yield __test_network, network_def, input_shape

    # 0c 3f
    input_shape = (None, 1, 8, 252)
    network_def = {
        "input_shape": input_shape,
        "layers": [
        {
            "type": "layers.DropoutLayer",
            "p": 0.25
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 512,
            "nonlinearity": "nonlin.rectify"
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 512,
            "nonlinearity": "nonlin.rectify"
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 2,
            "nonlinearity": "nonlin.softmax"
        }],
        "loss": "loss.categorical_crossentropy"
    }
    yield __test_network, network_def, input_shape

    # 3c 3f
    {
        "input_shape": input_shape,
        "layers": [{
            "type": "layers.Conv2DLayer",
            "num_filters": 16,
            "filter_size": (1, 3),
            "nonlinearity": "nonlin.rectify",
            "W": "init.glorot"},
        {
            "type": "layers.MaxPool2DLayer",
            "pool_size": (1, 2)  # 8 x 125
            },
        {
            "type": "layers.Conv2DLayer",
            "num_filters": 32,
            "filter_size": (3, 4),  # -> 6x122
            "nonlinearity": "nonlin.rectify",
            "W": "init.glorot"
        },
        {
            "type": "layers.MaxPool2DLayer",
            "pool_size": (2, 2)  # -> 3 x 61
        },
        {
            "type": "layers.Conv2DLayer",
            "num_filters": 64,
            "filter_size": (2, 4),  # -> 2 x 58
            "nonlinearity": "nonlin.rectify",
            "W": "init.glorot"
        },
        {
            "type": "layers.MaxPool2DLayer",
            "pool_size": (1, 2)  # -> 2 x 29
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 256,
            "nonlinearity": "nonlin.rectify"
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 256,
            "nonlinearity": "nonlin.rectify"
        },
        {
            "type": "layers.DropoutLayer",
            "p": 0.5
        },
        {
            "type": "layers.DenseLayer",
            "num_units": 2,
            "nonlinearity": "nonlin.softmax"
        }],
        "loss": "loss.categorical_crossentropy"
    }
    yield __test_network, network_def, input_shape


def test_batchnorm(batch_norm_def):
    model = models.NetworkManager(batch_norm_def)
    assert model is not None

    layer_names = [l.__class__.__name__
                   for l in get_all_layers(model._network)]
    batch_norm_layers = [l for l in layer_names
                         if 'BatchNormLayer' in l]
    layer_count = len(batch_norm_def['layers'])
    assert len(batch_norm_layers) == layer_count


def test_batchnorm_except_last_layer(batch_norm_no_last_layer_def):
    model = models.NetworkManager(batch_norm_no_last_layer_def)
    assert model is not None

    layer_names = [l.__class__.__name__
                   for l in get_all_layers(model._network)]
    batch_norm_layers = [l for l in layer_names
                         if 'BatchNormLayer' in l]
    layer_count = len(batch_norm_no_last_layer_def['layers'])
    assert len(batch_norm_layers) == (layer_count - 1)


@pytest.mark.skip(reason="ToDo")
def test_networkmanager_updatehypers():
    pass


def test_networkmanager_save(workspace, simple_network_def):
    """Also test deserialization."""
    save_path = os.path.join(workspace, "output.npz")

    model = models.NetworkManager(simple_network_def)
    assert model is not None

    success = model.save(save_path)
    assert success and os.path.exists(save_path)

    data = np.load(save_path)
    assert "definition" in data and "params" in data

    model = models.NetworkManager.deserialize_npz(save_path)
    assert model is not None
    assert model._network is not None


def test_networkmanager_train_and_predict(simple_network_def):
    input_shape = (None, 1, 5, 5)

    model = models.NetworkManager(simple_network_def)
    assert model is not None

    batch_size = 8
    input_shape = (batch_size,) + input_shape[1:]

    batch = dict(
        x_in=np.random.random(input_shape),
        target=np.random.randint(2, size=batch_size))
    loss = model.train(batch)
    assert np.isfinite(loss)

    probs = model.predict(batch)
    assert np.all(np.isfinite(probs))

    loss, acc = model.evaluate(batch)
    assert np.isfinite(loss) and np.isfinite(acc)


def test_networkmanager_t_and_p_experiments(network_def_fn):
    input_shape = (None, 1, 43, 252)
    n_classes = 3

    network_def = network_def_fn(input_shape[2], n_classes)
    model = models.NetworkManager(network_def)
    assert model is not None

    batch_size = 8
    input_shape = (batch_size,) + input_shape[1:]

    batch = dict(
        x_in=np.random.random(input_shape),
        target=np.random.randint(n_classes, size=batch_size))
    loss = model.train(batch)
    assert np.isfinite(loss)

    probs = model.predict(batch)
    assert np.all(np.isfinite(probs))

    loss, acc = model.evaluate(batch)
    assert np.isfinite(loss) and np.isfinite(acc)


@pytest.mark.cqt
@pytest.mark.slowtest
def test_overfit_two_samples_cqt(tiny_feats):
    """Prove that our network works by training it with two random files
    from our dataset, intentionally overfitting it.

    Warning: not deterministic, but you could make it.
    """
    features_df = tiny_feats.to_df()

    # Get list of instruments
    instruments = sorted(features_df["instrument"].unique())
    selected_instruments = instruments[:2]

    # Create a dataframe from our dataframe with only two files in it
    test_df = pandas.concat([
        features_df[features_df["instrument"] ==
                    selected_instruments[0]].sample(),
        features_df[features_df["instrument"] ==
                    selected_instruments[1]].sample()])

    t_len = 8
    batch_size = 8
    n_targets = 2
    # Create a streamer that samples just those two files.
    streamer = streams.InstrumentStreamer(
        test_df, streams.cqt_slices,
        t_len=t_len, batch_size=batch_size)

    # Create a new model
    network_def = models.cqt_iX_c1f1_oY(t_len, n_targets)
    model = models.NetworkManager(network_def)

    # Train the model for N epochs, till it fits the damn thing
    max_batches = 10
    i = 0
    for batch in streamer:
        train_loss = model.train(batch)

        i += 1
        print("Batch: ", i, "Loss: ", train_loss)
        if i >= max_batches:
            break

    # Evaluate it. On the original files. Should do well.
    eval_batch = next(streamer)
    eval_probs = model.predict(eval_batch)
    eval_loss, accuracy = model.evaluate(eval_batch)
    print("Predictions:", eval_probs)
    print("Eval Loss:", eval_loss, "Accuracy:", accuracy)
    assert np.all(np.isfinite(eval_probs)) and np.isfinite(eval_loss) and \
        np.isfinite(accuracy)


# @pytest.mark.wcqt
# @pytest.mark.slowtest
# def test_overfit_two_samples_wcqt(tiny_feats):
#     """Prove that our network works by training it with two random files
#     from our dataset, intentionally overfitting it.

#     Warning: not deterministic, but you could make it.
#     """
#     features_df = tiny_feats.to_df()

#     # Get list of instruments
#     instruments = sorted(features_df["instrument"].unique())
#     selected_instruments = instruments[:2]

#     # Create a dataframe from our dataframe with only two files in it
#     test_df = pandas.concat([
#         features_df[features_df["instrument"] ==
#                     selected_instruments[0]].sample(),
#         features_df[features_df["instrument"] ==
#                     selected_instruments[1]].sample()])

#     t_len = 8
#     batch_size = 8
#     n_targets = 2
#     # Create a streamer that samples just those two files.
#     streamer = streams.InstrumentStreamer(
#         test_df, streams.wcqt_slices,
#         t_len=t_len, batch_size=batch_size)
#     input_shape = next(streamer)['x_in'].shape
#     print(input_shape)

#     # Create a new model
#     network_def = models.wcqt_iX_c1f1_oY(t_len, n_targets)
#     model = models.NetworkManager(network_def)

#     # Train the model for N epochs, till it fits the damn thing
#     max_batches = 10
#     i = 0
#     for batch in streamer:
#         train_loss = model.train(batch)

#         i += 1
#         print("Batch: ", i, "Loss: ", train_loss)
#         if i >= max_batches:
#             break

#     # Evaluate it. On the original files. Should do well.
#     eval_batch = next(streamer)
#     eval_probs = model.predict(eval_batch)
#     eval_loss, accuracy = model.evaluate(eval_batch)
#     print("Eval predictions:", eval_probs)
#     print("Eval Loss:", eval_loss, "Accuracy:", accuracy)
#     assert np.isfinite(eval_loss) and np.isfinite(accuracy)

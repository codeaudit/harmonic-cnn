"""A class and utilities for managing the dataset and dataframes.
"""

import copy
import json
import jsonschema
import logging
import os
import pandas
import requests
import sys

import wcqtlib.common.config as C

logger = logging.getLogger(__name__)

SCHEMA_PATH = "https://raw.githubusercontent.com/ejhumphrey/minst-dataset/" \
              "master/minst/schema/observation.json"


def get_remote_schema(url=SCHEMA_PATH):
    return requests.get(url).json()


class Observation(object):
    """Document model each item in the collection.
    TODO: Inherit / whatever from minst-dataset repo
    """
    SCHEMA = get_remote_schema()

    def __init__(self, index, dataset, audio_file, instrument, source_key,
                 start_time, duration, note_number, dynamic, partition,
                 features=None):
        self.index = index
        self.dataset = dataset
        self.audio_file = audio_file
        self.instrument = instrument
        self.source_key = source_key
        self.start_time = start_time
        self.duration = duration
        self.note_number = note_number
        self.dynamic = dynamic
        self.partition = partition
        self.features = features if features else dict()

    def to_dict(self):
        return self.__dict__.copy()

    def validate(self, schema=None):
        schema = self.SCHEMA if schema is None else schema
        success = True
        try:
            jsonschema.validate(self.to_dict(), schema)
        except jsonschema.ValidationError:
            success = False
        success &= os.path.exists(self.audio_file)
        # if success:
        #     success &= utils.check_audio_file(self.audio_file)[0]

        return success


class Dataset(object):
    """A class wrapper for loading the dataset
    from various inputs, and writing to various
    outputs, with utilities for providing
    views over datasets and generating train/val
    sets.

    A dataset contains the following columns
     - audio_file
     - target [normalized target names]
     - [some provenance information]
    """

    def __init__(self, observations):
        """
        Parameters
        ----------
        observations : list
            List of Observations (as dicts or Observations.)
            If they're dicts, this will convert them to Observations.
        """
        def safe_obs(obs):
            "Get dict from an Observation if an observation, else just dict"
            if isinstance(obs, Observation):
                return obs.to_dict()
            else:
                return obs
        self.observations = [Observation(**safe_obs(x)) for x in observations]

    @classmethod
    def read_json(cls, json_path):
        with open(json_path, 'r') as fh:
            return cls(json.load(fh))

    def save_json(self, json_path):
        with open(json_path, 'w') as fh:
            json.dump(self.to_builtin(), fh)

    def to_df(self):
        """Returns the dataset as a dataframe."""
        return pandas.DataFrame.from_dict(self.to_builtin())

    def to_builtin(self):
        return [x.to_dict() for x in self.observations]

    @property
    def items(self):
        return self.observations

    def __len__(self):
        return len(self.observations)

    def validate(self):
        if len(self.observations > 0):
            return all([x.validate for x in self.observations])
        else:
            logger.warning("No observations to validate.")
            return False

    def view(self, dataset):
        """Returns a copy of the analyzer pointing to the desired dataset.
        Parameters
        ----------
        dataset : str
            String in ["rwc", "uiowa", "philharmonia"] which is
            the items in the dataset to return.

        Returns
        -------
        """
        thecopy = copy.copy(self.to_df())
        ds_view = thecopy[thecopy["dataset"] == dataset]
        return ds_view


class TinyDataset(Dataset):
    ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
        os.pardir, os.pardir, "tests", "tinydata"))
    DS_FILE = os.path.join(self.ROOT_PATH, "tinydata.json")

    @classmethod
    def read_json(cls, json_path=DS_FILE):
        with open(json_path, 'r') as fh:
            data = json.load(fh)
            # Update the paths to full paths.
            for item in data:
                item['audio_file'] = os.path.join(cls.ROOT_PATH,
                                                  item['audio_file'])
        return cls(data)


def build_tiny_dataset_from_old_dataframe(config):
    def sample_record(df, dataset, instrument):
        query_records = df.loc[(df["dataset"] == dataset) &
                               (df["instrument"] == instrument)]

        return query_records.sample() if not query_records.empty else None
    df_path = os.path.expanduser(config['paths/extract_dir'])
    notes_df_path = os.path.join(df_path, config['dataframes/notes'])
    notes_df = pandas.read_pickle(notes_df_path)

    tiny_dataset = []
    # Get one file for each instrument for each dataset.
    for dataset in notes_df["dataset"].unique():
        for instrument in notes_df["instrument"].unique():
            # Grab it from the notes
            record = sample_record(notes_df, dataset, instrument)
            # If that fails, just grab a file from the original datasets
            if record is None:
                logger.warning("Dataset {} has no instrument '{}'".format(
                    dataset, instrument))
                continue

            tiny_dataset.append(
                Observation(
                    index=record.index[0][0],
                    dataset=record['dataset'][0],
                    audio_file=record['audio_file'][0],
                    instrument=record['instrument'][0],
                    source_key=None,
                    start_time=None,
                    duration=None,
                    note_number=record['note'][0],
                    dynamic=record['dynamic'][0],
                    partition=None
                    ))
    return tiny_dataset


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Building tiny dataset from notes_df.")
    ROOT_DIR = os.path.join(
        os.path.dirname(__file__), os.pardir, os.pardir)
    CONFIG_PATH = os.path.join(ROOT_DIR, "data", "master_config.yaml")
    config = C.Config.from_yaml(CONFIG_PATH)

    TINY_DATASET_JSON = os.path.normpath(
        os.path.join(ROOT_DIR, config['paths/tiny_dataset']))

    tinyds = build_tiny_dataset_from_old_dataframe(config)
    tinyds = Dataset(tinyds)
    logger.debug("Tiny Dataset has {} records.".format(len(tinyds)))
    # Save it.
    logger.info("Saving dataset to: {}".format(TINY_DATASET_JSON))
    tinyds.save_json(TINY_DATASET_JSON)
    sys.exit(os.path.exists(TINY_DATASET_JSON) is False)

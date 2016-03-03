"""Utilities for manipulating audio files."""

import claudio
import claudio.sox
import librosa
import logging
import numpy as np
import os
import pandas
import progressbar

import wcqtlib.data.parse
import wcqtlib.common.utils as utils

logger = logging.getLogger(__name__)


def get_onsets(audio, sr, **kwargs):
    # reshape the damn audio so that librosa likes it.
    reshaped_audio = audio.reshape((audio.shape[0],))
    onset_frames = librosa.onset.onset_detect(
        y=reshaped_audio, sr=sr, **kwargs)
    onset_samples = librosa.frames_to_samples(onset_frames)
    return onset_samples


def split_and_standardize_examples(input_audio_path,
                                   output_dir,
                                   first_onset_start=.05,
                                   final_duration=None):
    """Takes an audio file, and splits it up into multiple
    audio files, using silence as the delimiter.

    Once they are split, the onset, as detected by librosa,
    is then placed at the location specified by first_onset_start.

    Parameters
    ----------
    input_audio_path : str
        Full path to the audio file to use.

    output_dir : str
        Full path to the folder where you want to place the
        result files. Will be created if it does not exist.

    first_onset_start : float
        Value in seconds where the first onset will
        be set, for a sort of normalization of the audio.

    final_duration : float or None
        If not None, trims the final audio file to final_duration
        seconds.

    Returns
    -------
    output_files : List of audio files created in this process.
    """
    original_name = os.path.basename(input_audio_path)
    filebase = utils.filebase(original_name)
    new_output_path = os.path.join(output_dir, original_name)

    # Make sure hte output directory exists
    utils.create_directory(output_dir)

    ready_files = []

    # Split the audio files using claudio.sox
    if claudio.sox.split_along_silence(
                input_audio_path, new_output_path):

        # Sox generates files of the form:
        # original_name001.xxx
        # original_name001.xxx
        process_files = [x for x in os.listdir(output_dir) if filebase in x]

        # For each file generated
        for file_name in process_files:
            audio_path = os.path.join(output_dir, file_name)
            success = standardize_one(audio_path,
                                      first_onset_start=first_onset_start,
                                      final_duration=final_duration)
            if success:
                ready_files.append(audio_path)

    return ready_files


def standardize_one(input_audio_path,
                    first_onset_start=.05,
                    center_of_mass_alignment=False,
                    final_duration=None):
    """Takes a single audio file, and standardizes it based
    on the parameters provided.

    Heads up! Modifies the file in place...

    Parameters
    ----------
    input_audio_path : str
        Full path to the audio file to work with.

    first_onset_start : float or None
        If not None, uses librosa's onset detection to find
        the first onset in the file, and then pads the beginning
        of the file with zeros such that the first onset
        ocurrs at first_onset_start seconds.

        If no onsets are discovered, assumes this is an
        empty file, and returns False.

    center_of_mass_alignment : boolean
        If True, aligns the center of mass of the file to
        be at the center of the sample.

    final_duration : float or None
        If not None, trims the final audio file to final_duration
        seconds.

    Returns
    -------
    True if all processes passed. False otherwise.
    """
    # Load the audio file
    audio_modified = False
    audio, sr = claudio.read(input_audio_path, channels=1)

    if first_onset_start is not None:
        # Find the onsets using librosa
        onset_samples = get_onsets(audio, sr)

        first_onset_start_samples = first_onset_start * sr
        actual_first_onset = onset_samples[0]
        # Pad the beginning with up to onset_start ms of silence
        onset_difference = first_onset_start_samples - actual_first_onset

        # Correct the difference by adding or removing samples
        # from the beginning.
        if onset_difference > 0:
            # In this case, we need to append this many zeros to the start
            audio = np.concatenate([
                np.zeros([onset_difference, audio.shape[-1]]),
                audio])
            audio_modified = True
        elif onset_difference < 0:
            audio = audio[np.abs(onset_difference):]
            audio_modified = True

    if center_of_mass_alignment:
        raise NotImplementedError("Center of mass not yet implemented.")

    if final_duration:
        final_length_samples = final_duration * sr
        # If this is less than the amount of data we have
        if final_length_samples < len(audio):
            audio = audio[:final_length_samples]
            audio_modified = True
        # Otherwise, just leave it at the current length.

    if audio_modified:
        # save the file back out again.
        claudio.write(input_audio_path, audio, samplerate=sr)

        return True
    else:
        return False


def datasets_to_notes(datasets_df, extract_path):
    """Take the dataset dataframe created in parse.py
    and extract and standardize separate notes from
    audio files which have multiple notes in them.

    Must have separate behaviors for each dataset, as
    they each have different setups w.r.t the number of notes
    in the file.

    RWC : Each file containes scales of many notes.
        The notes themselves don't seem to be defined in the
        file name.

    UIOWA : Each file contains a few motes from a scale.
        The note range is defined in the filename, but
        does not appear to be consistent.
        Also the space between them is not consistent either.
        Keep an ear out for if the blank space algo works here.

    Philharmonia : These files contain single notes,
        and so are just passed through.


    Parameters
    ----------
    dataset_df : pandas.DataFrame
        Dataframe which defines the locations
        of all input audio files in the dataset and
        their associated instrument classes.

    extract_path : str
        Path which new note-separated files can be written to.

    Returns
    -------
    notes_df : pandas.DataFrame
        Dataframe which points to the extracted
        note files, still pointing to the same
        instrument classes as their parent file.

        Indexed By:
            id : [dataset identifier] + [8 char md5 of filename]
        Columns:
            parent_id : id from "dataset" file.
            audio_file : "split" audio file path.
            dataset : dataset it is from
            instrument : instrument label.
            dynamic : dynamic tag
    """
    # Two arrays for multi/hierarchical indexing.
    indexes = [[], []]
    records = []
    i = 0
    with progressbar.ProgressBar(max_value=len(datasets_df)) as progress:
        for (index, row) in datasets_df.iterrows():
            original_audio_path = row['audio_file']
            dataset = row['dataset']
            output_dir = os.path.join(extract_path, dataset)

            if dataset in ['uiowa', 'rwc']:
                result_notes = split_and_standardize_examples(
                    original_audio_path, output_dir)
            else: # for philharmonia, just pass it through.
                result_notes = [original_audio_path]

            for note_file_path in result_notes:
                # Hierarchical indexing with (parent, new)
                indexes[0].append(index)
                indexes[1].append(wcqtlib.data.parse.generate_id(
                    dataset, note_file_path))
                records.append(
                    dict(audio_file=note_file_path,
                         datset=dataset,
                         instrument=row['instrument'],
                         dynamic=row['dynamic']))
            progress.update(i)
            i += 1

    return pandas.DataFrame(records, index=indexes)

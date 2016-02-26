#!/usr/bin/env python
"""Compute CQTs for a collection of audio files.

This script writes the output files under the given output directory:

  "/some/audio/file.mp3" maps to "${output_dir}/file.npz"

Sample Call:
$ python audio_to_cqts.py \
    filelist.json \
    ./cqt_arrays \
    --cqt_params=params.json \
    --num_cpus=2
"""
from __future__ import print_function

import argparse
import claudio
from joblib import delayed
from joblib import Parallel
import json
import librosa
import numpy as np
import os
import sys
import time

import wcqtlib.common.utils as utils

CQT_PARAMS = dict(
    hop_length=512, fmin=27.5, n_bins=252, bins_per_octave=36, tuning=0.0,
    filter_scale=1, aggregate=None, norm=1, sparsity=0.0, real=True)

AUDIO_PARAMS = dict(samplerate=11025.0, channels=1, bytedepth=2)


def cqt_one(input_file, output_file, cqt_params=None, audio_params=None):
    """Compute the CQT for a input/output file Pair.

    Parameters
    ----------
    input_file : str
        Audio file to apply the CQT

    output_file : str
        Path to write the output.

    Returns
    -------
    success : bool
        True if the output file was successfully created.
    """
    if not cqt_params:
        cqt_params = CQT_PARAMS.copy()

    if not audio_params:
        audio_params = AUDIO_PARAMS.copy()

    x, fs = claudio.read(input_file, **audio_params)
    # TODO: This isn't quite correct.
    cqt_spectra = np.array([librosa.cqt(x_c, sr=fs, **cqt_params)
                            for x_c in x.T])
    frame_idx = np.arange(cqt_spectra[0].shape[1])
    time_points = librosa.frames_to_time(
        frame_idx, sr=fs, hop_length=cqt_params['hop_length'])
    np.savez(output_file, time_points=time_points, cqt=cqt_spectra)
    print("[{0}] Finished: {1}".format(time.asctime(), output_file))
    return os.path.exists(output_file)


def cqt_many(audio_files, output_files, cqt_params=None, audio_params=None,
             num_cpus=-1):
    """Compute CQT representation over a number of audio files.

    Parameters
    ----------
    audio_files : list of str, len=n
        Audio files over which to compute the CQT.

    output_files : list of str, len=n
        File paths for writing outputs.

    cqt_params : dict, default=None
        Parameters to use for CQT computation.

    audio_params : dict, default=None
        Parameters to use for loading the audio file.

    num_cpus : int, default=-1
        Number of parallel threads to use for computation.

    Returns
    -------
    success : bool
        True if all input files were processed successfully.
    """
    pool = Parallel(n_jobs=num_cpus)
    dcqt = delayed(cqt_one)
    pairs = zip(audio_files, output_files)
    return all(pool(dcqt(fin, fout, cqt_params, audio_params)
                    for fin, fout in pairs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("audio_files",
                        metavar="audio_files", type=str,
                        help="A JSON file with a list of audio filepaths.")
    parser.add_argument("output_directory",
                        metavar="output_directory", type=str,
                        help="Directory to save output arrays.")
    parser.add_argument("--cqt_params",
                        metavar="cqt_params", type=str,
                        default='',
                        help="Path to a JSON file of CQT parameters.")
    parser.add_argument("--audio_params",
                        metavar="audio_params", type=str,
                        default='',
                        help="Path to a JSON file of CQT parameters.")
    parser.add_argument("--num_cpus", type=int,
                        metavar="num_cpus", default=-1,
                        help="Number of CPUs over which to parallelize "
                             "computations.")

    args = parser.parse_args()
    with open(args.audio_files) as fp:
        audio_files = json.load(fp)

    cqt_params = None
    audio_params = None

    cqt_params = json.load(open(args.cqt_params)) if args.cqt_params else None
    audio_params = json.load(open(args.audio_params)) \
        if args.audio_params else None

    output_files = [utils.map_io(fin, args.output_directory)
                    for fin in audio_files]
    success = cqt_many(audio_files, output_files,
                       cqt_params=cqt_params, audio_params=audio_params,
                       num_cpus=args.num_cpus)
    sys.exit(0 if success else 1)

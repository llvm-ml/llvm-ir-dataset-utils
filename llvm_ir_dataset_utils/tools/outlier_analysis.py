import subprocess
from collections import Counter
import os
from os import listdir
from os.path import join
from typing import List
import pandas as pd
import parallelbar
import ray
from itertools import repeat

from opt_analysis_tools import parse_pass_analysis_exec

import psutil
import time
import re

num_cpus = psutil.cpu_count(logical=False)

opt_load_args = [
    "opt",
    "-load",
    "RemoveFunctionBodyPass/build/libRemoveFunctionBody.so",
    "-load-pass-plugin=RemoveFunctionBodyPass/build/libRemoveFunctionBody.so",
    "-passes=remove-fn-body",
]

"""
    inputs:
    - i: index of function whose function body is to be removed
    - src: path to source bitcode/IR file
    - dst: path to destination bitcode file
"""


def remove_fn(i: int, src: str, dst: str):
    if not (os.path.isfile(src) or os.path.exists(os.path.dirname(dst))):
        print("invalid file path in either src or dst argument")
        return None
    command = opt_load_args + [
        "-index",
        f"{i}",
        src,
        "-o",
        dst,
    ]

    subprocess.run(command)


"""
    inputs:
    - i: index of function whose function body is to be removed
    - bc: bitcode module (binary format)

    output:
    - modified bitcode module (binary format)

    error:
    - if wrong value input fed into the command
"""


def remove_fn_bc(i: int, bc):
    if i < 0:
        print("No negative index!")
        return None
    try:
        with subprocess.Popen(
            opt_load_args
            + [
                "-index",
                f"{i}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        ) as proc:
            return proc.communicate(input=bc)[0]
    except ValueError as e:
        print(e)
        return None


"""
Get number of functions by running opt command with remove-fn-body and parse the first line of output
"""


def get_n_functions(file_path: str):
    bc = None
    with open(file_path, mode="rb") as f:
        bc = f.read()
    try:
        with subprocess.Popen(
            opt_load_args
            + [
                "-index",
                "-1",
                "--disable-output",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        ) as proc:
            return int(proc.communicate(input=bc)[0].decode("utf-8").split("\n")[0][2:])
    except ValueError as e:
        print(e)
        return -1


"""
    Input: bitcode module (binary format)
    Output: LLVM IR (string)
"""


def get_ir(bitcode_module):
    with subprocess.Popen(
        opt_load_args
        + [
            "-index",
            "-1",
            "-S",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
    ) as proc:
        return proc.communicate(input=bitcode_module)[0].decode("utf-8")


"""
Non-optimized version of get outliers.
Inputs:
- file_path: path to bitcode file
- opt: O1, O2, O3, Oz,... optimization options (case-sensitive)
- outlier_threshold: ratio of number of outlier passes over total number of passes 
- quantile: percentile of passes given runtime data to be considered outlier for every pass
"""


def get_outliers(file_path: str, opt: str, outlier_threshold=1, quantile=0.95):
    n_functions = get_n_functions(file_path=file_path)

    tmp_path = file_path.split("/")
    tmp_path[-2] = "_tmp"
    tmp_path = "/".join(tmp_path)
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)

    ref_data = pd.read_csv(
        f"pass_runtime/transformations/{opt.lower()}_cpp.csv"
    )  # TODO: filename needs to be abstracted away!
    groups = ref_data.groupby("pass").quantile(
        q=quantile
    )  # TODO: put this outside of the loop
    bc = None
    n_removed = 0
    src_path = file_path
    fraction_outliers = []
    for i in range(n_functions):
        if n_removed > 0:
            src_path = tmp_path
        with open(src_path, mode="rb") as f:
            bc = f.read()

        # delete (non-save) function ith
        tmp = remove_fn_bc(i, bc)

        # this ignores the src_path and only takes the bitcode module
        time_analysis_tmp = parse_pass_analysis_exec(src_path, True, True, opt, tmp)

        # if removed function still results in module being in outlier range,
        # delete that function because it doesn't affect the outliers
        # (minimize functions in module such that outliers are preserved)

        outlier_status, fraction_outlier = is_outlier(
            time_analysis_tmp, ref_data=groups, threshold=outlier_threshold
        )

        if outlier_status:
            remove_fn(i, src_path, tmp_path)
            n_removed += 1
            src_path = tmp_path

        print(f"i: {i}. n_removed: {n_removed}. src_path={src_path}")
        fraction_outliers.append(fraction_outlier)
    return (n_removed, n_functions, sum(fraction_outliers) / len(fraction_outliers))


"""
Helper function for is_outlier.
Inputs:
- time: time elapsed for pass_name execution
- pass_name: name of pass to check
- ref_data: pandas DataFrame of reference data on distributions of all passes
- time col: column name that specifies time in DataFrame
"""


def check_outliers(time, pass_name, ref_data, time_col="fraction_total_time"):
    return time >= ref_data.loc[pass_name][time_col]


"""
Check if bitcode module (as data) has outlier in any of its pass, return True if so
- threshold: percentage of passes being outliers to return True. range: [0,1]
"""


def is_outlier(
    data,
    ref_data: pd.DataFrame,
    time_col="fraction_total_time",
    threshold=1,
):

    data_len = len(data["pass-exec"])
    times = [data["pass-exec"][i][0] for i in range(data_len)]
    pass_names = [data["pass-exec"][i][1] for i in range(data_len)]

    outliers = parallelbar.progress_starmap(
        check_outliers,
        zip(times, pass_names, repeat(ref_data), repeat(time_col)),
        total=data_len,
    )

    print(Counter(outliers)[True] / len(outliers))
    return (
        Counter(outliers)[True] / len(outliers) >= threshold,
        Counter(outliers)[True] / len(outliers),
    )


"""
Same with get_outliers function but works on a directory of bitcode module files.
Inputs:
- dir_path: absolute path to directory containing bitcode module files
- opt: optimization option
- outlier_threshold: threshold of fraction of function being outlier for all pass to classify as outlier
"""


def preserve_outliers_dir(dir_path: str, opt: str, outlier_threshold=1):
    files = listdir(dir_path)
    fp = parallelbar.progress_starmap(
        join, zip(repeat(dir_path), files), total=len(files)
    )

    data = []
    for f in fp:
        data.append(get_outliers(f, opt, outlier_threshold=outlier_threshold))
        print(f)

    return data


"""
Given path to bitcode module file and a pass name, write new file with 
outlier functions extracted.

Inputs:
- file_path: absolute path to bitcode module file.
- opt: optimization pipeline in {O1,O2,O3,Oz}.
- pass_name: pass name in which outlier threshold used to extract
  outlier functions.
- quantile (optional): percentile used as outlier threshold with range [0,1].
- ref_data (optional): pandas.DataFrame object used as reference for outlier extraction.
- dst (optional): If empty, write file to a directory '_tmp'. Else, write file to directory dst.
- abs_threshold (optional): In seconds, absolute wall time threshold to consider for outlier extraction. 
  Used to minimize noise.

Output:
- If bitcode module file is an outlier, return a tuple
  (number of functions removed, total number of functions in module).
- If bitcode module file is an outlier but unexpected error from retrieving outlier data, returns (-2, -2).
- If pass_name is not in opt time-pass analysis of the file, return (-3,-3).
- If bitcode module file is not outlier, return (0, number of functions).
"""


@ray.remote
def get_outliers_pass_specific(
    file_path: str,
    opt: str,
    pass_name: str,
    quantile: float = 0.95,
    ref_data: pd.DataFrame = None,
    dst="",
    abs_threshold=0.005,
):
    tmp_path = file_path.split("/")
    tmp_path[-2] = "_tmp" if dst == "" else dst
    tmp_path = "/".join(tmp_path)
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)

    if ref_data is None:
        ref_data = pd.read_csv(
            f"pass_runtime/transformations/{opt.lower()}_cpp.csv"
        )  # TODO: abstract this away. currently hard coding transformations pass data

    bc = None
    n_removed = 0
    src_path = file_path

    analysis = parse_pass_analysis_exec(
        src_path, True, True, opt, bitcode_module=None, dict_format=True
    )
    if analysis is not None:
        analysis = analysis["pass-exec"]
    else:
        return None

    groups = ref_data.groupby("pass").quantile(
        q=quantile
    )  # TODO: replace "pass" with parameter

    if pass_name in analysis:
        abs_time, rel_time = analysis[pass_name]
    else:
        return (-3, -3)  # TODO: come up with better error signals

    n_functions = get_n_functions(file_path=file_path)

    if (
        check_outliers(rel_time, pass_name, groups, time_col="rel_time")
        and abs_time >= abs_threshold
    ):
        try:
            for i in range(n_functions):
                if n_removed > 0:
                    src_path = tmp_path
                with open(src_path, mode="rb") as f:
                    bc = f.read()

                tmp = remove_fn_bc(i, bc)
                analysis = parse_pass_analysis_exec(
                    src_path, True, True, opt, tmp, dict_format=True
                )
                if analysis is not None:
                    analysis = analysis["pass-exec"]
                else:
                    return (-2, -2)  # deprecated. should never happen.

                if pass_name in analysis and check_outliers(
                    analysis[pass_name][1], pass_name, groups, time_col="rel_time"
                ):
                    remove_fn(i, src_path, tmp_path)
                    n_removed += 1
                    src_path = tmp_path
            return (n_removed, n_functions)
        except KeyError:
            return (
                -1,
                -1,
            )  # deprecated since if statement above check for this condition

    return (0, n_functions)


"""
Given a directory of all bitcode module files and a pass name, 
output all outlier modules with outlier functions being preserved.

Inputs:
- dir_path: path to directory containing bitcode module files.
- opt: optimization pipeline option in {O1,O2,O3,Oz}.
- pass_name: name of pass.
- quantile (optional): threshold to consider which time being an outlier.
- fp_list (optional): List of bitcode module files to process outlier 
  preservation. Default: get all files in dir_path directory.
- ref_data (optional): pandas.DataFrame object as a reference for 
  getting outlier data from pass_name.
- dst (optional): destination path to write module file with 
  outlier functions preserved to.

Output: dictionary type with key being pass_name and value being a list of 
tuples. Each tuple represents number of functions removed (1st element) 
and total number of functions (2nd element) of a module.
"""


@ray.remote
def preserve_outliers_dir_pass_specific(
    dir_path: str,
    opt: str,
    pass_name: str,
    quantile: float = 0.95,
    fp_list: List = [],
    ref_data: pd.DataFrame = None,
    dst: str = "",
):
    if len(fp_list) > 0:
        fp = fp_list
    else:
        files = listdir(dir_path)
        fp = [join(dir_path, files[i]) for i in range(len(files))]
    if ref_data is not None:
        df = ref_data
    else:
        df = pd.read_csv(
            f"pass_runtime/transformations/{opt.lower()}_cpp.csv"
        )  # TODO: change this
    data = []
    s = time.time()
    results = [
        get_outliers_pass_specific.remote(
            fp[i], opt, pass_name, quantile, ref_data=df, dst=dst
        )
        for i in range(len(fp))
    ]

    unfinished = results
    while unfinished:
        finished, unfinished = ray.wait(unfinished, num_returns=1)
        data.extend(ray.get(finished))
    print(f"{pass_name}: time elapsed={time.time() - s}", flush=True)

    return {pass_name: data}


"""
Check if the number of outlier modules modified fit with the number of outlier modules 
given by `quantile`. 

Inputs:
- dir_path: absolute path to source directory.
- ref_data: pandas.DataFrame
- opt: optimization option.
- quantile (optional): threshold to be considered as outlier for relative time.
- pass_col (optional): label of categorical column storing all pass names in `ref_data`.
- pass_list (optional): passes to check. If empty, check all passes in `ref_data`.
"""


def check_correctness(
    dir_path: str,
    ref_data: pd.DataFrame,
    opt: str,
    quantile: float = 0.95,
    pass_col="pass",
    pass_list=[],
):
    if len(pass_list) != 0:
        passes = pass_list
    else:
        passes = ref_data[pass_col].unique()  # numpy array
    files = listdir(dir_path)
    n_files = len(files)
    fp = [join(dir_path, files[i]) for i in range(len(files))]
    data = {}
    tmp_dir_names = [f"tmp_{''.join(re.split('<|,|>|llvm::|, ', p))}" for p in passes]
    results = [
        preserve_outliers_dir_pass_specific.remote(
            dir_path, opt, passes[i], quantile, fp_list=fp, dst=tmp_dir_names[i]
        )
        for i in range(len(passes))
    ]
    unfinished = results
    while unfinished:
        finished, unfinished = ray.wait(unfinished, num_returns=1)
        result = ray.get(finished[0])
        pass_name = next(iter(result.keys()))
        result_dict = Counter(result[pass_name])
        data[pass_name] = (
            1
            - (
                result_dict[(0, 0)]
                + result_dict[(-1, -1)]
                + result_dict[(-2, -2)]
                + result_dict[(-3, -3)]
            )
            / n_files
        )

    return data


"""
Same as check_outlier, but return if both relative and absolute wall time of bitcode 
module file meet the outlier threshold.

Inputs:
- file_path: path to bitcode module file.
- pass_name: pass name.
- opt: optimization pipeline.
- rel_threshold_value: relative wall time threshold.
- abs_threshold_value: absolute wall time threshold.

Output: True if `pass_name` of bitcode module file in `opt` pipeline meeet both 
relative and absolute wall time threshold. False otherwise.
"""


### RELATIVE TIME DATA
@ray.remote
def check_outliers2(
    file_path: str,
    pass_name: str,
    opt: str,
    rel_threshold_value: float,
    abs_threshold_value: float,
):
    analysis = parse_pass_analysis_exec(
        file_path, True, True, opt, bitcode_module=None, dict_format=True
    )
    analysis_abs = parse_pass_analysis_exec(
        file_path,
        relative=False,
        bitcode_file=True,
        opt=opt,
        bitcode_module=None,
        dict_format=True,
    )
    if analysis is not None and analysis_abs is not None:
        analysis = analysis["pass-exec"]
        analysis_abs = analysis_abs["pass-exec"]
    else:
        return None

    if pass_name in analysis and pass_name in analysis_abs:
        time_rel = analysis[pass_name]
        time_abs = analysis_abs[pass_name]
    else:
        return None

    return time_rel >= rel_threshold_value and time_abs >= abs_threshold_value


"""
Return list of bitcode module files that are outliers for specific pass name.
Inputs:
- file_dir: directory to source module files.
- pass_name: pass name.
- opt: optimization pipeline.
- rel_threshold_value: relative wall time threshold.
- abs_threshold_value: absolute wall time threshold.
- fp (optional): list of bitcode module files. If empty, function processes all files in `file_dir`.
"""


def get_outliers_pass_specific2(
    file_dir: str,
    pass_name: str,
    opt: str,
    rel_threshold_value: float,
    abs_threshold_value: float,
    fp: List = [],
):
    if fp != []:
        files = fp
    else:
        files = listdir(file_dir)

    bools = ray.get(
        [
            check_outliers2.remote(
                join(file_dir, file),
                pass_name,
                opt,
                rel_threshold_value,
                abs_threshold_value,
            )
            for file in files
        ]
    )

    return [files[fi] for fi in range(len(files)) if bools[fi] is True]

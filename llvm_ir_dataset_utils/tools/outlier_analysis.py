import subprocess
from collections import Counter
import os
from os import listdir
from os.path import isfile, join
from typing import List, Union, Callable
import pandas as pd

import parallelbar
from itertools import repeat

from opt_analysis_tools import parse_pass_analysis_exec, read_data_bc

# Source: https://codegolf.stackexchange.com/questions/4707/outputting-ordinal-numbers-1st-2nd-3rd#answer-4712
ordinal = lambda n: "%d%s" % (
    n,
    "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4],
)

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
    command = [
        "/p/lustre1/khoidng/LLVM/build/bin/opt",
        f"-passes=remove-fn-body<i={i}>",
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
    if i == -1:
        print("Currently not supporting i == -1")
        return None
    try:
        with subprocess.Popen(
            ["/p/lustre1/khoidng/LLVM/build/bin/opt", f"-passes=remove-fn-body<i={i}>"],
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
            [
                "/p/lustre1/khoidng/LLVM/build/bin/opt",
                "-passes=remove-fn-body<i=-1>",
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
        [
            "/p/lustre1/khoidng/LLVM/build/bin/opt",
            "-passes=remove-fn-body<i=-1>",
            "-S",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
    ) as proc:
        return proc.communicate(input=bitcode_module)[0].decode("utf-8")


"""
- outlier_check_fn: must be a callable function. Requires at least time analysis data and ref_data as arguments.
                    must return True if outlier, and False otherwise.
- Return: number of functions removed, total number of functions, average fraction of passes being outliers if ith function is removed
"""


def get_outliers(file_path: str, opt: str, outlier_threshold=1, quantile=0.95):
    n_functions = get_n_functions(file_path=file_path)

    tmp_path = file_path.split("/")
    tmp_path[-2] = "_tmp"
    tmp_path = "/".join(tmp_path)
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)

    ref_data = pd.read_csv(
        f"{opt.lower()}_cpp.csv"
    )  # TODO: filename needs to be abstracted away!

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

        # pd.DataFrame consisting of quantiles grouped by passes
        groups = ref_data.groupby("pass").quantile(
            q=quantile
        )  # TODO: put this outside of the loop

        # if removed function still results in module being in outlier range,
        # delete that function because it doesn't affect the outliers
        # (minimize functions in module such that outliers are preserved)

        outlier_status, fraction_outlier = is_outlier(
            time_analysis_tmp, ref_data=groups, threshold=outlier_threshold
        )

        if outlier_status:
            remove_fn(i, src_path, tmp_path)
            # print(f"removed {ordinal(i)} function as non-outlier")
            n_removed += 1
            src_path = tmp_path

        print(f"i: {i}. n_removed: {n_removed}. src_path={src_path}")
        fraction_outliers.append(fraction_outlier)
    # print(f"{n_removed}/{n_functions} functions are removed.")
    # print(get_ir(bc))
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
    quantile=0.95,
    pass_col="pass",
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

    # # check for all passes in data
    # for i in range(len(data["pass-exec"])):
    #     time, pass_name = data["pass-exec"][i]
    #     tmp = ref_data.loc[ref_data[pass_col] == pass_name]
    #     outliers.append(time > tmp[time_col].quantile(q=quantile))

    print(Counter(outliers)[True] / len(outliers))
    return (
        Counter(outliers)[True] / len(outliers) >= threshold,
        Counter(outliers)[True] / len(outliers),
    )
    # return Counter(outliers)[True] / len(outliers) >= threshold


"""
Same with get_outliers function but works on a directory of bitcode module files.
Inputs:
- dir_path: absolute path to directory containing bitcode module files
- opt: optimization option
- outlier_threshold: threshold of fraction of function being outlier for all pass to classify as outlier
"""


def preserve_outliers_dir(dir_path: str, opt: str, outlier_threshold=1):
    # bc_module_files = [f for f in listdir(dir_path) if isfile(join(dir_path, f))]
    # for f in bc_module_files:
    #     fp = join(dir_path, f)
    #     get_outliers(fp, opt)
    #     print(f"Finished processing file: {f}")

    files = listdir(dir_path)
    fp = parallelbar.progress_starmap(
        join, zip(repeat(dir_path), files), total=len(files)
    )
    # data = parallelbar.progress_starmap(
    #     get_outliers,
    #     zip(fp, repeat(opt), repeat(outlier_threshold)),
    #     total=len(files),
    # )

    data = []
    for f in fp:
        data.append(get_outliers(f, opt, outlier_threshold=outlier_threshold))
        print(f)

    return data


def get_outliers_pass_specific(
    file_path: str, opt: str, pass_name: str, quantile: float = 0.95
):
    tmp_path = file_path.split("/")
    tmp_path[-2] = "_tmp"
    tmp_path = "/".join(tmp_path)
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)

    ref_data = pd.read_csv(f"{opt.lower()}_cpp.csv")  # TODO: optimize this away

    bc = None
    n_removed = 0
    src_path = file_path

    analysis = parse_pass_analysis_exec(
        src_path, True, True, opt, bitcode_module=None, dict_format=True
    )

    if analysis is not None:
        analysis = analysis["pass-exec"]
    else:
        # print("[get_outliers_pass_specified] parse_pass_analysis_exec returns None!")
        return None

    groups = ref_data.groupby("pass").quantile(q=quantile)

    if pass_name in analysis:
        time = analysis[pass_name]
    else:
        # print(f"There's no {pass_name} in this module!")
        return (-3, -3)  # TODO: come up with better error signals

    # print(
    #     f"Initial checking if {pass_name} with time={time} is an outlier in this module..."
    # )
    if check_outliers(time, pass_name, groups):  # is an outlier
        # print(
        #     f"{pass_name} is an outlier ({time} >= {ordinal(int(quantile*100))} quantile={groups.loc[pass_name]['fraction_total_time']})"
        # )
        n_functions = get_n_functions(file_path=file_path)
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
                    # print("[inside for loop] parse_pass_analysis_exec returns None!")
                    return (-2, -2)
                if check_outliers(analysis[pass_name], pass_name, groups):
                    remove_fn(i, src_path, tmp_path)
                    n_removed += 1
                    src_path = tmp_path
                # print(f"i: {i}. n_removed: {n_removed}. src_path={src_path}")
            return (n_removed, n_functions)
        except KeyError as e:
            # print(f"KeyError: arguments {e.args}")
            return (-1, -1)
    # print(
    #     f"{pass_name} is not outlier for bitcode module file {file_path} (outlier={groups.loc[pass_name]['fraction_total_time']})"
    # )
    return (0, 0)


def preserve_outliers_dir_pass_specific(
    dir_path: str, opt: str, pass_name: str, quantile: float = 0.95, fp_list: List = []
):
    if len(fp_list) > 0:
        fp = fp_list
    else:
        files = listdir(dir_path)
        fp = parallelbar.progress_starmap(
            join, zip(repeat(dir_path), files), total=len(files)
        )
    data = parallelbar.progress_starmap(
        get_outliers_pass_specific,
        zip(fp, repeat(opt), repeat(pass_name), repeat(quantile)),
        total=len(fp),
    )

    return data


def check_correctness(
    dir_path: str, ref_data: str, opt: str, quantile: float = 0.95, pass_col="pass"
):
    # 1. get all the passes
    # 2.1 for each pass, run preserve_outliers_dir_pass_specific
    # 2.2 during each pass in 2.1, calculate Q = N files in _tmp / N files total
    # 2.3 add Q, and whether |Q| > 5% (error of percentile), into a list

    # assume ref_data is df of O{1,2,3,z} optimization
    passes = ref_data[pass_col].unique()  # numpy array
    files = listdir(dir_path)
    n_files = len(files)
    fp = parallelbar.progress_starmap(join, zip(repeat(dir_path), files), total=n_files)
    data = {}
    for p in passes:
        print(f"\n{p}:\n")
        result = preserve_outliers_dir_pass_specific(
            dir_path, opt, p, quantile, fp_list=fp
        )
        result_dict = Counter(result)
        data[p] = (
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


def permutations():
    pass

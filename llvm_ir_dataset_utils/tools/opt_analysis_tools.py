""" Tools working with llvm-opt output data """

from typing import Union

from os import listdir
from os.path import isfile, isdir, join
import subprocess

from textwrap import fill

import json
import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import random

from datasets import load_dataset

from itertools import repeat
import parallelbar
from yaspin import yaspin

OPT_O3_PASS_LIST = [
    "Annotation2MetadataPass",
    "ForceFunctionAttrsPass",
    "InferFunctionAttrsPass",
    "CoroEarlyPass",
    "LowerExpectIntrinsicPass",
    "SimplifyCFGPass",
    "SROAPass",
    "EarlyCSEPass",
    "CallSiteSplittingPass",
    "OpenMPOptPass",
    "IPSCCPPass",
    "CalledValuePropagationPass",
    "GlobalOptPass",
    "PromotePass",
    "InstCombinePass",
    "SimplifyCFGPass",
    "RequireAnalysisPass<llvm::GlobalsAA, llvm::Module>",
    "InvalidateAnalysisPass<llvm::AAManager>",
    "RequireAnalysisPass<llvm::ProfileSummaryAnalysis, llvm::Module>",
    "InlinerPass",
    "InlinerPass",
    "PostOrderFunctionAttrsPass",
    "ArgumentPromotionPass",
    "OpenMPOptCGSCCPass",
    "SROAPass",
    "EarlyCSEPass",
    "SpeculativeExecutionPass",
    "JumpThreadingPass",
    "CorrelatedValuePropagationPass",
    "SimplifyCFGPass",
    "InstCombinePass",
    "AggressiveInstCombinePass",
    "LibCallsShrinkWrapPass",
    "TailCallElimPass",
    "SimplifyCFGPass",
    "ReassociatePass",
    "RequireAnalysisPass<llvm::OptimizationRemarkEmitterAnalysis, llvm::Function>",
    "LoopSimplifyPass",
    "LCSSAPass",
    "LoopInstSimplifyPass",
    "LoopSimplifyCFGPass",
    "LICMPass",
    "LoopRotatePass",
    "SimpleLoopUnswitchPass",
    "SimplifyCFGPass",
    "InstCombinePass",
    "LCSSAPass",
    "LoopIdiomRecognizePass",
    "IndVarSimplifyPass",
    "LoopDeletionPass",
    "LoopFullUnrollPass",
    "SROAPass",
    "VectorCombinePass",
    "MergedLoadStoreMotionPass",
    "GVNPass",
    "SCCPPass",
    "BDCEPass",
    "InstCombinePass",
    "JumpThreadingPass",
    "CorrelatedValuePropagationPass",
    "ADCEPass",
    "MemCpyOptPass",
    "DSEPass",
    "LCSSAPass",
    "CoroElidePass",
    "SimplifyCFGPass",
    "InstCombinePass",
    "CoroSplitPass",
    "InlinerPass",
    "InlinerPass",
    "PostOrderFunctionAttrsPass",
    "ArgumentPromotionPass",
    "OpenMPOptCGSCCPass",
    "CoroSplitPass",
    "InvalidateAnalysisPass<llvm::ShouldNotRunFunctionPassesAnalysis>",
    "DeadArgumentEliminationPass",
    "CoroCleanupPass",
    "GlobalOptPass",
    "GlobalDCEPass",
    "EliminateAvailableExternallyPass",
    "ReversePostOrderFunctionAttrsPass",
    "RecomputeGlobalsAAPass",
    "Float2IntPass",
    "LowerConstantIntrinsicsPass",
    "LCSSAPass",
    "LoopDistributePass",
    "InjectTLIMappings",
    "LoopVectorizePass",
    "LoopLoadEliminationPass",
    "InstCombinePass",
    "SimplifyCFGPass",
    "SLPVectorizerPass",
    "VectorCombinePass",
    "InstCombinePass",
    "LoopUnrollPass",
    "WarnMissedTransformationsPass",
    "SROAPass",
    "InstCombinePass",
    "RequireAnalysisPass<llvm::OptimizationRemarkEmitterAnalysis, llvm::Function>",
    "LCSSAPass",
    "AlignmentFromAssumptionsPass",
    "LoopSinkPass",
    "InstSimplifyPass",
    "DivRemPairsPass",
    "TailCallElimPass",
    "SimplifyCFGPass",
    "GlobalDCEPass",
    "ConstantMergePass",
    "CGProfilePass",
    "RelLookupTableConverterPass",
    "AnnotationRemarksPass",
    "VerifierPass",
    "BitcodeWriterPass",
]

""" Parse each line of pass execution timing report
    Assumed each data line is the same formatting.
    input: line of string containing analysis data
    output: list of parsed floats & strings containing times, time 
    percentages, and pass name of the line input
    
    Line format example:
    '0.0066 ( 26.1%)   0.0003 ( 11.9%)   0.0070 ( 24.7%)   0.0070 ( 24.0%)  InstCombinePass'
    
    return: result = [usertime, systime, usrsystime, walltime, 'passname']
"""


def extract_alphanum(line: str) -> list:
    result = []

    len_line = len(line)
    start = 0
    string = ""
    alpha = 0

    for i in range(len_line):
        c = line[i]
        if c == " " and not start:  # trailing space at start
            continue
        if c.isdigit() or c == ".":  # extract value (without percentage)
            string += c
            start = 1
        elif c == "%":  # convert percentage value into decimal
            string = str(float(string) / 100)
        elif c.isalpha():  # name of the pass
            string += c
            start = 1
            alpha = 1
        elif c == " ":
            if not alpha:
                start = 0
                result.append(string)
                string = ""
                alpha = 0
            else:  # assuming end of pass name == end of line
                string += c
        else:  # special chars
            if c != "(" and c != ")":
                string += c  # for name pass with special chars
            continue

    result.append(string)  # append the name pass
    try:
        r_len = len(result)
        for i in range(r_len):
            if i != r_len - 1:
                result[i] = float(result[i])
    except ValueError:
        print("Wrong value. Debug: ", line)
        return None
    return result


def find_start_line(data):
    rows = len(data)
    for i in range(rows):
        if "===" in data[i][:3]:
            return i + 6
    print(data)
    return None


""" Extract wall time and pass name from each extracted line of data
"""


def extract_wall_pass_name(
    line_data: list[Union[float, str]], relative: bool, total_wall_time: float
):
    # return [
    #     line_data[-2] if relative else total_wall_time * line_data[-2],
    #     line_data[-1],
    # ]

    return [
        line_data[-2] * total_wall_time,
        line_data[-2],
        line_data[-1],
    ]  # [abs_time, rel_time, pass_name]


""" Parse section with line line_start (first line containing the correct line input format)
"""


def parse_section(
    data: list[str], line_start: int, relative: bool, dict_format: bool = False
):
    total_wall_time = 0.0
    last_section_line = 0  # line contains total time results for pass execution section

    # find total
    for i in range(line_start, len(data)):
        line_data = extract_alphanum(data[i])
        if line_data is None:
            print("DEBUG parse_section, line:", i)
            return None, None
        if line_data[-1] == "Total":
            total_wall_time = line_data[-3]
            last_section_line = i
            break

    # extract data
    try:
        data = data[line_start:last_section_line]
        tmp = [extract_alphanum(d) for d in data]
        if dict_format:
            result = {}
            for t in tmp:
                abs_time, rel_time, pass_name = extract_wall_pass_name(
                    t, relative, total_wall_time
                )
                result[pass_name] = [abs_time, rel_time]
        else:
            result = [extract_wall_pass_name(t, relative, total_wall_time) for t in tmp]

    except IndexError:
        print("Index out of range!")
        return None, None
    return result, last_section_line


""" Parse pass and analysis execution timing sections
    input: output_file_path: path to output file
    output: dict{'pass-exec': list[float, float, float, str], 
                 'analysis-exec': list[float, float, float, str]} 
"""


def parse_pass_analysis_exec(
    output_file_path: str,
    relative: bool,
    bitcode_file: bool,
    opt: str,
    bitcode_module=None,
    dict_format=False,
):
    opt_option = {"O3", "O2", "O1", "Oz"}
    if opt not in opt_option:
        print(f"{opt} not a valid optimization option")
        return None
    try:
        if bitcode_module is not None:
            data = read_data_bc(bitcode_module, opt).split("\n")
        else:
            data = read_data(output_file_path, bitcode_file, opt).split("\n")

        result = {"pass-exec": None, "analysis-exec": None}

        line_start = find_start_line(data)
        if line_start is None:
            print("line start is none")
            return None

        result["pass-exec"], pass_end_line = parse_section(
            data, line_start, relative, dict_format=dict_format
        )
        if pass_end_line is None:
            print("Something's wrong. Check file:", output_file_path)
            return None
        result["analysis-exec"], _ = parse_section(
            data, pass_end_line + 8, relative, dict_format=dict_format
        )

        return result

    except FileNotFoundError:
        print("File not found. Make sure path to file exists")
        return None


"""
Read opt data from file
Inputs:
- file_path: Path to .bc/.ll file
- bitcode_file: True if file is of .bc extension. False if file is of .ll extension.
- opt: Optimization option (O1,O2,O3,Oz, etc.)

Output:
- String of all opt --time-passes and --stats data gathered from source file.
"""


def read_data(file_path: str, bitcode_file: bool, opt: str):
    command = [
        "opt",
        "-" + opt,
        "--stats",
        "--disable-output",
        "--time-passes",
    ]  # TODO: replace the hardcoded opt path with something more flexible
    if bitcode_file:
        bc = None
        with open(file_path, mode="rb") as f:
            bc = f.read()
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        ) as proc:
            stdout = proc.communicate(input=bc)[0].decode("utf-8")
            return stdout
    else:
        with open(file_path, mode="r", encoding="utf-8") as f:
            return f.read()


def read_data_bc(bitcode_module, opt: str):
    command = [
        "opt",
        "-" + opt,
        "--stats",
        "--disable-output",
        "--time-passes",
    ]
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
    ) as proc:
        stdout = proc.communicate(input=bitcode_module)[0].decode("utf-8")
        return stdout


def sampling_fp_helper(files: list[str], r: list[int]):
    result = []
    for i in r:
        result.append(files[i])
    return result


""" Return wall time from n random samples
"""


def sampling(
    dir_path: str,
    n: int,
    relative: bool = False,
    bitcode_file: bool = False,
    opt: str = "O3",
):
    wall_time = {k: [] for k in OPT_O3_PASS_LIST}
    passes = set(OPT_O3_PASS_LIST)
    files = listdir(dir_path)
    r = random.sample(range(len(files) - 1), n)
    failed = 0
    fp = parallelbar.progress_starmap(
        join, zip(repeat(dir_path), files), total=len(files)
    )
    fp = sampling_fp_helper(fp, r)
    data = parallelbar.progress_starmap(
        parse_pass_analysis_exec,
        zip(fp, repeat(relative), repeat(bitcode_file), repeat(opt)),
        total=n,
    )

    for d in data:
        if d is None:
            failed += 1
            continue
        pass_exec_data = d["pass-exec"]
        n_passes = len(pass_exec_data)

        for i in range(n_passes):
            pass_name = pass_exec_data[i][-1]
            if pass_name not in passes:
                wall_time[pass_name] = [pass_exec_data[i][-2]]
            else:
                wall_time[pass_name].append(pass_exec_data[i][-2])
    print(
        f"{n-failed}/{n} files have successfully sampled ({round((n-failed)/n * 100,2)}% success rate)."
    )
    return wall_time


### CSV format for sampling
def sampling_csv(
    dir_path: str,
    n: int,
    relative: bool = False,
    bitcode_file: bool = False,
    opt: str = "O3",
    data_type: str = "pass-exec",
):
    files = listdir(dir_path)
    r = random.sample(range(len(files)), n)
    print("Getting all file name...")
    fp = parallelbar.progress_starmap(
        join, zip(repeat(dir_path), files), total=len(files)
    )
    fp = sampling_fp_helper(fp, r)
    print("Extracting data...")
    data = parallelbar.progress_starmap(
        parse_pass_analysis_exec,
        zip(fp, repeat(relative), repeat(bitcode_file), repeat(opt)),
        total=n,
    )

    result = []
    for d in data:
        if d is not None:
            result.extend(d[data_type])
    return result


"""
source_dir: source directory of bitcode files
fp: name for output csv file
nsamples: number of files to sample
ncols: number of columns for output file table
relative (deprecated, don't use): output whether data table is relative time or absolute time
col_labels: list of labels for the output data table (recommend: []abs_time, rel_time, pass])
bitcode_file: whether type of files in source_dir bitcode file
opt: optimization pipeline
data_type: output transformation pass ('pass-exec') or analysis pass ('analysis-exec') data
"""


def sample_then_export_csv(
    source_dir: str,
    fp: str,
    nsamples: int,
    ncols: int,
    col_labels: list[str],
    relative: bool = False,
    bitcode_file: bool = False,
    opt: str = "O3",
    data_type: str = "pass-exec",
):
    assert ncols == len(col_labels)
    o = sampling_csv(source_dir, nsamples, relative, bitcode_file, opt, data_type)
    return export_to_csv(o, fp, ncols, col_labels)


def export_to_json(data: Union[str, list[float]], fn: str = "", indent: int = 2):
    out = json.dumps(data, indent=indent)
    name = fn if fn != "" else "json_file.json"
    with open(name, "w") as f:
        f.write(out)


def import_from_json(file_path: str, encoding: bool = False):
    decoding_scheme = [None, lambda pairs: {int(k): v for k, v in pairs}]
    data = None
    with open(file_path) as f:
        data = json.load(f, object_pairs_hook=decoding_scheme[int(encoding)])
    return data


def export_to_csv(
    data: list[list[Union[str, float]]], fp: str, ncols: int, col_labels: list[str]
):
    print("Checking data validity...")
    if not (isinstance(data, list) and all(isinstance(d, list) for d in data)):
        print("Data is not valid type")
        return None

    if len(col_labels) != len(data[0]):
        print("Number of labels must be equal to number of columns")
        return None

    print("Exporting as csv...")
    with open(fp, "w", newline="") as f:
        o = csv.writer(f)
        o.writerow(col_labels)
        o.writerows(data)
    print("Exported successfully!")
    return 0


def convert_to_csv_struct_helper(k: str, v: float) -> list[Union[str, float]]:
    return [k, v]


def convert_to_csv_struct(
    data: Union[str, list[float]]
) -> list[list[Union[str, float]]]:
    result = []
    keys = list(data.keys())
    for k in keys:
        n = len(data[k])
        if n == 0:
            print("Skipped:", k)
            continue  # likely this version doesn't have empty labels (labels have no data on)
        print("Processing:", k)
        result.extend(
            parallelbar.progress_starmap(
                convert_to_csv_struct_helper, zip(repeat(k), data[k]), total=n
            )
        )
    return result


def plot(  # deprecated
    samples: Union[str, list[float]],
    export_png: str = "",
    xlabel="",
    ylabel="",
    labelsize=10,
):
    sns.set(style="darkgrid")
    ax = sns.violinplot(data=samples, orient="h", split=True, inner="quart")
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.tick_params(labelsize=labelsize)

    if (
        export_png != ""
    ):  # if not empty string, export png with that string value as file name
        plt.savefig(export_png + ".png")


"""
Plot histograms of time distribution of passes from pandas.DataFrame input object
Inputs:
- df: pandas.DataFrame object. Should have one category column (pass name) and numerical column (time).
- num_col: label of numerical column.
- cat_col: label of category column.
- ncols: number of columns of histogram plots to display in the figure.
- suptitle (optional): Suptitle of figure.
- fontsize (optional): fontsize of labels in all plots.
- title_size (optional): Size of suptitle.
- save (optional): File name of figure to be saved. No saving/exporting figure if argument is empty.
- passes (optional): List of passes to plot. If empty, plot all passes available in df.
- figsize (optional): Size of figure.
"""


def plot_df(
    df: pd.DataFrame,
    num_col: str,
    cat_col: str,
    ncols: int = 4,
    suptitle="",
    fontsize=20,
    title_size=12,
    save: str = "",
    passes=[],
    figsize=(15, 30),
):
    if passes != []:
        group_values = passes
    else:
        group_values = list(pd.unique(df[cat_col]))

    # calculate number of rows in the plot
    nrows = len(group_values) // ncols + (len(group_values) % ncols > 0)

    # Define the plot
    plt.figure(figsize=figsize)
    plt.subplots_adjust(hspace=0.9)
    plt.suptitle(suptitle, y=0.95)

    for n, col in enumerate(group_values):
        try:
            # add a new subplot at each iteration using nrows and cols
            ax = plt.subplot(nrows, ncols, n + 1)

            # Filter the dataframe data for each state
            df_temp = df[df[cat_col] == col]
            df_temp[num_col].hist(ax=ax, bins=50)
            if len(df_temp) > 1:
                ax2 = df_temp[num_col].plot.kde(
                    ax=ax, secondary_y=True, fontsize=fontsize, title=col
                )
                ax2.set_xlim(left=0)

            # chart formatting
            ax.tick_params(labelsize=fontsize)
            ax.set_title(fill(col, 40), size=title_size)
            ax.set_xlabel("% of total time", fontsize=fontsize)
            if n % ncols == 0:
                ax.set_ylabel("Frequency", fontsize=fontsize)
            else:
                ax.set_ylabel("")
        except ValueError:  # continue with the loop
            print(col, "only has 1 value. Ignoring...")
            pass

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    if save != "":
        plt.savefig(save)


def sort_data(data: Union[str, list[float]]):
    sorted_keys = sorted(list(data.keys()))
    result = {k: data[k] for k in sorted_keys}
    return result


def cat_encode(data: Union[str, list[float]]):
    sorted_keys = sorted(list(data.keys()))
    encoding = {k: v for (k, v) in enumerate(sorted_keys, 0)}
    result = {k: data[v] for (k, v) in enumerate(sorted_keys, 0)}
    return (result, encoding)


def download_bitcode(target_dir: str, languages: list[str], n: int = -1, random=False):
    if not isinstance(languages, list):
        print("languages arg has to be list type")
        return 1
    if not isdir(target_dir):
        print(f"{target_dir} is not a directory!")
        return 1
    if len(languages) > 5:
        print(f"Maximum number of languages is 5! (Current arg: {len(languages)})")
        return 1

    available_langs = {"cpp", "c", "rust", "swift", "julia"}
    for i in languages:
        if i not in available_langs:
            print(f"{i} is not available to download")
            return 1
    lang_set = set(languages)

    # download
    ds = load_dataset("llvm-ml/ComPile", split="train", streaming=True)
    print("Successfully loaded dataset!")
    ds_iter = iter(ds)
    row = next(ds_iter)
    print("converted to python iterable")
    counter = 0
    spin_text = "Downloading bitcode files"

    with yaspin(text=spin_text) as sp:
        while (n != -1 and counter < n) or (row is not None and n == -1):
            if row["language"] in lang_set:
                fn = f"bc{counter}.bc"
                full_path = target_dir + "/" + fn
                if isfile(full_path):
                    row = next(ds_iter)
                    continue
                with open(full_path, "wb") as f:
                    f.write(row["content"])
                if counter % 500 == 0 and counter > 0:
                    sp.write(f"> {counter} downloaded")
                counter += 1
            row = next(ds_iter)

    print(f"{counter} bitcode files have been downloaded to directory {target_dir}.")
    return 0

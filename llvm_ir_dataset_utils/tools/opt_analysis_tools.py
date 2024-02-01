""" Tools working with llvm-opt output data (O3 optimization)."""

from typing import Union

from os import listdir
from os.path import isfile, isdir, join

import json
import subprocess
import seaborn as sns
import matplotlib.pyplot as plt
import random

from datasets import load_dataset

from yaspin import yaspin
from alive_progress import alive_bar

from multiprocessing import Pool
from itertools import repeat
import parallelbar

pool = Pool()

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
    return [
        line_data[-2] if relative else total_wall_time * line_data[-2],
        line_data[-1],
    ]


""" Parse section with line line_start (first line containing the correct line input format)
"""


def parse_section(data: list[str], line_start: int, relative: bool):
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
    result = [[]] * (last_section_line - line_start)
    try:
        # for i in range(line_start, last_section_line):
        #    line_data = extract_alphanum(data[i])
        #    tmp = [  # get time by multiplying by fraction for higher precision
        #        line_data[-2] if relative else total_wall_time * line_data[-2],
        #        line_data[-1],
        #    ]
        #    result[i - line_start] = tmp
        tmp = pool.map(extract_alphanum, data[line_start:last_section_line])
        # print(tmp)
        # result = [helper(tmp[i]) for i in range(len(tmp))]
        result = pool.starmap(
            extract_wall_pass_name, zip(tmp, repeat(relative), repeat(total_wall_time))
        )
    except IndexError:
        print("Index out of range!")
        print("DEBUG parse_section: index", i, "line:", line_data)
        return None, None
    return result, last_section_line


""" Parse pass and analysis execution timing sections
    input: output_file_path: path to output file
    output: dict{'pass-exec': list[float, float, float, str], 
                 'analysis-exec': list[float, float, float str]} 
"""


def parse_pass_analysis_exec(
    output_file_path: str, relative: bool, bitcode_file: bool, opt: str
):
    opt_option = {"O3", "O2", "O1", "Oz"}
    if opt not in opt_option:
        print(f"{opt} not a valid optimization option")
        return None
    try:
        data = read_data(output_file_path, bitcode_file, opt).split("\n")
        result = {"pass-exec": None, "analysis-exec": None}
        line_start = find_start_line(data)
        if line_start is None:
            print("line start is none")
            return None
        result["pass-exec"], pass_end_line = parse_section(data, line_start, relative)
        if pass_end_line is None:
            print("Something's wrong. Check file:", output_file_path)
            return None
        result["analysis-exec"], _ = parse_section(data, pass_end_line + 8, relative)

        return result

    except FileNotFoundError:
        print("File not found. Make sure path to file exists")
        return None


def read_data(file_path: str, bitcode_file: bool, opt: str):
    command = [
        "/p/lustre1/khoidng/LLVM/build/bin/opt",
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


def sampling_fp_helper():
    pass


""" Return wall time from n random samples
"""


def sampling(
    dir_path: str,
    n: int,
    relative: bool = False,
    bitcode_file: bool = False,
    opt: str = "O3",
):
    # available_pass_list = import_pass_from_file('./opt_passes.txt')
    wall_time = {k: [] for k in OPT_O3_PASS_LIST}
    passes = set(OPT_O3_PASS_LIST)
    files = listdir(dir_path)
    r = random.sample(range(len(listdir(dir_path)) - 1), n)
    failed = 0

    # fp = pool.starmap(join, zip(repeat(dir_path), files))  # list of file paths
    # data = pool.starmap(
    #    parse_pass_analysis_exec,
    #    zip(fp, repeat(relative), repeat(bitcode_file), repeat(opt)),
    # )
    with alive_bar(n) as bar:
        for i in r:
            fp = join(dir_path, files[i])
            if not isfile(fp):
                failed += 1
            else:
                data = parse_pass_analysis_exec(fp, relative, bitcode_file, opt)
                if data is None:  # wrong files & format
                    failed += 1
                    continue
                pass_exec_data = data["pass-exec"]
                n_passes = len(pass_exec_data)

                for i in range(n_passes):
                    pass_name = pass_exec_data[i][-1]
                    if pass_name not in passes:
                        wall_time[pass_name] = [pass_exec_data[i][-2]]
                    else:
                        wall_time[pass_name].append(pass_exec_data[i][-2])
            bar()
    print(
        f"{n-failed}/{n} files have successfully sampled ({round((n-failed)/n * 100,2)}% success rate)."
    )
    return wall_time


def export_pass_name(pass_collection: list[str], fp, append=True):
    # append_cond = lambda append: 'a' if append else 'w'
    def append_cond(append):
        if append:
            return "a"
        return "w"

    with open(fp, append_cond) as f:
        for i in pass_collection:
            f.write(i)
            f.write("\n")
    return 0


def import_pass_from_file(fp, delimeter="\n"):
    data = None
    with open(fp, "r") as f:
        data = f.read().split(delimeter)
    return data


def export_to_json(data: Union[str, list[float]], fn="", indent=2):
    out = json.dumps(data, indent=indent)
    name = fn if fn != "" else "json_file.json"
    with open(name, "w") as f:
        f.write(out)


def import_from_json(file_path: str):
    data = None
    with open(file_path) as f:
        data = json.load(
            f, object_pairs_hook=lambda pairs: {int(k): v for k, v in pairs}
        )
    return data


def plot(
    samples: Union[str, list[float]],
    export_png: str = "",
    kind="point",
    size: int = 5,
    xlabel="",
    ylabel="",
    labelsize=5,
):
    sns.set(style="darkgrid")
    plt.figure(figsize=(12, 10))
    ax = sns.catplot(data=samples, kind=kind)
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.tick_params(labelsize=labelsize)
    if (
        export_png != ""
    ):  # if not empty string, export png with that string value as file name
        plt.savefig(export_png + ".png")


def sort_data(data: Union[str, list[float]]):
    sorted_keys = sorted(list(data.keys()))
    result = {k: data[k] for k in sorted_keys}
    return result


def cat_encode(data: Union[str, list[float]]):
    sorted_keys = sorted(list(data.keys()))
    encoding = {k: v for (k, v) in enumerate(sorted_keys, 0)}
    result = {k: data[v] for (k, v) in enumerate(sorted_keys, 0)}
    return (result, encoding)


def stats_counter():
    pass


def download_bitcode(target_dir: str, languages: list[str], n: int = -1):
    if isinstance(languages, list):
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


# sns.set(style='darkgrid')
# ax = sns.catplot(sorted_data, s=10, height=5, aspect=3)
# ax.set(xlabel='pass', ylabel='fraction of total time')
# ax.tick_params(labelsize=10)
# ax.set_yticklabels(rotation=0)
# ax.set_xticklabels(rotation=90)

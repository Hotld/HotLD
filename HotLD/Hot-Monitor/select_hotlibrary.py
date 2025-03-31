import sys
import subprocess
import json
import ast
import copy
import os
from parse_optimized_perfdata import *
from parse_hotlibrary import *
from compare_workload_features import *
from tabulate import tabulate


def execute_command(command: str):
    try:
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"执行命令时出错: {stderr}")

        return stdout
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return None


def parse_mapinfo_file(file_path):
    parsed_data = {}

    with open(file_path, "r") as file:
        for line in file:
            parts = line.strip().split()
            if len(parts) != 4:
                continue

            index = int(parts[0])
            ht_path = parts[1]
            json_path = parts[2]
            address = parts[3]

            parsed_data[index] = {
                "ht_path": ht_path,
                "json_path": json_path,
                "address": int(address, 16)
            }

    return parsed_data


def get_hotlibrary_infos(mapinfo_data):
    hotlibrary_map_infos = {}
    for index, files in mapinfo_data.items():
        hotlibrary_path = files["ht_path"]
        header = get_hotlibrary_header(hotlibrary_path)

        depend_table = get_hotlibrary_depend_table(hotlibrary_path)

        ht_map_range = (files["address"], files["address"]+header.text_size)
        ht_map_start = ht_map_range[0]
        hotlibrary_map_infos[str(ht_map_range)] = {}
        hotlibrary_map_infos[str(ht_map_range)]["index"] = index

        cfg_file = files["json_path"]
        with open(cfg_file, 'r') as f:
            config_data = json.load(f)
            symbol_infos = config_data["symbols_info"]

        map_symbol_infos = {}
        for lib in symbol_infos.keys():

            # Get the memory-mapped address of hot library functions
            cur_hotbbs_symbols = symbol_infos[lib]["hot_bbs"]
            cur_hotbbs_start = depend_table[lib].hotbbs_start
            for addresses, name in cur_hotbbs_symbols.items():
                tuple_address = ast.literal_eval(addresses)
                modified_address = (
                    tuple_address[0]+ht_map_start+cur_hotbbs_start, tuple_address[1]+ht_map_start+cur_hotbbs_start)
                map_symbol_infos[str(modified_address)] = name

            cur_coldbbs_symbols = symbol_infos[lib]["cold_bbs"]
            cur_coldbbs_start = depend_table[lib].coldbbs_start
            for addresses, name in cur_coldbbs_symbols.items():
                tuple_address = ast.literal_eval(addresses)
                modified_address = (
                    tuple_address[0]+ht_map_start+cur_coldbbs_start, tuple_address[1]+ht_map_start+cur_coldbbs_start)
                map_symbol_infos[str(modified_address)] = name

        hotlibrary_map_infos[str(ht_map_range)
                             ]["symbol_infos"] = map_symbol_infos

    return hotlibrary_map_infos


def print_results_as_table(mapinfo_data, total_result):
    headers = ["HT Path", "Func Call similarity",
               "Func Time similarity", "Total"]
    table = []

    for i in range(len(total_result)):
        ht_path = mapinfo_data[i]['ht_path']
        row = [ht_path] + list(total_result[i])
        table.append(row)

    return tabulate(table, headers=headers, tablefmt="grid")


def select_hotlibrary(perf_data, mapinfo_data, hotlibrary_mapinfos, threshold):
    perf_script_commond = f"perf script -i {perf_data} -F -tid,-time,-comm --no-demangle"
    perf_output = execute_command(perf_script_commond)

    result, total_cycle = process_file_from_string(perf_output)

    symbol_dict, duplicate_names = convert_dict_by_symbol(
        result, total_cycle, hotlibrary_mapinfos)
    selected_hot_symbol = filter_dict(symbol_dict, threshold)

    duplicate_names = {key: duplicate_names[key] for key in (
        duplicate_names.keys() & selected_hot_symbol.keys())}

    # Compare the characteristics of current workload with HotLibs
    workload_pairs = {}
    for key, vaules in mapinfo_data.items():
        cfg_path = vaules['json_path']
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg_data = json.load(f)
            workload2_path = cfg_data['workload_features']
            ori_libraries = cfg_data["hot_library"]

        with open(workload2_path, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        data2 = filter_dict(data2, threshold)

        data1 = copy.deepcopy(selected_hot_symbol)
        for sym, vals in duplicate_names.items():
            for val in vals[1:]:
                if val in data2:
                    data1[val] = data1.pop(sym)

        ori_libraries_symbols = get_target_library_symbols(ori_libraries)
        new_keys = [key for key in set(data1.keys()).union(
            set(data1.keys())) if key in ori_libraries_symbols]

        new_data1 = {key: data1.get(key, [0]) for key in new_keys}
        new_data2 = {key: data2.get(key, [0]) for key in new_keys}
        workload_pairs[key] = {
            "cur_workload": new_data1,
            "static_workload": new_data2
        }

    binary_cosin = [0]*len(workload_pairs.keys())
    for key, values in workload_pairs.items():
        data1 = values["cur_workload"]
        data2 = values["static_workload"]
        vector1 = np.array([sum(data1[key]) for key in data1.keys()])
        vector2 = np.array([sum(data2[key]) for key in data1.keys()])
        binary_cosin[key] = compute_binary_cosine_similarity(
            vector1, vector2)

    total_result = compute_stage2_similarity(workload_pairs, binary_cosin)
    max_index = max(range(len(total_result)),
                    key=lambda i: total_result[i][len(total_result[0])-1])
    if (total_result[max_index][len(total_result[0])-1]) == 0:
        max_index = -1
    return max_index, total_result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python script.py <optimized_perf.data> <hotlibrary_mapinfos> <threshold>")
        sys.exit(1)

    perf_data = sys.argv[1]
    mapinfo_file = sys.argv[2]
    threshold = float(sys.argv[3])

    mapinfo_data = parse_mapinfo_file(mapinfo_file)
    hotlibrary_mapinfos = get_hotlibrary_infos(mapinfo_data)

    max_index, total_result = select_hotlibrary(perf_data,
                                                mapinfo_data, hotlibrary_mapinfos, threshold)

    print(f"{os.path.basename(perf_data)} result:")
    table_str = print_results_as_table(mapinfo_data, total_result)
    print(table_str)
    print(f"mapped hotlibrary is {mapinfo_data[max_index]['ht_path']}")

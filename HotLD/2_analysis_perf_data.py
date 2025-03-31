from collections import defaultdict
from create_hotld_enviroment import get_library_paths
import subprocess
import os
import sys
import json

skipp_libs = ["libc.so.6", "ld-linux-x86-64.so.2"]


def analyze_perf_data(perf_data_path):
    """
    Analyze perf.data and sort shared libraries by function call count.

    Args:
        perf_data_path (str): Path to the perf.data file.
    """
    if not os.path.isfile(perf_data_path):
        raise FileNotFoundError(f"perf.data file not found: {perf_data_path}")

    try:
        result = subprocess.run(
            ['perf', 'script', '-i', perf_data_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"perf script command failed: {result.stderr.strip()}")

        lib_call_counts = defaultdict(int)
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) > 1 and '/' in parts[-1]:
                lib_name = parts[-1]
                lib_call_counts[lib_name] += 1

        sorted_libs = sorted(lib_call_counts.items(),
                             key=lambda x: x[1], reverse=True)

        total_count = 0
        libs = []
        print("Shared libraries sorted by function call count:")
        for lib, count in sorted_libs:
            print(f"{lib}: {count} calls")
            total_count += count

        for lib, count in sorted_libs:
            if count/total_count >= 0.00001:
                lib = lib.replace('(', '').replace(')', '')
                if os.path.basename(lib) in skipp_libs:
                    continue
                if ".so" not in lib:
                    continue
                libs.append(lib.replace('(', '').replace(')', ''))

        return libs
    except Exception as e:
        raise RuntimeError(f"An error occurred while analyzing perf.data: {e}")


def main():
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <perf_data_path> <app_cfg_path> <command>")
        sys.exit(1)

    perf_data = sys.argv[1]
    app_cfg_path = sys.argv[2]
    command = sys.argv[3]

    libs = analyze_perf_data(perf_data)

    depend_list = get_library_paths(command)

    sorted_libs = []
    for lib in depend_list:
        if lib in libs:
            sorted_libs.append(lib)

    if len(sorted_libs) != len(libs):
        print("Can't find all hot libraries.")

    print(sorted_libs)

    cfg = {
        "exe_file": command,
        "hot_library": sorted_libs
    }
    with open(app_cfg_path, "w") as file:
        json.dump(cfg, file, indent=4)


if __name__ == "__main__":
    main()

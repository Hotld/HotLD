import json
import sys
import subprocess
import sys
import os

benchmarks = ["overwrite"]
total_benchmarks = [
    "fillrandom", "fillseq", "readrandom", "readseq", "overwrite", "updaterandom"
]
benchmarks_infos = {
    "fillseq": {
        "--num": 10000000,
        "--db": "",
        "other_cfg": " --duration=60 -report_file=report.csv -report_interval_seconds=1 "
    },
    "fillrandom": {
        "--num": 10000000,
        "--db": "",
        "other_cfg": " --duration=60 -report_file=report.csv -report_interval_seconds=1 "
    },
    "readrandom": {
        "--num": 2000000,
        "--db": "",
        "other_cfg": " --duration=60 --use_existing_db=true --use_existing_keys=true -report_file=report.csv -report_interval_seconds=1 "
    },
    "readseq": {
        "--num": 2000000,
        "--db": "",
        "other_cfg": " --duration=60 --use_existing_db=true --use_existing_keys=true -report_file=report.csv -report_interval_seconds=1 "
    },
    "overwrite": {
        "--num": 2000000,
        "--db": "",
        "other_cfg": " --duration=60 --use_existing_db=true --use_existing_keys=true -report_file=report.csv -report_interval_seconds=1 "
    },
    "updaterandom": {
        "--num": 2000000,
        "--db": "",
        "other_cfg": " --duration=60 --use_existing_db=true --use_existing_keys=true -report_file=report.csv -report_interval_seconds=1 "
    },

}

current_path = os.getcwd()
perf_script = f"{os.path.dirname(current_path)}/HotLD/1_run_with_perf.py"
analy_perf_script = f"{os.path.dirname(current_path)}/HotLD/2_analysis_perf_data.py"
bolt_script = f"{os.path.dirname(current_path)}/HotLD/3_run_bolt.py"
parse_ori_perfdata_script = f"{os.path.dirname(current_path)}/HotLD/4_extract_perf_data_features.py"
generate_hotlibs_script = f"{os.path.dirname(current_path)}/HotLD/Hot-Generator/main.py"

Bolt2Hotld = f"{os.path.dirname(current_path)}/HotLD/Hot-Generator/Bolted2Hotld.sh"


def execute_command(command: str):
    print(f"[commond] {command}")

    try:
        process = subprocess.Popen(
            command, shell=True, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()

    except Exception as e:
        print(f"执行命令时出错: {e}")


def add_features(json_file, features_path):
    with open(json_file, 'r', encoding='utf-8') as f:
        json_dict = json.load(f)

    json_dict["workload_features"] = features_path
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_dict, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <exe_file> <testdb_path>")
        sys.exit(1)

    exe_file = sys.argv[1]
    testdb_path = sys.argv[2]

    all_hot_library = {}
    for index, benchmark in enumerate(benchmarks):
        working_directory = f"{current_path}/{benchmark}"
        app_cfg_path = working_directory+"/db_bench.json"
        num = benchmarks_infos[benchmark]['--num']
        others = benchmarks_infos[benchmark]['other_cfg']
        arguments = f"--benchmarks={benchmark} --num={num} {others}"
        is_run_perf = False
        if not os.path.exists(f"{app_cfg_path}"):
            is_run_perf = True
        if not os.path.exists(f"{working_directory}/perf.data"):
            is_run_perf = True

        if benchmark not in ["fillrandom", "fillseq"]:
            if benchmark == "readseq":
                create_testdb = f"{exe_file} --benchmarks=fillrandom --db={testdb_path} --num=10000000 "
            else:
                create_testdb = f"{exe_file} --benchmarks=fillrandom --db={testdb_path} --num=2000000 "
            if is_run_perf:
                execute_command(create_testdb)
            arguments = f"{arguments} --db={testdb_path}"

        # 1. run with perf
        run_perf_commond = f"python3 {perf_script} {working_directory} {exe_file} {arguments}"

        if is_run_perf:
            execute_command(run_perf_commond)

        # 2. analysis perf.data
        perf_data = f"{working_directory}/perf.data"
        analy_perf_commond = f"python3 {analy_perf_script} {perf_data} {app_cfg_path} {exe_file}"
        execute_command(analy_perf_commond)

        # 3. generate Bolted-libraries
        run_bolt_command = f"python3 {bolt_script} {app_cfg_path} {working_directory}/perf.data {working_directory}"
        execute_command(run_bolt_command)

        # 4. extract perf.data features
        parse_perf_data = f"python3 {parse_ori_perfdata_script} {perf_data} {app_cfg_path}"
        execute_command(parse_perf_data)

        # 5. generate HotLib
        generate_hotlib_commond = f"python3 {generate_hotlibs_script} {app_cfg_path} {Bolt2Hotld} {working_directory} "
        execute_command(generate_hotlib_commond)

        all_hot_library[benchmark] = {
            "index": index,
            "hotlibrary": f"{working_directory}/db_bench.ht",
            "cfg": app_cfg_path
        }

        delete_cmd = f"rm -rf {testdb_path}"
        execute_command(delete_cmd)

    all_hotlibrary_path = "total_hotlibrary"

    with open(all_hotlibrary_path, 'w') as f:
        f.write(f"{len(benchmarks)}\n")

        for benchmark in benchmarks:
            integer = all_hot_library[benchmark]["index"]
            string = all_hot_library[benchmark]["hotlibrary"]
            cfg_path = all_hot_library[benchmark]["cfg"]

            f.write(f"{integer} {string} {cfg_path}\n")

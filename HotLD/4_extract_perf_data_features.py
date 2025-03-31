import sys
import json
import os
import subprocess


def execute_command(command: str):
    print(f"[commond] {command}")

    try:
        process = subprocess.Popen(
            command, shell=True, stdout=sys.stdout, stderr=sys.stderr)
        process.wait()

    except Exception as e:
        print(f"Run error: {e}")


def convert_dict_by_symbol(input_dict, total_cycle):
    symbol_dict = {}

    # Iterate over the original dictionary
    for address, data in input_dict.items():
        symbol = data["symbol"]
        cycle_count = data["cycle_count"]

        if "unknown" in symbol:
            if address.startswith("ffff"):
                symbol = "kernel_event"
            else:
                print(f"unprocess event {address} {data}")

        if symbol not in symbol_dict:
            symbol_dict[symbol] = []
        symbol_dict[symbol].append(cycle_count)

    threshold = 0.000001 * total_cycle
    result = {key: [v / total_cycle for v in values]
              for key, values in symbol_dict.items()
              if sum(values) >= threshold}

    return result


def process_file(perf_data):
    perf_data_text = f"{os.path.dirname(perf_data)}/perf_data_text"
    perf_script_commond = f"perf script -i {perf_data} -F -tid,-time,-comm --no-demangle >{perf_data_text}"
    execute_command(perf_script_commond)

    data_dict = {}  # Dictionary to store data with address as key
    total_cycle = 0
    with open(perf_data_text, 'r') as file:
        for line in file:
            parts = line.split()
            if len(parts) != 5:
                print("Line with unexpected column count:", line.strip())
            else:
                cycle_count = int(parts[0])
                address = parts[2]

                symbol = parts[3].split('+')[0]
                total_cycle += cycle_count

                if address in data_dict:
                    data_dict[address]["cycle_count"] += cycle_count
                else:
                    data_dict[address] = {
                        "cycle_count": cycle_count,
                        "symbol": symbol,
                    }

    print(f"total cycle count {total_cycle}")
    symbol_result = convert_dict_by_symbol(data_dict, total_cycle)
    return symbol_result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <perf_data> <app_cfg_path>")
        sys.exit(1)

    perf_data = sys.argv[1]
    app_cfg_path = sys.argv[2]

    symbol_result = process_file(perf_data)

    with open(app_cfg_path, 'r') as f:
        cfg_data = json.load(f)

    cfg_data['workload_features'] = symbol_result
    # Save the dictionary to a JSON file
    with open(app_cfg_path, 'w') as json_file:
        json.dump(cfg_data, json_file, indent=4)

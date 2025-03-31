import ast
import bisect


def convert_str_to_list(range_strs):
    return [list(ast.literal_eval(range_str)) for range_str in range_strs]


def process_file(input_file):
    data_dict = {}  # Dictionary to store data with address as key
    total_cycle = 0
    with open(input_file, 'r') as file:
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

    # print(f"total cycle count {total_cycle}")
    return data_dict, total_cycle


def process_file_from_string(perf_output):
    data_dict = {}
    total_cycle = 0

    for line in perf_output.strip().split("\n"):
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

    return data_dict, total_cycle


def find_range(ranges, num):
    starts = [r[0] for r in ranges]

    idx = bisect.bisect_right(starts, num)

    if idx > 0:
        start, end = ranges[idx - 1]
        if start <= num < end:
            return (start, end)

    return None


def map_address2symbolname(address, ht_ranges, symbol_ranges_dict):
    ht_target = find_range(ht_ranges, address)
    if ht_target != None:
        symbol_target = find_range(symbol_ranges_dict[str(ht_target)], address)
        return ht_target, symbol_target
    return None, None


def convert_dict_by_symbol(input_dict, total_cycle, hotlibrary_mapinfos):
    ht_ranges = hotlibrary_mapinfos.keys()
    symbol_ranges_dict = {}
    for key in ht_ranges:
        symbol_ranges = hotlibrary_mapinfos[key]["symbol_infos"].keys()
        symbol_ranges = [list(ast.literal_eval(range_str))
                         for range_str in symbol_ranges]
        symbol_ranges = sorted(symbol_ranges, key=lambda x: x[0])
        symbol_ranges_dict[key] = symbol_ranges

    ht_ranges = [list(ast.literal_eval(range_str)) for range_str in ht_ranges]
    ht_ranges = sorted(ht_ranges, key=lambda x: x[0])
    symbol_dict = {}

    duplicate_names = {}
    for address, data in input_dict.items():
        symbol = data["symbol"]
        cycle_count = data["cycle_count"]

        if "unknown" in symbol:
            if address.startswith("ffff"):
                symbol = "kernel_event"
            else:
                ht_target, symbol_target = map_address2symbolname(
                    int(address, 16), ht_ranges, symbol_ranges_dict)

                if symbol_target != None:
                    symbol_names = hotlibrary_mapinfos[str(
                        ht_target)]["symbol_infos"][str(symbol_target)]

                    symbol = symbol_names[0]
                    if len(symbol_names) > 1:
                        duplicate_names[symbol] = symbol_names
                else:
                    print(f"unprocess event {address} {data}")
                    continue

        if symbol not in symbol_dict:
            symbol_dict[symbol] = []
        symbol_dict[symbol].append(cycle_count)

    threshold = 0.00001 * total_cycle
    result = {key: [v / total_cycle for v in values]
              for key, values in symbol_dict.items()
              if sum(values) >= threshold}

    return result, duplicate_names


def filter_dict(data, threshold=0.05):
    return {key: values for key, values in data.items() if sum(values) >= threshold}

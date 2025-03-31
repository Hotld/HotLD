import re
import sys
import json
import concurrent.futures
from objdump_function import *
from common import *

HOT_TEXT_NAME = ".text"
COLD_TEXT_NAME = ".text.cold"


def parse_bolt_file(file_path):
    """
    Parse the BOLT info file to extract function data.
    """
    functions_data = []  # To store all function data
    total_functions = 0
    current_function = None  # To track the current function being parsed

    with open(file_path, 'r') as file:
        lines = file.readlines()
        cold_mapping = []
        for i, line in enumerate(lines):
            line = line.strip()

            # Extract the total number of functions
            match_total = re.match(
                r"BOLT-INFO: Parsed (\d+) BAT entries", line)
            if match_total:
                total_functions = int(match_total.group(1))
                continue

            # Match function start address
            match_function = re.match(
                r"Function Address:\s+(0x[0-9a-fA-F]+)", line)
            if match_function:
                # Save data for the previous function (if any)
                if current_function:
                    functions_data.append(current_function)

                # Initialize current function
                current_function = {
                    "start_address": match_function.group(1),
                    # "basic_blocks": [],
                    "num_blocks": 0,
                    # "branches": []
                }
                continue

            # Match the number of basic blocks
            match_num_blocks = re.match(r"NumBlocks:\s+(\d+)", line)
            if match_num_blocks:
                current_function["num_blocks"] = int(match_num_blocks.group(1))
                continue

            # Match cold block mappings
            match_cold_mapping = re.match(r"\d+\s+cold\s+mappings:\s*", line)
            if match_cold_mapping:
                cold_mapping = lines[i+1:]
                break
        # Save data for the last function (if any)
        if current_function:
            functions_data.append(current_function)

        # Regular expression to match address mappings
        pattern = r"0x([0-9a-fA-F]+) -> ([0-9a-fA-F]+)"
        formatted_addresses = []

        # Process cold mappings
        for line in cold_mapping:
            line = line.strip()
            matches = re.findall(pattern, line)
            formatted_addresses.extend(
                [(match[0], match[1]) for match in matches])
    return total_functions, functions_data, formatted_addresses


def process_address_blocks(address_blocks, elf_file):
    """
    Process address blocks using multi-threading to disassemble.
    """
    if len(address_blocks) <= MAX_THREAD:
        max_threads = len(address_blocks)
    else:
        max_threads = MAX_THREAD

    # Using a thread pool to process address blocks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []

        # Submit tasks for disassembling each address block
        for start_addr, end_addr in address_blocks:
            futures.append(executor.submit(disassemble_block,
                           start_addr, end_addr, elf_file))

        all_results = []
        # Collect disassembly results as tasks are completed
        for future in concurrent.futures.as_completed(futures):
            start_addr, disassembled_output = future.result()
            if disassembled_output:
                all_results.append((start_addr, disassembled_output))
        return all_results


def main():
    """
    Main function to handle the script logic.
    """
    if len(sys.argv) != 4:
        print("Usage: python extract_hot_functions.py <bolted_elf_path> <bat_info_file> <bolted_output_file>")
        sys.exit(1)

    bolted_elf_file = sys.argv[1]
    bat_file = sys.argv[2]
    bolted_output = sys.argv[3]

    # Parse the BOLT info file to extract function data
    total_functions, functions_data, cold_mapping = parse_bolt_file(bat_file)

    # Parse the ELF file to get function dictionary
    functions_dict = get_functions_as_dict_orderby_address(bolted_elf_file)

    functions_info = {}
    # Process each function and add additional information
    for func in functions_data:
        func_start_addr = int(func['start_address'][2:], 16)
        functions_info[func_start_addr] = functions_dict[func_start_addr]
        functions_info[func_start_addr]["parent_addr"] = 0
        functions_info[func_start_addr]["num_blocks"] = func["num_blocks"]

    # Process cold mapping and update functions info
    for item in cold_mapping:
        func_start = int(item[0], 16)
        functions_info[func_start]["parent_addr"] = int(item[1], 16)

    # Generate address block list, each element is (start_address, end_address)
    address_blocks = []
    for func_address, info in functions_info.items():
        start_address = int(func_address)
        end_address = start_address + info['size']
        address_blocks.append((start_address, end_address))

    # Use multi-threading to disassemble address blocks
    disassembly_results = process_address_blocks(
        address_blocks, bolted_elf_file)

    # Store disassembly results in the function information
    for start_addr, parsed_results in disassembly_results:
        functions_info[start_addr]["instrs_info"] = parsed_results

    # Write the final output to a JSON file
    with open(bolted_output, 'w') as f:
        json.dump(functions_info, f, indent=4)


if __name__ == "__main__":
    main()

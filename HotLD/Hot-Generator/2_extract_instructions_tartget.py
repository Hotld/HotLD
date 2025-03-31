import sys
import json
import concurrent.futures
import struct
import re
import logging
from common import *
from x86_64_instructions import *
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
MAX_THREAD = 64
HOT_BBS_RANGE = [0, 0]
COLD_BBS_RANGE = [0, 0]

if sys.byteorder == 'little':
    BYTEORDER = "<i"
else:
    BYTEORDER = ">i"


def extract_function_name_and_offset(input_str):
    # Extract content inside angle brackets
    match = re.search(r'<(.*?)>', input_str)
    if not match:
        return None, None  # Return None if no content inside angle brackets is found

    # Extracted content
    content = match.group(1)

    # Try to match function name and offset (offset is optional)
    func_match = re.match(r'(.+?)(?:\+0x([0-9a-fA-F]+))?$', content)
    if func_match:
        function_name = func_match.group(1)
        offset = func_match.group(2)  # Offset may be None
        return function_name, offset

    return None, None  # Return None if function name is not matched


def extract_target_address(address, opcode, offset, length):
    byte_list = opcode.split()
    if offset + 4 > len(byte_list):
        logging.error(
            f"{opcode}: Offset {offset} out of range{len(byte_list)}, unable to read 4 bytes")
        return None, None

    selected_bytes = byte_list[offset:offset + 4]
    byte_values = bytes(int(b, 16) for b in selected_bytes)
    signed_int = struct.unpack(BYTEORDER, byte_values)[0]
    target_address = address+signed_int+length
    return signed_int, target_address


def determine_address_region(address):
    """
    Determine the region of the given address.

    Region definitions:
    - 0: Hot basic block range (HOT_BBS_RANGE)
    - 1: Cold basic block range (COLD_BBS_RANGE)
    - 2: Original binary region (default)

    :param address: Target address (int)
    :return: Region identifier (int)
    """
    if HOT_BBS_RANGE[0] <= address < HOT_BBS_RANGE[1]:
        return 0  # Address is within the hot basic block range
    if COLD_BBS_RANGE[0] <= address < COLD_BBS_RANGE[1]:
        return 1  # Address is within the cold basic block range
    return 2  # Address belongs to the original binary region


def judge_target_address_is_valid(target_address, reloc_info, total_symbols, instr_info):
    target_name = reloc_info["target_name"]

    name, offset = extract_function_name_and_offset(target_name)
    if (target_address, name) in total_symbols.keys():
        return True
    if "@plt" in name:
        return True
    name = name.replace('@Base', '')
    if (0, name) in total_symbols.keys():
        return True

    if ("@Base") in target_name:
        return True

    if ("@@GLIBCXX") in target_name:
        return True

    if ("@@CXXABI_") in target_name:
        return True

    if (".cold") in target_name:
        return True

    if ("org.0") in target_name:
        return True

    if offset != None:
        modifed_target_addr = target_address-int(offset, 16)
        if (modifed_target_addr, name) in total_symbols.keys():
            return True

    logging.error(
        f"relocation extract failed {reloc_info} \n instr info: {instr_info} name: {name}")
    return False


"""
Relocation Address (Hot Basic Blocks):
Case 1: Target address is in the original binary.
Case 2: Target address is in hot basic blocks (Hot BBs).
Case 3: Target address is in cold basic blocks (Cold BBs). (# 777:Hot->cold)

Relocation Address (cold Basic Blocks):
Case 4: Target address is in the original binary.
Case 5: Target address is in hot basic blocks (Hot BBs).
Case 6: Target address is in cold basic blocks (Cold BBs). (# 778:Cold->hot)
"""


def generate_pre_function_relocations(func_addr, func_info, total_symbols):
    if "reloc_site" not in func_info.keys():
        return None, None
    bolted_instructions = func_info["instrs_info"]
    reloc_sites = func_info["reloc_site"]
    internal_relocs = {}

    for address, instr_info in bolted_instructions.items():
        reloc_addr = instr_info["reloc"]
        reloc_info = reloc_sites[reloc_addr]

        target_address = reloc_info["target_address"]

        if determine_address_region(reloc_addr) == 0:
            target_region = determine_address_region(target_address)
            if target_region == 0:  # case 2
                continue
            elif target_region == 1:  # case 3
                internal_relocs[reloc_addr] = {
                    "r_type": 777,
                    "dist_next_instr": reloc_info["dist_next_instr"],
                    "target_offset": target_address
                }
                continue
            elif target_region == 2:  # case1
                if judge_target_address_is_valid(target_address, reloc_info, total_symbols, instr_info):
                    internal_relocs[reloc_addr] = {
                        "r_type": reloc_info["r_type"],
                        "dist_next_instr": reloc_info["dist_next_instr"],
                        "target_offset": target_address
                    }
                    continue
        elif determine_address_region(reloc_addr) == 1:
            target_region = determine_address_region(target_address)
            if target_region == 0:  # case 5
                internal_relocs[reloc_addr] = {
                    "r_type": 778,
                    "dist_next_instr": reloc_info["dist_next_instr"],
                    "target_offset": target_address
                }
                continue
            elif target_region == 1:  # case 6
                continue
            elif target_region == 2:  # case4
                if judge_target_address_is_valid(target_address, reloc_info, total_symbols, instr_info):
                    internal_relocs[reloc_addr] = {
                        "r_type": reloc_info["r_type"],
                        "dist_next_instr": reloc_info["dist_next_instr"],
                        "target_offset": target_address
                    }
                    continue
        else:
            print(f"unprocess relocable instruction {address} {instr_info}")
    return func_addr, internal_relocs


def process_bolt_instructions(opcode_asm, instr_addr, instr_info):
    instruction = instr_info["instruction"]
    length = instr_info['length']
    key = (opcode_asm, length)
    if key not in x86_64_instructions.keys():
        logging.error(
            f"This instruction's not in x86_64_instructions. {instr_info}")
        return None, None

    offset = x86_64_instructions[key]
    signed_int, target_address = extract_target_address(
        instr_addr, instr_info["opcode"], offset, instr_info['length'])

    if hex(target_address)[2:] not in instr_info["instruction"]:
        logging.error(
            f"extract target address fail in bolted add instruction: {instr_info}")
        return None, None

    bolted_reloc = instr_addr+offset
    dist_next_instr = instr_info['length']-offset
    bolted_target_name = re.search(r'<(.*?)>', instruction).group()

    type = 776
    if "@plt" in bolted_target_name:
        type = 779
    reloc_info = {
        "r_type": type,
        "dist_next_instr": dist_next_instr,
        "target_address": target_address,
        "target_name": bolted_target_name
    }
    return bolted_reloc, reloc_info


def extract_bolted_function_relocations(func_start, bolted_func):
    bolted_instructions = bolted_func["instrs_info"]
    cur_func_name = bolted_func["name"]
    reloc_site = {}

    for address in bolted_instructions.keys():
        instr_info = bolted_instructions[address]

        opcode_asm = instr_info["instruction"].split()[0]
        if "lock xadd" in instr_info["instruction"]:
            opcode_asm = "lock xadd"
        if "lock add" in instr_info["instruction"]:
            opcode_asm = "lock add"

        if instr_info['length'] < 4:
            target_name, target_offset = extract_function_name_and_offset(
                instr_info["instruction"])
            if (target_name == cur_func_name) & (target_offset != None):
                continue
            # logging.info(f"This instruction is a short jmp {instr_info}")
            continue

        bolted_reloc, reloc_info = process_bolt_instructions(
            opcode_asm, int(address), instr_info)

        if bolted_reloc:
            instr_info["reloc"] = bolted_reloc
            bolted_instructions[address] = instr_info
            reloc_site[bolted_reloc] = reloc_info
        else:
            logging.error(f"instruction parse error")

    filter_bolted_instructions = {}
    for key, value in bolted_instructions.items():
        if "reloc" in value.keys():
            filter_bolted_instructions[key] = value
    bolted_func["instrs_info"] = filter_bolted_instructions
    bolted_func["reloc_site"] = reloc_site

    return func_start, bolted_func


def extract_instructions_target(bolted_functions_info):
    if len(bolted_functions_info.keys()) <= MAX_THREAD:
        max_threads = len(bolted_functions_info.keys())
    else:
        max_threads = MAX_THREAD

    print(f"max_threads: {max_threads}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []

        for key, func_info in bolted_functions_info.items():
            if "instrs_info" not in func_info:
                continue

            futures.append(executor.submit(
                extract_bolted_function_relocations, key, func_info))

        for future in concurrent.futures.as_completed(futures):
            func_start, func_info = future.result()
            bolted_functions_info[func_start] = func_info
        return bolted_functions_info


def generate_text_elf_relocations(bolted_functions_info, ori_binary):
    if len(bolted_functions_info.keys()) <= MAX_THREAD:
        max_threads = len(bolted_functions_info.keys())
    else:
        max_threads = MAX_THREAD

    print(f"max_threads: {max_threads}")
    all_result = {}

    total_symbols = get_total_symbols(ori_binary)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []

        for key, func_info in bolted_functions_info.items():
            if "instrs_info" not in func_info:
                continue
            futures.append(executor.submit(
                generate_pre_function_relocations, key, func_info, total_symbols))

        for future in concurrent.futures.as_completed(futures):
            func_start, reloc_sites = future.result()
            if func_start:
                all_result[func_start] = reloc_sites

    return all_result


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python main.py  <ori_binary> <optimized_binary>  <bolted_functions_info> <rela_info_file> <internal_relocations_file>")
        sys.exit(1)

    ori_binary = sys.argv[1]
    optimized_binary = sys.argv[2]
    bolted_functions_info_file = sys.argv[3]
    rela_info_file = sys.argv[4]
    internal_relocations_file = sys.argv[5]

    with open(bolted_functions_info_file, "r") as file:
        bolted_functions_info = json.load(file)

    HOT_BBS_RANGE = get_section_addresses(optimized_binary, HOT_BBS_NAME)
    COLD_BBS_RANGE = get_section_addresses(optimized_binary, COLD_BBS_NAME)
    if (HOT_BBS_RANGE == None) | (COLD_BBS_RANGE == None):
        print(
            f"can't find Hot/Cold BBS: Hot:{HOT_BBS_RANGE}, Cold:{COLD_BBS_RANGE}")
    else:
        print(f"HOT_BBS_RANGE: {HOT_BBS_RANGE}")
        print(f"COLD_BBS_RANGE:{COLD_BBS_RANGE}")

    bolted_functions_info = extract_instructions_target(
        bolted_functions_info)

    with open(rela_info_file, "w") as file:
        json.dump(bolted_functions_info, file, indent=4)

    bolted_code_relocations = generate_text_elf_relocations(
        bolted_functions_info, ori_binary)

    with open(internal_relocations_file, "w") as file:
        json.dump(bolted_code_relocations, file, indent=4)

import json
from elftools.elf.elffile import ELFFile
from common import *
import logging

# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the sections for readonly and dynamic relocations
readonly_rela_sections = [".rela.text", ".rela.eh_frame"]
dynamic_rela_sections = [".rela.dyn", "rela.plt"]

# Define ELF relocation types for x86_64 architecture
RELA_TYPES = {
    "R_X86_64_NONE": 0,
    "R_X86_64_64": 1,
    "R_X86_64_PC32": 2,  # Target address accesses writable data section
    "R_X86_64_PLT32": 4,  # Target address accesses PLT section
    "R_X86_64_GLOB_DAT": 6,
    "R_X86_64_JUMP_SLOT": 7,
    "R_X86_64_RELATIVE": 8,
    "R_X86_64_GOTPCREL": 9,  # Target address accesses GOT table
    "R_X86_64_32": 10,
    "R_X86_64_DTPMOD64": 16,
    "R_X86_64_DTPOFF64": 17,
    "R_X86_64_TPOFF64": 18,
    "R_X86_64_TLSGD": 19,
    "R_X86_64_TLSLD": 20,
    "R_X86_64_DTPOFF32": 21,
    "R_X86_64_GOTTPOFF": 22,
    "R_X86_64_IRELATIVE": 37,
    "R_X86_64_REX_GOTPCRELX": 42,  # Target address accesses GOT table
}

# Function to parse writable relocation entries and check for hot functions


def parse_writable_relocation_and_check_hot_functions(rel, symbol):
    r_type = rel["r_info_type"]
    symbol_offset = symbol.entry["st_value"]
    r_addend = rel["r_addend"]
    r_offset = rel["r_offset"]
    cur_rela = None

    # Skip certain relocation types
    if r_type in [
        RELA_TYPES["R_X86_64_NONE"],
        RELA_TYPES["R_X86_64_DTPMOD64"],
        RELA_TYPES["R_X86_64_DTPOFF64"],
        RELA_TYPES["R_X86_64_TPOFF64"],
        RELA_TYPES["R_X86_64_DTPOFF32"],
    ]:
        return None

    # Handle specific relocation types
    if r_type in [
        RELA_TYPES["R_X86_64_JUMP_SLOT"],
        RELA_TYPES["R_X86_64_GLOB_DAT"],
        RELA_TYPES["R_X86_64_REX_GOTPCRELX"],
    ]:
        cur_rela = {
            "r_type": r_type,
            "r_offset": r_offset,
            "sym_name": symbol.name,
            "sym_offset": symbol_offset,
            "sym_type": symbol["st_info"]["type"],
            "r_target": symbol_offset,
            "r_addend": r_addend,
        }
        return cur_rela

    # Process R_X86_64_64 and R_X86_64_RELATIVE relocations
    if r_type in [RELA_TYPES["R_X86_64_64"], RELA_TYPES["R_X86_64_RELATIVE"]]:
        r_target = symbol_offset + r_addend
        cur_rela = {
            "r_type": r_type,
            "r_offset": r_offset,
            "sym_name": symbol.name,
            "sym_offset": symbol_offset,
            "sym_type": symbol["st_info"]["type"],
            "r_target": r_target,
            "r_addend": r_addend,
        }
        return cur_rela

    # Log unsupported relocation types
    logging.error(
        f"hotlib unprocess relocation type {r_type} {hex(r_offset)}"
    )
    return None

# Function to extract GOT (Global Offset Table) relocations for a given ELF library


def extract_per_library_got_relocations(elf_file_path):
    try:
        # Open and parse the ELF file
        with open(elf_file_path, 'rb') as elf_file:
            elf = ELFFile(elf_file)
            writable_segments = get_writable_segments(elf_file_path)

            relocations = {}
            # Iterate through all sections in the ELF file
            for section in elf.iter_sections():
                # Skip readonly relocation sections
                if section.name in readonly_rela_sections:
                    continue
                if section.header['sh_type'] in ('SHT_REL', 'SHT_RELA'):
                    # Iterate through all relocation entries in the section
                    for rel in section.iter_relocations():
                        r_offset = rel['r_offset']
                        # Check if the relocation address is in a writable segment
                        if not is_address_in_writable_segment(writable_segments, r_offset):
                            continue

                        # Get the symbol for the relocation
                        symbol_index = rel['r_info_sym']
                        if symbol_index is None:
                            continue

                        symbol = section.elffile.get_section(
                            section.header['sh_link']).get_symbol(symbol_index)

                        # Filter out object, section, or invalid symbol types
                        symbol_type = symbol["st_info"]["type"]
                        if symbol_type in ["STT_OBJECT", "STT_SECTION", ""]:
                            continue

                        # Process the relocation entry and check if it matches hot functions
                        cur_rela = parse_writable_relocation_and_check_hot_functions(
                            rel, symbol)
                        if cur_rela:
                            relocations[r_offset] = cur_rela
            return relocations
    except FileNotFoundError:
        print(f"Error: File '{elf_file_path}' not found.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Function to collect GOT relocations for parent libraries, filtering based on external hot functions


def collect_parent_got_relocations(parent_libs, external_hot_functions):
    total_got_relocation = {}
    print(parent_libs)

    # Iterate over parent libraries to collect their GOT relocations
    for library in parent_libs:
        got_relocations = extract_per_library_got_relocations(library)
        filter_got_relocations = {}

        # Filter out relocations that do not target external hot functions
        for r_offset, rela_info in got_relocations.items():
            r_target_name = rela_info["sym_name"]
            if r_target_name in external_hot_functions.keys():
                rela_info["r_hot_target"] = external_hot_functions[r_target_name]
                filter_got_relocations[r_offset] = rela_info

        # Store filtered relocations for the library
        total_got_relocation[library] = filter_got_relocations

    return total_got_relocation

# Function to collect GOT relocations for all libraries based on the configuration


def collect_got_relocations(config_data):
    exe_file = config_data["exe_file"]
    dependency_tree = build_dependency_relation(exe_file)
    hot_librarys = config_data["hot_library"]
    library_infos = config_data["library_infos"]

    all_got_relocations = {}

    # Iterate through each hot library and collect its GOT relocations
    for library in hot_librarys:
        # Retrieve the hot functions for the library
        rela_info_file = library_infos[library]["rela_info"]
        with open(rela_info_file, 'r') as f:
            functions_info = json.load(f)

        hot_symbols = []
        # Collect function address and name pairs
        for func_addr, value in functions_info.items():
            key = (int(func_addr), value["name"])
            hot_symbols.append(key)

        external_hot_functions = {}
        dynamic_symbols = get_dynamic_symbols(
            library_infos[library]["bolted_library"])

        # Check if the hot functions exist in dynamic symbols and match addresses
        for key in hot_symbols:
            name = key[1]
            address = key[0]
            if name in dynamic_symbols.keys():
                if address == dynamic_symbols[name]:
                    external_hot_functions[name] = dynamic_symbols[name]
                else:
                    logging.error(f"symbol {name} may have different address")

        # Collect GOT relocations for parent libraries of the hot library
        parent_got_relocations = collect_parent_got_relocations(
            dependency_tree[library]["parent"], external_hot_functions)
        all_got_relocations[library] = parent_got_relocations

    return all_got_relocations

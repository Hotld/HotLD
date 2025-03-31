import subprocess
from elftools.elf.elffile import ELFFile
import os
import logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
HOT_BBS_NAME = ".text"
COLD_BBS_NAME = ".text.cold"

LD_LIBRARY_PATH = os.environ.get("HOTLD_LIBRARY_PATH", "")
LD_LIBRARY_PATH = LD_LIBRARY_PATH.split(os.pathsep)


def find_library_in_ld_library_path(library_name):
    for path in LD_LIBRARY_PATH:
        if not os.path.isdir(path):
            continue
        full_path = os.path.join(path, library_name)
        if os.path.isfile(full_path):
            return full_path

    return None


def parse_dependencies(binary_path):
    if (os.path.exists(binary_path)):
        abs_filepath = binary_path
    else:
        abs_filepath = find_library_in_ld_library_path(binary_path)

    if abs_filepath == None:
        logging.error(f"can't find lib {binary_path}")
        return [], abs_filepath
    dependencies = []

    with open(abs_filepath, "rb") as f:
        elf = ELFFile(f)

        # Parse dynamic section to find shared libraries
        dynamic_section = elf.get_section_by_name(".dynamic")
        for tag in dynamic_section.iter_tags():
            if tag.entry.d_tag == "DT_NEEDED":
                depend = find_library_in_ld_library_path(tag.needed)
                if depend != None:
                    dependencies.append(depend)

    return dependencies, abs_filepath


def build_dependency_relation(filepath):
    dependency_tree = {}
    parsed_depends = []
    need_parse_depends = []
    need_parse_depends.append(filepath)
    while len(need_parse_depends) > 0:
        cur_depend = need_parse_depends[0]
        # print(f"get denpendcy of {cur_depend}")
        dependencies, abs_filepath = parse_dependencies(cur_depend)
        if abs_filepath != "":
            parsed_depends.append(abs)
            dependency_tree[abs_filepath] = {
                "dependencies": dependencies,
                "parent": []
            }
            for item in dependencies:
                if (item not in need_parse_depends) & (item not in parsed_depends):
                    need_parse_depends.append(item)

        parsed_depends.append(cur_depend)
        need_parse_depends.remove(cur_depend)

    for file_path in dependency_tree.keys():
        dependency_tree[file_path]["parent"] .append(file_path)
        depend = dependency_tree[file_path]["dependencies"]
        for item in depend:
            dependency_tree[item]["parent"].append(file_path)

    return dependency_tree


def get_higher_priority_symbol(symbol1, symbol2):
    # Priority dictionary for symbol types
    priority = {
        'T': 1,  # Global symbol
        't': 2,  # Local symbol
        'U': 3,  # Undefined symbol
        'W': 4,  # Weak symbol
        'B': 5,  # BSS symbol (uninitialized static global variable)
        'D': 6,  # Data symbol (initialized global variable)
        'R': 7,  # Read-only symbol
        'A': 8   # Symbol in the program (used in assembly)
    }

    # Check if symbols are in the priority dictionary
    if symbol1 not in priority:
        raise ValueError(f"Unrecognized symbol type: {symbol1}")
    if symbol2 not in priority:
        raise ValueError(f"Unrecognized symbol type: {symbol2}")

    # Get the priority of each symbol
    priority1 = priority[symbol1]
    priority2 = priority[symbol2]

    # Return the symbol with the higher priority
    if priority1 < priority2:
        return symbol1
    elif priority1 > priority2:
        return symbol2
    else:
        return symbol1  # If both symbols have the same priority, return either one


def display_functions(functions):
    """
    Format and print function information stored in the dictionary.
    """
    print(f"{'Address':<16}{'Size':<10}{'Type':<6}{'Function Name'}")
    print("-" * 50)
    for address in sorted(functions):
        func_info = functions[address]
        print(
            f"{hex(address):<16}{func_info['size']:<10}{func_info['type']:<6}{func_info['name']}")


def get_functions_as_dict_orderby_address(elf_file_path):
    """
    Use nm to extract all function information from an ELF file 
    and store it in a dictionary where the address is the key.
    Each function contains size, name, and type (e.g., T, U).
    """
    functions = {}
    try:
        # Run the nm command to get the symbol table
        result = subprocess.run(
            ['nm', '--print-size', '--numeric-sort', elf_file_path],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:  # Ensure the line format is as expected
                try:
                    func_address = int(parts[0], 16)  # Function address
                    func_size = int(parts[1], 16)    # Function size
                    # Function type (e.g., T or U)
                    func_type = parts[2]
                    func_name = parts[3]            # Function name

                    if func_address in functions.keys():
                        pre_type = functions[func_address]["type"]
                        highter_type = get_higher_priority_symbol(
                            func_type, pre_type)
                        if highter_type != func_type:
                            continue
                    functions[func_address] = {
                        "size": func_size,
                        "name": func_name,
                        "type": func_type
                    }
                except ValueError:
                    # Skip lines that cannot be parsed (e.g., undefined symbols)
                    continue

    except subprocess.CalledProcessError as e:
        print(f"Error while running nm: {e}")

    return functions


def get_total_symbols(elf_file_path):
    functions = {}
    try:
        # Run the nm command to get the symbol table
        result = subprocess.run(
            ['nm', '--print-size', '--numeric-sort', elf_file_path],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:  # Ensure the line format is as expected
                try:
                    func_address = int(parts[0], 16)  # Function address
                    func_size = int(parts[1], 16)    # Function size
                    # Function type (e.g., T or U)
                    func_type = parts[2]
                    func_name = parts[3]            # Function name
                    functions[(func_address, func_name)] = {
                        "size": func_size,
                        "type": func_type
                    }
                except ValueError:
                    # Skip lines that cannot be parsed (e.g., undefined symbols)
                    continue
            if len(parts) == 3:
                func_address = int(parts[0], 16)  # Function address
                func_size = 0    # Function size
                # Function type (e.g., T or U)
                func_type = parts[1]
                func_name = parts[2]            # Function name
                functions[(func_address, func_name)] = {
                    "size": func_size,
                    "type": func_type
                }
            if len(parts) == 2:
                func_address = 0  # Function address
                func_size = 0    # Function size
                # Function type (e.g., T or U)
                func_type = parts[0]
                func_name = parts[1]            # Function name
                functions[(func_address, func_name)] = {
                    "size": func_size,
                    "type": func_type
                }

    except subprocess.CalledProcessError as e:
        print(f"Error while running nm: {e}")

    with open(elf_file_path, 'rb') as f:
        elffile = ELFFile(f)
        for section in elffile.iter_sections():
            if section.name == ".got":
                start_address = section['sh_addr']
                functions[start_address, ".got"] = {"size": 0,
                                                    "type": "N"}
    return functions


def get_dynamic_symbols(file_path):
    with open(file_path, 'rb') as f:
        elf = ELFFile(f)

        dynamic_symbols = {}
        for section in elf.iter_sections():
            if section.name == '.dynsym':
                for symbol in section.iter_symbols():
                    name = symbol.name
                    address = symbol['st_value']
                    if name in dynamic_symbols.keys():
                        if address == dynamic_symbols[name] == address:
                            logging.error(
                                f"dynamic symbol {name} have different address")
                    else:
                        dynamic_symbols[name] = address

        return dynamic_symbols


def get_section_addresses(elf_file_path, section_name):
    with open(elf_file_path, 'rb') as f:
        elf = ELFFile(f)
        for section in elf.iter_sections():
            if section.name == section_name:
                start_addr = section['sh_addr']
                size = section['sh_size']
                end_addr = start_addr + size
                return [start_addr, end_addr]

    return None


def get_writable_segments(elf_path):
    """
    Get the ranges of all writable segments in the ELF file.

    :param elf_path: Path to the ELF file
    :return: List of ranges of writable segments, each range is a tuple (start, end)
    """
    writable_segments = []
    with open(elf_path, 'rb') as f:
        elf = ELFFile(f)
        # Iterate through all segments in the ELF file
        for segment in elf.iter_segments():
            # Check if the segment is of type PT_LOAD and has write permission (PF_W = 0x2)
            if segment['p_type'] == 'PT_LOAD' and segment['p_flags'] & 0x2:  # PF_W = 0x2
                seg_start = segment['p_vaddr']  # Start address of the segment
                # End address of the segment
                seg_end = seg_start + segment['p_memsz']
                # Add the range to the list
                writable_segments.append((seg_start, seg_end))
    return writable_segments


def is_address_in_writable_segment(writable_segments, address):
    for start, end in writable_segments:
        if start <= address < end:
            return True
    return False


def get_functions_in_range(elf_path, start_offset, end_offset):
    functions = []

    with open(elf_path, "rb") as f:
        elf = ELFFile(f)

        symtab = elf.get_section_by_name(".symtab")
        if not symtab:
            print("ELF 文件中没有符号表")
            return []

        for symbol in symtab.iter_symbols():
            if symbol['st_info']['type'] == 'STT_FUNC':
                func_addr = symbol['st_value']
                func_size = symbol['st_size']
                func_name = symbol.name

                if start_offset <= func_addr < end_offset:
                    functions.append(
                        (func_addr, func_addr+func_size, func_name))

    return functions


"""
    # Example usage
if __name__ == "__main__":
    # Replace with the path to your ELF file
    elf_file_path = "/usr/local/hotld/libzstd.so.1"
    try:
        symbols = get_total_symbols(elf_file_path)
        for symbol, value in symbols.items():
            func_addr = symbol[0]
            func_name = symbol[1]
            size = value["size"]
            type = value["type"]
            print(
                f"Address: {hex(func_addr)}\t {size}\t Type: {type}\t Name: {func_name}")
    except RuntimeError as e:
        print(e)
"""

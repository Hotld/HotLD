import subprocess
import re

MAX_THREAD = 64


def is_contains_symbol_name_in_instruction(instruction):
    """
    Check if the instruction contains a symbol name or relocation target.
    """
    is_angle_bracket = bool(re.search(r'<.*>', instruction))
    is_hash = bool(re.search(r'#', instruction))

    if not is_angle_bracket and not is_hash:
        return False

    return True


def parse_disassembly(disassembly_text):
    """
    Parse the disassembly text and extract information such as address, opcode,
    instruction, immediate values, etc.
    """
    results = []

    # Split the input text by lines
    address_pattern = re.compile(r"^\s*[0-9a-fA-F]{1,16}:\s+")
    total_lines = disassembly_text.splitlines()
    lines = [line for line in total_lines if address_pattern.match(line)]

    current_instr = None  # To store information for multi-line instructions

    for line in lines:
        # Match lines that start with an address, followed by opcode and instruction
        match = re.match(
            r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s)+)(.*)$", line)
        if match:
            address = match.group(1)  # Instruction start address
            opcode = match.group(2).strip()  # Opcode (bytecodes)
            instruction = match.group(3).strip()  # Assembly instruction text

            if instruction:
                # If instruction is present, this is a new instruction
                if current_instr:
                    # Save the previous instruction
                    results.append(current_instr)
                # Start a new instruction record
                current_instr = {
                    "address": int(address, 16),
                    "opcode": opcode,
                    "instruction": instruction
                }
            else:
                # This is a continuation of the previous instruction
                if current_instr:
                    current_instr["opcode"] += f" {opcode}"  # Append to opcode
        else:
            pass  # Handle lines that do not match the expected format

    # Save the last instruction
    if current_instr:
        results.append(current_instr)

    # Extract instruction length and immediate values
    for instr in results:
        # Length based on opcode bytes
        instr["length"] = len(instr["opcode"].split())

    # Filter out instructions with length <= 4 (usually don't need relocation)
    filtered_instructions = {}
    for instr in results:
        instruction = instr["instruction"]
        if not is_contains_symbol_name_in_instruction(instruction):
            continue

        address = instr["address"]
        length = instr["length"]
        opcode = instr["opcode"]

        filtered_instructions[address] = {
            "opcode": opcode,
            "instruction": instruction,
            "length": length,
        }

    return filtered_instructions


def disassemble_block(start_addr, end_addr, elf_file):
    """
    Disassemble a block of code from the specified address range in the ELF file.
    """
    cmd = f"objdump -D --start-address={start_addr} --stop-address={end_addr} {elf_file}"
    try:
        # Call objdump via subprocess
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True)

        parse_result = parse_disassembly(result.stdout)

        return start_addr, parse_result

    except subprocess.CalledProcessError as e:
        print(f"Error running objdump: {e}")
        exit()

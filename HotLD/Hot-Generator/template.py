from tabulate import tabulate
from common import *
import struct

# Template Header


class Templatehdr:
    def __init__(self):
        self.info_off = 0
        self.info_size = 0
        self.text_off = 0
        self.text_size = 0

        self.shoff = 0
        self.shnum = 0
        self.shentsize = 4 * 4

    def to_binary(self):
        return struct.pack(
            'IIIIIII',
            self.info_off,
            self.info_size,
            self.text_off,
            self.text_size,
            self.shoff,
            self.shnum,
            self.shentsize
        )

    def size_of(self):
        return 4 * 7


section_types = {
    "depend_table": 0,
    "got_relocations_table": 1,
    "text_relocations_table": 2,
    "ro_string": 3,
    "text_data": 4,
}


class SectionHeader:
    def __init__(self):
        self.type = 0
        self.offset = 0
        self.size = 0
        self.entrysize = 0

    def set_section(self, type, offset, size, entrysize):
        self.type = type
        self.offset = offset
        self.size = size
        self.entrysize = entrysize

    def to_binary(self):
        return struct.pack(
            'IIII',
            self.type,
            self.offset,
            self.size,
            self.entrysize,
        )


class LibRelocationInfo:
    def __init__(self):
        self.name = ""
        self.name_ptr = 0
        self.offset = 0
        self.size = 0
        self.entrysize = 0

    def to_binary(self):
        return struct.pack(
            'IIII',
            self.name_ptr,
            self.offset,
            self.size,
            self.entrysize,
        )

    def print_values(self):
        print(f"name: {self.name}, name_ptr: {self.name_ptr}, "
              f"offset: {self.offset}, size: {self.size}, entrysize: {self.entrysize}")


class LibraryMetaData:
    def __init__(self):
        self.name = ""
        self.md5 = 0  # 16bytes
        self.hotcode_range = (0, 0)  # 4bytes
        self.coldcode_range = (0, 0)  # 4bytes
        self.got_relocations = [0, 0, 0]  # 4bytes
        self.code_relocations = [0, 0, 0]  # 4bytes
        self.ori_hotbbs_range = (0, 0)
        self.ori_coldbbs_range = (0, 0)
        self.length = 56

    def __str__(self):
        return f"{self.name}, {self.name_ptr}, {self.md5}, {self.hotcode_range}, {self.coldcode_range}, {self.got_relocations}, {self.code_relocations}, {self.length}"


class LibraryInfo:
    def __init__(self):
        self.name = ""
        self.name_ptr = 0  # 4bytes
        self.md5 = b'\x00' * 16  # 16bytes
        self.hotbbs_start = 0  # 4bytes
        self.hotbbs_end = 0  # 4bytes
        self.coldbbs_start = 0  # 4bytes
        self.coldbbs_end = 0  # 4bytes

    def setlibraryinfo(self, name_ptr, md5, hotbbs_start, hotbbs_end, coldbbs_start, coldbbs_end):
        self.name_ptr = name_ptr
        self.md5 = md5
        self.hotbbs_start = hotbbs_start
        self.hotbbs_end = hotbbs_end
        self.coldbbs_start = coldbbs_start
        self.coldbbs_end = coldbbs_end

    def to_binary(self):
        return struct.pack(
            'I16sIIII',  # 4bytes（I）、16bytes（16s）、4*4bytes（IIII）
            self.name_ptr,
            self.md5,
            self.hotbbs_start,
            self.hotbbs_end,
            self.coldbbs_start,
            self.coldbbs_end
        )

    def print_values(self):
        print(f"name: {self.name}, name_ptr: {self.name_ptr}, md5: {self.md5.hex()}, "
              f"hotbbs_start: {self.hotbbs_start}, hotbbs_end: {self.hotbbs_end}, "
              f"coldbbs_start: {self.coldbbs_start}, coldbbs_end: {self.coldbbs_end}")


def print_library_metadata(library_list):
    headers = ["Name", "MD5", "Hotcode Range", "Coldcode_Range",
               "Ori_hotbbs_range", "Ori_coldbbs_range", "GOT Relocations", "Code Relocations", "Length"]

    rows = [
        [lib.name, lib.md5, lib.hotcode_range, lib.coldcode_range, lib.ori_hotbbs_range,
            lib.ori_coldbbs_range, lib.got_relocations, lib.code_relocations, lib.length]
        for lib in library_list
    ]

    print(tabulate(rows, headers=headers, tablefmt="grid"))


class TemplateHotLibrary:
    def __init__(self):
        self.librarymetas = []

        self.header = Templatehdr()

        self.sections_table = []
        self.library_info_table = []
        self.got_relocations_table = []
        self.text_relocations_table = []

        self.hdr_size = 4*7
        self.sections_entry_size = 4*4
        self.library_info_table_entry_size = 9*4
        self.relocations_table_entry_size = 16

        self.section_table_size = 0
        self.library_info_table_size = 0
        self.got_relocation_table_size = 0
        self.text_relocation_table_size = 0

        self.got_relocation_entry_size = 12
        self.text_relocation_entry_size = 12

        self.readonly_string_info = {}
        self.linked_got_relocations_info = {}
        self.linked_text_relocations_info = {}

        self.linked_got_relocations_data = bytearray()
        self.linked_text_relocations_data = bytearray()
        self.readonly_string_data = bytearray()
        self.optimized_codes = bytearray()

        self.linked_got_relocations = {}
        self.linked_text_relocations = {}

    def generate_section_table(self):
        section_table = []
        for i in range(len(section_types.keys())):
            cur_section = SectionHeader()
            cur_section.type = i
            section_table.append(cur_section)

        self.sections_table = section_table
        self.section_table_size = len(
            self.sections_table)*self.sections_entry_size

    def generate_library_info_table(self):
        library_info_table = []
        for item in self.linked_got_relocations.keys():
            cur_library = LibraryInfo()
            cur_library.name = item
            library_info_table.append(cur_library)
        self.library_info_table = library_info_table
        self.library_info_table_size = len(
            self.library_info_table)*self.library_info_table_entry_size

    def generate_got_relocations_table(self):
        got_relocations_table = []
        print(self.linked_got_relocations.keys())
        for item in self.linked_got_relocations.keys():
            cur_got_relocations = LibRelocationInfo()
            cur_got_relocations.name = item
            got_relocations_table.append(cur_got_relocations)

        print(f"got_relocations_table:{got_relocations_table}")
        self.got_relocations_table = got_relocations_table
        self.got_relocation_table_size = len(
            got_relocations_table)*self.relocations_table_entry_size

    def generate_text_relocations_table(self):
        text_relocations_table = []
        print(self.linked_text_relocations.keys())
        for item in self.linked_text_relocations.keys():
            cur_text_relocations = LibRelocationInfo()
            cur_text_relocations.name = item
            text_relocations_table.append(cur_text_relocations)
            print(f"cur_text_relocations_item: {item}")
        self.text_relocations_table = text_relocations_table
        self.text_relocation_table_size = len(
            self.text_relocations_table)*self.relocations_table_entry_size

    """
    {
        "r_type": 7, # 4 bytes
        "r_offset": 604672, # 4 bytes
        "r_hot_target": 1604 # 4 bytes
    },
    """

    def packed_got_relocations(self):
        metadata = {}
        cur_start = 0
        entry_size = self.got_relocation_entry_size
        total_data = bytearray()

        for library, relocations in self.linked_got_relocations.items():
            for entry in relocations:
                total_data.extend(struct.pack(
                    "<III",
                    entry["r_type"],
                    entry["r_offset"],
                    entry["r_hot_target"],
                ))
            total_size = entry_size*len(relocations)
            metadata[library] = (cur_start, total_size)
            cur_start = cur_start+total_size

            print(
                f"The got relocation of {library} start: {metadata[library][0]},total size is {metadata[library][1]}")
        self.linked_got_relocations_data = total_data
        self.linked_got_relocations_info = metadata

    """
    {
        "r_type": 7, # 2 bytes
        "dist_next_instr": 4 # 2 bytes
        "r_offset": 604672, # 4 bytes
        "r_hot_target": 1604 # 4 bytes
    },
    """

    def packed_text_relocations(self):
        metadata = {}
        cur_start = 0
        entry_size = self.text_relocation_entry_size
        total_data = bytearray()

        for library, relocations in self.linked_text_relocations.items():
            for entry in relocations:
                if entry["r_type"] not in [776, 777, 778, 779]:
                    logging.error(f"packed_text_relocations error {entry} ")
                total_data.extend(struct.pack(
                    "<HHII",  # 2bytes, 2bytes, 4bytes、4bytes
                    entry["r_type"],
                    entry["dist_next_instr"],
                    entry["r_offset"],
                    entry["r_hot_target"],
                ))
            total_size = entry_size*len(relocations)
            metadata[library] = (cur_start, total_size)
            cur_start = cur_start+total_size

            print(
                f"The text relocation of {library} start: {metadata[library][0]},total size is {metadata[library][1]}")
        self.linked_text_relocations_data = total_data
        self.linked_text_relocations_info = metadata

    def packed_readonly_string(self):
        cur_start = 0
        total_data = bytearray()
        for library in self.linked_got_relocations.keys():
            total_data.extend(library.encode('utf-8'))
            total_data.append(0)  # add \0
            self.readonly_string_info[library] = cur_start
            cur_start = len(total_data)
        self.readonly_string_data = total_data

    def check_packed_readonly_string(self):
        paths = []
        current_path = bytearray()

        for byte in self.readonly_string_data:
            if byte == 0:
                paths.append(current_path.decode('utf-8'))
                current_path = bytearray()
            else:
                current_path.append(byte)

        print("\n check_packed_readonly_string")
        for path in paths:
            print(path)
        return paths

    def get_readonly_string_offset(self):
        for section in self.sections_table:
            if section.type == 3:
                return section.offset
        return None

    def write_hdr(self):
        # Calculate the offset and size of the info segment.
        total_size = self.hdr_size + self.section_table_size+self.library_info_table_size + \
            self.got_relocation_table_size+self.text_relocation_table_size + \
            len(self.readonly_string_data)+len(self.linked_got_relocations_data) + \
            len(self.linked_text_relocations_data)

        self.header.info_off = 0
        self.header.info_size = total_size
        self.header.text_off = total_size
        self.header.text_size = len(self.optimized_codes)
        self.header.shoff = self.hdr_size
        self.header.shnum = len(self.sections_table)
        self.header.shentsize = self.sections_entry_size

        binary_data = self.header.to_binary()
        return binary_data

    def write_section_table(self):
        total_data = bytearray()
        for section in self.sections_table:
            if section.type == 0:
                section_start = self.hdr_size+self.section_table_size
                section.set_section(
                    0, section_start, self.library_info_table_size, self.library_info_table_entry_size)
            elif section.type == 1:
                section_start = self.hdr_size+self.section_table_size+self.library_info_table_size
                section.set_section(
                    1, section_start, self.got_relocation_table_size, self.relocations_table_entry_size)

            elif section.type == 2:
                section_start = self.hdr_size+self.section_table_size + \
                    self.library_info_table_size+self.got_relocation_table_size
                section.set_section(
                    2, section_start, self.text_relocation_table_size, self.relocations_table_entry_size)

            elif section.type == 3:
                section_start = self.hdr_size+self.section_table_size + \
                    self.library_info_table_size+self.got_relocation_table_size + \
                    self.text_relocation_table_size
                section.set_section(
                    3, section_start, len(self.readonly_string_data), 1)

            elif section.type == 4:
                section.set_section(
                    4, self.header.text_off, self.header.text_size, 1)
            else:
                logging.error(f"unprocess section type {section.type}")

        for section in self.sections_table:
            cur_datas = section.to_binary()
            total_data.extend(cur_datas)
        return total_data

    def calculate_md5(self, library):
        return b'\x00' * 16

    def write_library_info_table(self):
        symtab_offset = self.get_readonly_string_offset()
        print(f"symtab_offset: {symtab_offset}")
        total_data = bytearray()
        for library in self.library_info_table:
            name_ptr = symtab_offset+self.readonly_string_info[library.name]
            md5 = self.calculate_md5(library)
            library.setlibraryinfo(name_ptr, md5, 0, 0, 0, 0)
            for item in self.librarymetas:
                if library.name == item.name:
                    library.setlibraryinfo(name_ptr, md5, item.hotcode_range[0],
                                           item.hotcode_range[1], item.coldcode_range[0], item.coldcode_range[1])

            library.print_values()
            total_data.extend(library.to_binary())

        return total_data

    def write_got_relocations_table(self):
        symtab_offset = self.get_readonly_string_offset()
        got_relocations_data_offset = self.header.info_size - \
            len(self.linked_got_relocations_data) - \
            len(self.linked_text_relocations_data)
        total_data = bytearray()
        for library in self.got_relocations_table:
            library.name_ptr = symtab_offset + \
                self.readonly_string_info[library.name]
            library.offset = self.linked_got_relocations_info[library.name][0] + \
                got_relocations_data_offset
            library.size = self.linked_got_relocations_info[library.name][1]
            library.entrysize = self.got_relocation_entry_size
            library.print_values()
            total_data.extend(library.to_binary())
        return total_data

    def write_text_relocations_table(self):
        symtab_offset = self.get_readonly_string_offset()
        text_relocations_data_offset = self.header.info_size - \
            len(self.linked_text_relocations_data)
        total_data = bytearray()
        for library in self.text_relocations_table:
            print(f"library_name:{library.name}")
            library.name_ptr = symtab_offset + \
                self.readonly_string_info[library.name]
            library.offset = self.linked_text_relocations_info[library.name][0] + \
                text_relocations_data_offset
            library.size = self.linked_text_relocations_info[library.name][1]
            library.entrysize = self.text_relocation_entry_size
            library.print_values()
            total_data.extend(library.to_binary())
        return total_data

    def generate_hotLibrary(self):
        # generate section table
        self.generate_section_table()
        self.generate_library_info_table()
        self.generate_got_relocations_table()
        self.generate_text_relocations_table()

        # generate .read_only
        self.packed_readonly_string()
        self.check_packed_readonly_string()
        print(self.readonly_string_info)

        self.packed_got_relocations()
        self.packed_text_relocations()
        print(f"\n {self.linked_got_relocations_info}")
        print(f"\n {self.linked_text_relocations_info}")

        HotLibrary_bytedata = bytearray()

        # write template Hdr
        binary_data = self.write_hdr()
        HotLibrary_bytedata.extend(binary_data)

        # write section table
        binary_data = self.write_section_table()
        HotLibrary_bytedata.extend(binary_data)

        # write library info table
        binary_data = self.write_library_info_table()
        HotLibrary_bytedata.extend(binary_data)

        # write got_relocations_info_table
        binary_data = self.write_got_relocations_table()
        HotLibrary_bytedata.extend(binary_data)

        # write text_relocations_info_table
        binary_data = self.write_text_relocations_table()
        HotLibrary_bytedata.extend(binary_data)

        # write  readonly string
        HotLibrary_bytedata.extend(self.readonly_string_data)

        HotLibrary_bytedata.extend(self.linked_got_relocations_data)
        HotLibrary_bytedata.extend(self.linked_text_relocations_data)
        print(f"optimized_codes size: {len(self.optimized_codes)}")
        HotLibrary_bytedata.extend(self.optimized_codes)
        return HotLibrary_bytedata

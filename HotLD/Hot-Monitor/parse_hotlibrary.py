import struct


class Templatehdr:
    STRUCT_FORMAT = "7I"

    def __init__(self, data):
        unpacked_data = struct.unpack(self.STRUCT_FORMAT, data)
        (self.info_off, self.info_size, self.text_off, self.text_size,
         self.shoff, self.shnum, self.shentsize) = unpacked_data

    def __repr__(self):
        return (f"Templatehdr(info_off={self.info_off}, info_size={self.info_size}, "
                f"text_off={self.text_off}, text_size={self.text_size}, "
                f"shoff={self.shoff}, shnum={self.shnum}, shentsize={self.shentsize})")


class TemplateShdr:
    STRUCT_FORMAT = "4I"
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)

    def __init__(self, data):
        unpacked_data = struct.unpack(self.STRUCT_FORMAT, data)
        self.type, self.offset, self.size, self.entrysize = unpacked_data

    def __repr__(self):
        return (f"TemplateShdr(type={self.type}, offset={self.offset}, "
                f"size={self.size}, entrysize={self.entrysize})")


class LibraryInfo:
    STRUCT_FORMAT = "I16s4I"
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)

    def __init__(self, data):
        unpacked_data = struct.unpack(self.STRUCT_FORMAT, data)
        self.name_ptr = unpacked_data[0]
        self.md5 = unpacked_data[1]
        self.hotbbs_start = unpacked_data[2]
        self.hotbbs_end = unpacked_data[3]
        self.coldbbs_start = unpacked_data[4]
        self.coldbbs_end = unpacked_data[5]

    def __repr__(self):
        md5_hex = self.md5.hex()
        return (f"LibraryInfo(name_ptr={self.name_ptr}, md5={md5_hex}, "
                f"hotbbs_start={self.hotbbs_start}, hotbbs_end={self.hotbbs_end}, "
                f"coldbbs_start={self.coldbbs_start}, coldbbs_end={self.coldbbs_end})")


def get_hotlibrary_header(filename):
    with open(filename, "rb") as f:
        data = f.read(28)
        template_header = Templatehdr(data)
        return template_header


def get_hotlibrary_section_table(filename):
    template_header = get_hotlibrary_header(filename)
    shoff = template_header.shoff
    shnum = template_header.shnum
    shdr_list = []
    with open(filename, "rb") as f:
        f.seek(shoff)
        for _ in range(shnum):
            data = f.read(TemplateShdr.STRUCT_SIZE)
            if len(data) < TemplateShdr.STRUCT_SIZE:
                break
            shdr_list.append(TemplateShdr(data))
    return shdr_list


def get_hotlibrary_depend_table(filename):
    sections_table = get_hotlibrary_section_table(filename)

    for item in sections_table:
        if (item.type == 0):
            depend_section = item
            break

    depend_table_off = depend_section.offset
    num = int(depend_section.size/depend_section.entrysize)

    library_info_list = []
    library_info_dict = {}
    with open(filename, "rb") as f:
        f.seek(depend_table_off)

        for _ in range(num):
            data = f.read(LibraryInfo.STRUCT_SIZE)
            if len(data) < LibraryInfo.STRUCT_SIZE:
                break
            library_info_list.append(LibraryInfo(data))

        for item in library_info_list:
            f.seek(item.name_ptr)
            string = f.read().split(b'\x00', 1)[0]
            name = string.decode('utf-8', errors='ignore')
            library_info_dict[name] = item

    return library_info_dict

#ifndef HOT_LIBRARY_H // Prevent multiple inclusions of the header file
#define HOT_LIBRARY_H

typedef struct
{
    uint32_t info_off;
    uint32_t info_size;
    uint32_t text_off;
    uint32_t text_size;
    uint32_t shoff;
    uint32_t shnum;
    uint32_t shentsize;
} Templatehdr;

typedef struct
{
    uint32_t type;      // 4 bytes
    uint32_t offset;    // 4 bytes
    uint32_t size;      // 4 bytes
    uint32_t entrysize; // 4 bytes
} TemplateShdr;

typedef struct
{
    uint32_t name_ptr;      // 4 bytes
    unsigned char md5[16];  // 16 bytes
    uint32_t hotbbs_start;  // 4 bytes
    uint32_t hotbbs_end;    // 4 bytes
    uint32_t coldbbs_start; // 4 bytes
    uint32_t coldbbs_end;   // 4 bytes
} LibraryInfo;

typedef struct
{
    uint32_t name_ptr;  // 4 bytes
    uint32_t offset;    // 4 bytes
    uint32_t size;      // 4 bytes
    uint32_t entrysize; // 4 bytes
} LibRelocationInfo;

typedef struct
{
    uint16_t r_type;          // 2 bytes
    uint16_t dist_next_instr; // 2 bytes
    uint32_t r_offset;        // 4 bytes
    uint32_t r_hot_target;    // 4 bytes
} TextRela;

typedef struct
{
    uint32_t r_type;       // 4 bytes
    uint32_t r_offset;     // 4 bytes
    uint32_t r_hot_target; // 4 bytes
} GotRela;

typedef struct
{
    uint64_t dso_baseaddr;
    uint64_t plt_rela_num;
    TextRela *plt_relocations;
} LibPltRelaInfo;

typedef struct
{
    uint64_t dso_baseaddr;
    uint64_t got_rela_num;
    GotRela *got_relocations;
} LibGotRelaInfo;

typedef struct
{
    uint64_t code_baseaddr;
    char *name;
    char *cfg_path;
    LibGotRelaInfo *total_got_relocations;
    uint64_t got_lib_num;
    LibPltRelaInfo *total_plt_relocations;
    uint64_t plt_lib_num;
    uint32_t index;

} HotLibraryMap;

void print_sectionheader(const TemplateShdr *header)
{
    printf("type: %u\t", header->type);
    printf("offset: %u\t", header->offset);
    printf("size: %u\t", header->size);
    printf("entrysize: %u\n", header->entrysize);
}

// Print the contents of the Templatehdr structure
void print_templatehdr(const Templatehdr *hdr)
{
    printf("info_off: %u\t", hdr->info_off);
    printf("info_size: %u\t", hdr->info_size);
    printf("text_off: %u\t", hdr->text_off);
    printf("text_size: %u\n", hdr->text_size);
    printf("shoff: %u\t", hdr->shoff);
    printf("shnum: %u\t", hdr->shnum);
    printf("shentsize: %u\t", hdr->shentsize);
}

void print_library_info(const LibraryInfo *info)
{
    /*printf("MD5: ");
    for (int i = 0; i < 16; i++)
    {
        printf("%02x", info->md5[i]);
    }*/
    printf("\n");
    printf("Hot BBS Start: %u\t", info->hotbbs_start);
    printf("Hot BBS End: %u\t", info->hotbbs_end);
    printf("Cold BBS Start: %u\t", info->coldbbs_start);
    printf("Cold BBS End: %u\n", info->coldbbs_end);
}

void print_lib_relocation_info(LibRelocationInfo *info)
{
    printf("Name Pointer: 0x%x\t", info->name_ptr);
    printf("Offset: 0x%x\t", info->offset);
    printf("Size: 0x%x\t", info->size);
    printf("Entry Size: 0x%x\n", info->entrysize);
}

#endif

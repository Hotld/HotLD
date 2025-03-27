#ifndef LOAD_HOTLIBRARY_H
#define LOAD_HOTLIBRARY_H
#include <sys/stat.h>
#include <stdio.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <stdint.h>
#include <string.h>
#include "hot_library.h"
#include "utils.h"

typedef struct
{
    const char *name;
    uint64_t start_address;
    uint64_t end_address;
} LibraryLibInfo;

LibraryLibInfo *libraries = NULL;
size_t libraries_count = 0;
HotLibraryMap *HotlibMaps = NULL;
size_t HotlibMapsNum = 0;

int cur_Hotlibray_index = -1;
int next_Hotlibray_index = 0;

uint64_t find_dso_baseaddr(char *dso_name)
{
    for (size_t i = 0; i < libraries_count; i++)
    {
        LibraryLibInfo *lib_info = &libraries[i];
        if (strcmp(lib_info->name, dso_name) == 0)
        {
            /*
            printf("find dso baseaddr: %s %lx %lx\n", lib_info->name,
                   lib_info->start_address,
                   lib_info->end_address);*/
            return lib_info->start_address;
        }
    }
    return -1;
}

void process_got_rela(uint64_t dso_baseaddr, uint64_t hot_text_start, GotRela *rela, size_t count)
{
    GotRela *cur_rela = rela;

    for (size_t i = 0; i < count; i++)
    {

        uint64_t *r_offset =
            (uint64_t *)((uint64_t)cur_rela->r_offset + dso_baseaddr);
        uint32_t r_type = cur_rela->r_type;
        // printf("exter relocation: r_type: %d, r_offset: %lx, baseaddr: %lx \n",
        // r_type, (uint64_t)cur_rela->r_offset + dso_baseaddr, dso_baseaddr);

        switch (r_type)
        {
        case R_X86_64_64:
        case R_X86_64_RELATIVE:
        case R_X86_64_GLOB_DAT:
        case R_X86_64_JUMP_SLOT:
            uint64_t target_addr = (uint64_t)(cur_rela->r_hot_target) +
                                   (uint64_t)hot_text_start;
            *r_offset = target_addr;
            if (dl_print_debug)
                printf("exter relocation: r_type: %d, r_offset: %lx, r_target:%lx\n ",
                       r_type, (uint64_t)r_offset, target_addr);

            break;

        default:
            printf("[ERROR] unprocess Got relocation \n");
            break;
        }
        cur_rela++;
    }
}

void rewrite_plt_rela(uint64_t dso_baseaddr, uint64_t hot_text_start, TextRela *rela, size_t count)
{
    TextRela *cur_rela = rela;
    for (size_t i = 0; i < count; i++)
    {
        uint64_t r_offset =
            cur_rela->r_offset + (uint64_t)hot_text_start;

        if (dl_print_debug)
            printf(
                "rewrite plt_rela(779), rela_offset: %lx, target_offset:%x\n",
                r_offset, cur_rela->r_hot_target);

        u_int64_t plt_addr = cur_rela->r_hot_target + dso_baseaddr;
        u_int64_t target_addr = plt_addr;
        u_int64_t got_addr = plt_addr;

        u_int64_t plt_got_offset = 0;
        uint8_t *byte_address = (uint8_t *)plt_addr;

        if (byte_address[0] == 0xff && byte_address[1] == 0x25)
            plt_got_offset = plt_addr + 2;
        else if (__glibc_likely((byte_address[0] == 0xf3 &&
                                 byte_address[1] == 0x0f)))
            plt_got_offset = plt_addr + 4 + 3;
        else
            printf(
                "[ERROR] unprocess plt type, not gcc and llvm\n");

        if (plt_got_offset != 0)
        {
            int32_t *int_address = (int32_t *)plt_got_offset;
            int32_t value = *int_address;
            got_addr = plt_got_offset + 4 + value;
            Elf64_Addr func_addr = *((Elf64_Addr *)got_addr);
            target_addr = func_addr;
        }

        int64_t offset = (int64_t)target_addr - (int64_t)r_offset -
                         (int64_t)cur_rela->dist_next_instr;

        if ((__glibc_unlikely(offset <= INT32_MIN)) |
            (__glibc_unlikely(offset >= INT32_MAX)))
        {
            offset = (int64_t)plt_addr - (int64_t)r_offset -
                     (int64_t)cur_rela->dist_next_instr;
            ;
            *((int32_t *)r_offset) = (int32_t)offset;
            if (dl_print_debug)
                printf(
                    "The distance between got value and rela offset is "
                    "too big, target_function: %lx rela_offset: %lx "
                    "plt_offset: %lx\n",
                    target_addr, r_offset, plt_addr);
        }
        else
        {
            *((int32_t *)r_offset) = (int32_t)offset;
        }
    }
}

LibPltRelaInfo process_text_rela(uint64_t dso_baseaddr, uint64_t hot_text_start, TextRela *rela, size_t count)
{
    // printf("process text relacation start!\n");
    LibPltRelaInfo cur_plt_infos;
    size_t capacity = 2;
    TextRela *result = (TextRela *)(malloc(capacity * sizeof(TextRela)));
    if (result == NULL)
    {
        printf("Memory allocation failed\n");
        return cur_plt_infos;
    }
    size_t result_count = 0;

    TextRela *cur_rela = rela;

    for (size_t i = 0; i < count; i++)
    {
        uint64_t r_offset =
            cur_rela->r_offset + (uint64_t)hot_text_start;

        if (dl_print_debug)
            printf(
                "type:%d, rela_offset: %lx, target_offset:%x\n",
                cur_rela->r_type, r_offset, cur_rela->r_hot_target);

        switch (cur_rela->r_type)
        {
        case 776:
        case 779:
            uint64_t target_addr = cur_rela->r_hot_target + dso_baseaddr;
            int64_t offset = (int64_t)target_addr - (int64_t)r_offset -
                             (int64_t)cur_rela->dist_next_instr;
            if ((__glibc_unlikely(offset <= INT32_MIN)) |
                (__glibc_unlikely(offset >= INT32_MAX)))
            {
                printf(
                    "[ERROR] The distance between got value and rela "
                    "offset is too big %lx %lx\n",
                    r_offset, offset);
            }
            *((int32_t *)r_offset) = (int32_t)offset;
            if (cur_rela->r_type == 779)
            {

                if (result_count >= capacity)
                {
                    capacity *= 2;
                    TextRela *new_result = (TextRela *)(realloc(result, capacity * sizeof(TextRela)));
                    if (new_result == NULL)
                    {
                        printf("Memory allocation failed\n");
                        free(result);
                        return cur_plt_infos;
                    }
                    result = new_result;
                }
                result[result_count] = *cur_rela;
                result_count++;
            }
            break;
        case 777:
        case 778:
            target_addr = cur_rela->r_hot_target + hot_text_start;
            offset = (int64_t)target_addr - (int64_t)r_offset -
                     (int64_t)cur_rela->dist_next_instr;
            *((int32_t *)r_offset) = (int32_t)offset;
            break;
        default:
            printf(
                "[ERROR] unprocess relocation inter item %lx, type: %d\n",
                r_offset, cur_rela->r_type);
            break;
        }
        cur_rela++;
    }

    cur_plt_infos.dso_baseaddr = dso_baseaddr;
    cur_plt_infos.plt_rela_num = result_count;
    cur_plt_infos.plt_relocations = result;
    // printf("process text relacation finish! plt_num: %ld\n", cur_plt_infos.plt_rela_num);
    return cur_plt_infos;
}

void load_hot_library(HotLibraryMap *map)
{
    char *ht_total_path = map->name;
    int fd;

    // 1. open HotLibrary
    fd = open(ht_total_path, O_RDONLY);
    if (fd == -1)
    {
        printf("open %s fail\n", ht_total_path);
        return;
    }

    struct stat ht_file_st;

    if (fstat(fd, &ht_file_st) == -1)
    {
        printf("fstat");
        close(fd);
        return;
    }

    void *mapped_data = mmap(NULL, ht_file_st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (mapped_data == MAP_FAILED)
    {
        printf("Failed to map file to memory");
        close(fd);
        return;
    }
    Templatehdr *header = (Templatehdr *)mapped_data;

    // print_templatehdr(header);
    uint32_t info_size = header->info_size;
    uint32_t code_offset = header->text_off;
    uint32_t code_size = header->text_size;

    void *hot_text_start = mmap(NULL, code_size, PROT_READ | PROT_WRITE | PROT_EXEC,
                                MAP_PRIVATE | MAP_POPULATE | MAP_ANONYMOUS, -1, 0);
    if (hot_text_start == MAP_FAILED)
    {
        printf("small hot text mmap failed\n");
        return;
    }

    // printf("hot text start %lx\n", (uint64_t)hot_text_start);
    memcpy(hot_text_start, (char *)mapped_data + code_offset, code_size);
    map->code_baseaddr = (uint64_t)hot_text_start;
    //  print_templatehdr(header);

    TemplateShdr *section_headers = (TemplateShdr *)((char *)mapped_data + header->shoff);
    uint32_t section_num = header->shnum;

    for (size_t i = 0; i < section_num; ++i)
    {
        TemplateShdr *cur_section = &section_headers[i];
        // printf("\n");
        // print_sectionheader(&section_headers[i]);
        switch (cur_section->type)
        {
        case 0:
            LibraryInfo *library_infos = (LibraryInfo *)((char *)mapped_data + cur_section->offset);
            uint32_t number = cur_section->size / cur_section->entrysize;
            /* code */
            break;
        case 1:
            LibRelocationInfo *got_relocation_table = (LibRelocationInfo *)((char *)mapped_data + cur_section->offset);
            number = cur_section->size / cur_section->entrysize;
            LibGotRelaInfo *got_infos = (LibGotRelaInfo *)(malloc(number * sizeof(LibGotRelaInfo)));
            map->got_lib_num = number;
            map->total_got_relocations = got_infos;
            for (size_t i = 0; i < number; i++)
            {
                char *library_name = (char *)mapped_data + got_relocation_table[i].name_ptr;
                // printf("Library name: %u %s \n", got_relocation_table[i].name_ptr, library_name);
                // print_lib_relocation_info(&got_relocation_table[i]);

                uint64_t dso_baseaddr = find_dso_baseaddr(library_name);
                if (dso_baseaddr == -1)
                {
                    printf("[ERROR] can't find baseaddr of library %s \n", library_name);
                    return;
                }

                GotRela *relocations = (GotRela *)((char *)mapped_data + got_relocation_table[i].offset);
                uint32_t got_number = got_relocation_table[i].size / got_relocation_table[i].entrysize;
                GotRela *relocations_data = (GotRela *)(malloc(got_relocation_table[i].size));
                memcpy(relocations_data, relocations, got_relocation_table[i].size);
                map->total_got_relocations[i].dso_baseaddr = dso_baseaddr;
                map->total_got_relocations[i].got_rela_num = got_number;
                map->total_got_relocations[i].got_relocations = relocations_data;

                // process_got_rela(dso_baseaddr, (uint64_t)hot_text_start, relocations, got_number);
            }
            break;
        case 2:
            LibRelocationInfo *text_relocation_table = (LibRelocationInfo *)((char *)mapped_data + cur_section->offset);
            number = cur_section->size / cur_section->entrysize;
            LibPltRelaInfo *plt_infos = (LibPltRelaInfo *)(malloc(number * sizeof(LibPltRelaInfo)));
            map->plt_lib_num = number;
            map->total_plt_relocations = plt_infos;

            for (size_t i = 0; i < number; i++)
            {
                char *library_name = (char *)mapped_data + text_relocation_table[i].name_ptr;
                // printf("Library name: %u %s \n", text_relocation_table[i].name_ptr, library_name);
                // print_lib_relocation_info(&text_relocation_table[i]);

                uint64_t dso_baseaddr = find_dso_baseaddr(library_name);
                if (dso_baseaddr == -1)
                {
                    printf("[ERROR] can't find baseaddr of library %s \n", library_name);
                    return;
                }

                TextRela *relocations = (TextRela *)((char *)mapped_data + text_relocation_table[i].offset);
                uint32_t text_number = text_relocation_table[i].size / text_relocation_table[i].entrysize;

                LibPltRelaInfo cur_plt_infos = process_text_rela(dso_baseaddr, (uint64_t)hot_text_start, relocations, text_number);
                map->total_plt_relocations[i] = cur_plt_infos;
            }
            break;

        case 3:
            // symtab = (char *)mapped_data + cur_section->offset;
            break;
        case 4:
            break;

        default:
            printf("Unprocess section type");
            break;
        }
    }

    if (munmap(mapped_data, info_size) == -1)
    {
        printf("Failed to unmap memory");
    }
    close(fd);

    return;
}

void link_hotLibrary_got(HotLibraryMap *map)
{
    // printf("process got relacation start!\n");
    for (size_t i = 0; i < map->got_lib_num; i++)
    {
        GotRela *relocations = map->total_got_relocations[i].got_relocations;
        uint64_t dso_baseaddr = map->total_got_relocations[i].dso_baseaddr;
        size_t number = map->total_got_relocations[i].got_rela_num;
        process_got_rela(dso_baseaddr, map->code_baseaddr, relocations, number);
    }
    // printf("process got relacation finish!\n");
}

void link_hotLibrary_plt(HotLibraryMap *map)
{
    if (dl_rewrite_indictCall)
    {
        // printf("process plt relacation start!\n");
        for (size_t i = 0; i < map->plt_lib_num; i++)
        {
            TextRela *relocations = map->total_plt_relocations[i].plt_relocations;
            uint64_t dso_baseaddr = map->total_plt_relocations[i].dso_baseaddr;
            size_t number = map->total_plt_relocations[i].plt_rela_num;
            rewrite_plt_rela(dso_baseaddr, map->code_baseaddr, relocations, number);
        }
        // printf("process plt relacation finish!\n");
    }
}

#endif
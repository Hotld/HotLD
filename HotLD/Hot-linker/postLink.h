#ifndef POSTLINK_H
#define POSTLINK_H
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <link.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <elf.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include "hot_library.h"
#include "utils.h"
#include "load_hotLibrary.h"

char *get_exec_path()
{
    static char exec_path[1024];
    ssize_t len = readlink("/proc/self/exe", exec_path, sizeof(exec_path) - 1);

    if (len == -1)
    {
        perror("readlink");
        return NULL;
    }

    exec_path[len] = '\0';
    return exec_path;
}

// Callback function to extract and save library information to a dynamic array
int callback(struct dl_phdr_info *info, size_t size, void *data)
{
    // Increase the library count and reallocate memory
    libraries_count++;
    libraries = (LibraryLibInfo *)realloc(libraries, libraries_count * sizeof(LibraryLibInfo));
    if (!libraries)
    {
        perror("Failed to allocate memory for libraries");
        exit(1);
    }

    // Get the library namec
    libraries[libraries_count - 1].name = strdup(info->dlpi_name);
    if ((libraries[libraries_count - 1].name == NULL) || libraries[libraries_count - 1].name[0] == '\0')
    {
        // If the name is not found, use the executable path as the library name
        char *exe_path = get_exec_path();
        libraries[libraries_count - 1].name = exe_path;
    }

    // Get the start address of the library
    libraries[libraries_count - 1].start_address = (uint64_t)info->dlpi_addr;
    // printf("Library: %s, Start Address: %lx\n", libraries[libraries_count - 1].name, libraries[libraries_count - 1].start_address);

    // Iterate over the program header table to calculate the end address
    uint64_t end_address = (uint64_t)info->dlpi_addr;
    for (int i = 0; i < info->dlpi_phnum; i++)
    {
        ElfW(Phdr) *phdr = (ElfW(Phdr) *)(&info->dlpi_phdr[i]);
        if (phdr->p_type == PT_LOAD)
        {
            uint64_t current_end = (uint64_t)(phdr->p_vaddr + phdr->p_memsz);
            if (current_end > end_address)
            {
                end_address = current_end;
            }
        }
    }
    libraries[libraries_count - 1].end_address = end_address;

    return 0;
}

int save_hot_libraries_mmap()
{
    pid_t pid = getpid();
    const char *hotld_dir = getenv("HOME");

    if (hotld_dir == NULL)
    {
        fprintf(stderr, "Error: The environment variable HOME is not defined.\n");
        return -1;
    }

    char tempFileName[256];
    if (snprintf(tempFileName, sizeof(tempFileName), "%s/hotld/tmp/mapinfo_%d.txt", hotld_dir, pid) >= sizeof(tempFileName))
    {
        fprintf(stderr, "Error: The file path is too long.\n");
        return -1;
    }
    printf("[HOTLD] Temporary file path: %s\n", tempFileName);

    FILE *tempFile = fopen(tempFileName, "w+");
    if (tempFile == NULL)
    {
        perror("Error: Unable to create temporary file");
        return -1;
    }

    for (int i = 0; i < HotlibMapsNum; i++)
    {
        if (fprintf(tempFile, "%d %s %s %lx\n", HotlibMaps[i].index, HotlibMaps[i].name, HotlibMaps[i].cfg_path, HotlibMaps[i].code_baseaddr) < 0)
        {
            fprintf(stderr, "Error: Failed to write to file\n");
            fclose(tempFile);
            return -1;
        }
    }

    if (fclose(tempFile) != 0)
    {
        perror("Error: Failed to close the file");
        return -1;
    }

    return 0;
}
static void __attribute_used__ smart_dynamic_loader_operations(char *exe_file)
{
    if (dl_iterate_phdr(callback, NULL) == 0)
    {
        if (libraries_count == 0)
            printf("No libraries found.\n");
    }
    if (dl_print_libs)
    {
        for (size_t i = 0; i < libraries_count; i++)
        {
            LibraryLibInfo *lib_info = &libraries[i];
            if (i == 0)
            {
                lib_info->name = exe_file;
            }
            printf("Library: %s\t", lib_info->name);
            printf("  Start Address: 0x%lx\t", lib_info->start_address);
            printf("  End Address: 0x%lx\n", lib_info->end_address);
            // print_section_info(lib_info->name);
        }
    }

    if (_dl_hot_template_path != NULL)
    {
        for (size_t i = 0; i < libraries_count; i++)
        {
            LibraryLibInfo *lib_info = &libraries[i];
            // printf("Library: %s\n", lib_info->name);
            if (strcmp(lib_info->name, "linux-vdso.so.1") == 0)
                continue;

            chmod_got_section(lib_info->name, lib_info->start_address);
        }
        struct timeval start, end;
        double elapsed_time;

        gettimeofday(&start, NULL);

        HotLibraryMap map;
        map.name = _dl_hot_template_path;
        load_hot_library(&map);
        link_hotLibrary_got(&map);
        link_hotLibrary_plt(&map);

        gettimeofday(&end, NULL);
        elapsed_time = (end.tv_sec - start.tv_sec) + (end.tv_usec - start.tv_usec) / 1000.0;

        printf("switch time: %f ms\n", elapsed_time);
    }
    else if (dl_multi_librarys != NULL)
    {
        for (size_t i = 0; i < libraries_count; i++)
        {
            LibraryLibInfo *lib_info = &libraries[i];
            // printf("Library: %s\n", lib_info->name);
            if (strcmp(lib_info->name, "linux-vdso.so.1") == 0)
                continue;

            chmod_got_section(lib_info->name, lib_info->start_address);
        }

        char *hot_libraries_info_path = dl_multi_librarys;
        FILE *file = fopen(hot_libraries_info_path, "r");
        if (file == NULL)
        {
            perror("can't open file");
            return;
        }

        int n;
        fscanf(file, "%d", &n);
        HotlibMapsNum = n;
        HotlibMaps = (HotLibraryMap *)malloc(sizeof(HotLibraryMap) * n);
        if (!HotlibMaps)
        {
            perror("malloc failed");
            fclose(file);
            return;
        }
        for (int i = 0; i < n; i++)
        {
            HotlibMaps[i].name = (char *)malloc(1024 * sizeof(char));
            HotlibMaps[i].cfg_path = (char *)malloc(1024 * sizeof(char));

            if (fscanf(file, "%d %s %s",
                       &HotlibMaps[i].index,
                       HotlibMaps[i].name,
                       HotlibMaps[i].cfg_path) != 3)
            {
                printf("Failed to read data from line %d\n", i + 1);
                free(HotlibMaps[i].name);
                continue;
            }
        }
        for (int i = 0; i < n; i++)
        {
            HotLibraryMap *map = &HotlibMaps[i];
            load_hot_library(map);
        }

        int result = 0;
        result = save_hot_libraries_mmap();
    }
    free(libraries);
}
#endif
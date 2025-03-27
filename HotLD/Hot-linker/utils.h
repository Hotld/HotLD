#ifndef UTILS_H
#define UTILS_H
#include <stdio.h>
#include <stdlib.h>
#include <elf.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <string.h>

int dl_rewrite_indictCall = 1;
int dl_print_debug = 0;
int dl_print_libs = 0;
int dl_load_time = 0;
char *_dl_hot_template_path = NULL;
char *dl_multi_librarys = NULL;

void parse_envs()
{
    char *env_var = getenv("HOTLD_PRINT_LIBS");
    if (env_var != NULL)
    {
        dl_print_libs = 1;
        printf("HOTLD_PRINT_LIBS : %s\n", env_var);
    }

    env_var = getenv("HOTLD_PRINT_DEBUG");
    if (env_var != NULL)
    {
        dl_print_debug = 1;
        printf("HOTLD_PRINT_DEBUG : %s\n", env_var);
    }

    env_var = getenv("HOTLD_REWRITE_PLT");
    if (env_var != NULL)
    {
        dl_rewrite_indictCall = 0;
        printf("HOTLD_REWRITE_PLT : %s\n", env_var);
    }

    env_var = getenv("HOTLD_HOT_LIBRARY");

    if (env_var != NULL)
    {
        _dl_hot_template_path = env_var;
        printf("HOTLD_HOT_LIBRARY : %s\n", _dl_hot_template_path);
    }

    env_var = getenv("HOTLD_HOT_LIBRARIES");

    if (env_var != NULL)
    {
        dl_multi_librarys = env_var;
        printf("[HOTLD] HOTLD_HOT_LIBRARIES : %s\n", dl_multi_librarys);
    }
}

void __chmod_got(u_int64_t baseaddr, Elf64_Shdr *section, char *section_name)
{
    int page_size = getpagesize();
    uint64_t section_addr = baseaddr + (uint64_t)section->sh_addr;
    uint64_t section_size = section->sh_size;
    uint64_t start_page = (section_addr) &
                          ~(page_size - 1);
    uint64_t end_page = ((start_page + section_size) &
                         ~(page_size - 1)) +
                        page_size;
    int res = -1;
    res = mprotect((void *)(start_page), end_page - start_page,
                   PROT_READ | PROT_WRITE);
    if (res != 0)
    {
        printf("%s: %lx\n", "change r/w segment fail",
               start_page);
        return;
    }
}
void chmod_got_section(const char *elf_file, u_int64_t baseaddr)
{
    int fd = open(elf_file, O_RDONLY);
    if (fd == -1)
    {
        perror("Failed to open ELF file");
        return;
    }

    struct stat st;
    if (fstat(fd, &st) == -1)
    {
        perror("fstat failed");
        return;
    }

    void *map = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (map == MAP_FAILED)
    {
        perror("mmap failed");
        return;
    }

    Elf64_Ehdr *ehdr = (Elf64_Ehdr *)map;

    if (memcmp(ehdr->e_ident, ELFMAG, SELFMAG) != 0)
    {
        printf("Not a valid ELF file\n");
        return;
    }

    Elf64_Shdr *shdr = (Elf64_Shdr *)((char *)map + ehdr->e_shoff);

    Elf64_Shdr *strtab_header = &shdr[ehdr->e_shstrndx];
    char *strtab = (char *)map + strtab_header->sh_offset;

    for (int i = 0; i < ehdr->e_shnum; i++)
    {
        Elf64_Shdr *section = &shdr[i];
        char *section_name = strtab + section->sh_name;

        if ((strcmp(section_name, ".got") == 0))
        {
            __chmod_got(baseaddr, section, section_name);
        }
        if ((strcmp(section_name, ".got.plt") == 0))
        {
            __chmod_got(baseaddr, section, section_name);
        }
        if ((strcmp(section_name, ".data.rel.ro") == 0))
        {
            __chmod_got(baseaddr, section, section_name);
        }
    }

    munmap(map, st.st_size);
    close(fd);
}
#endif
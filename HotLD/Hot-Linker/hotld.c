#define _GNU_SOURCE
#include <link.h>
#include <stdio.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>
#include "postLink.h"
#include <sys/time.h>

#define SOCKET_PATH_TEMPLATE "/tmp/hotld_%d_socket"

typedef int (*libc_start_main_t)(int (*main)(int, char **, char **), int argc, char **argv,
                                 void (*init)(), void (*fini)(), void (*rtld_fini)(), void *stack_end);

libc_start_main_t original_libc_start_main = NULL;

static int server_fd = -1;
static pthread_t monitor_thread_id;

void *monitor_thread(void *arg)
{
    int client_fd;
    struct sockaddr_un addr;
    int monitored_value = -1;

    pid_t pid = getpid();
    char socket_path[108];
    snprintf(socket_path, sizeof(socket_path), SOCKET_PATH_TEMPLATE, pid);

    if ((server_fd = socket(AF_UNIX, SOCK_STREAM, 0)) == -1)
    {
        perror("[HOTLD] Socket creation failed");
        return NULL;
    }

    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);
    unlink(socket_path);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) == -1)
    {
        perror("[HOTLD] Bind failed");
        close(server_fd);
        return NULL;
    }

    if (listen(server_fd, 1) == -1)
    {
        perror("[HOTLD] Listen failed");
        close(server_fd);
        return NULL;
    }

    printf("[HOTLD] Listening on %s\n", socket_path);

    while ((client_fd = accept(server_fd, NULL, NULL)) != -1)
    {
        struct timeval start, end;
        double elapsed_time;
        gettimeofday(&start, NULL);

        read(client_fd, &monitored_value, sizeof(int));
        printf("[HOTLD] Received new value: %d\n", monitored_value);
        if (monitored_value != cur_Hotlibray_index)
        {
            if (monitored_value < HotlibMapsNum)
            {
                printf("[HOTLD] Choose HotLibrary %s\n\n", HotlibMaps[monitored_value].name);
                link_hotLibrary_got(&HotlibMaps[monitored_value]);
                link_hotLibrary_plt(&HotlibMaps[monitored_value]);
                link_hotLibrary_plt(&HotlibMaps[cur_Hotlibray_index]);
                cur_Hotlibray_index = monitored_value;
            }
        }
        close(client_fd);
        gettimeofday(&end, NULL);
        elapsed_time = (end.tv_sec - start.tv_sec) + (end.tv_usec - start.tv_usec) / 1000.0;

        printf("switch time: %f ms\n", elapsed_time);
    }
    return NULL;
}

void cleanup_resources(void)
{
    if (server_fd != -1)
    {
        close(server_fd);
        printf("[HOTLD] Socket closed\n");
    }

    if (monitor_thread_id)
    {
        pthread_cancel(monitor_thread_id);
        pthread_join(monitor_thread_id, NULL);
        printf("[HOTLD] Monitor thread stopped\n");
    }
}

int __libc_start_main(int (*main)(int, char **, char **), int argc, char **argv,
                      void (*init)(), void (*fini)(), void (*rtld_fini)(), void *stack_end)
{
    struct timeval start, end;
    double elapsed_time;

    gettimeofday(&start, NULL);
    char *exe_file = argv[0];
    //  printf("exe_file: %s\n", exe_file);

    parse_envs();

    if (dl_multi_librarys != NULL)
    {
        if (pthread_create(&monitor_thread_id, NULL, monitor_thread, NULL) != 0)
        {
            perror("pthread_create failed");
            exit(1);
        }
        pthread_detach(monitor_thread_id);
    }

    smart_dynamic_loader_operations(exe_file);
    gettimeofday(&end, NULL);
    elapsed_time = (end.tv_sec - start.tv_sec) + (end.tv_usec - start.tv_usec) / 1000.0;

    printf("Load time: %f ms\n", elapsed_time);

    return original_libc_start_main(main, argc, argv, init, fini, rtld_fini, stack_end);
}

__attribute__((constructor)) void my_init()
{

    original_libc_start_main = (libc_start_main_t)dlsym(RTLD_NEXT, "__libc_start_main");

    if (original_libc_start_main == NULL)
    {
        fprintf(stderr, "Error: Could not find original __libc_start_main\n");
        exit(1);
    }
}

__attribute__((destructor)) void library_cleanup(void)
{
    cleanup_resources();
}
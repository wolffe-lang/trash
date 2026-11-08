/* census/fixture/mkname.c: the census's one fixture no shell can be trusted
 * with — bytes that are not UTF-8, in a name and in an argument. pelt, PAX's
 * shell, turns such a byte into '?' in a command substitution and refuses a
 * script that holds one (pelt#20), so the census makes them here.
 *
 *   mkname file DIR HEX          creates DIR/NAME, NAME's bytes given in hex
 *   mkname exec PROG LABEL HEX   runs PROG with the arguments LABEL and the bytes
 *
 * Exit 0, or 1 with a line on standard error. Calls: open(2), execv(2).
 */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static char *unhex(const char *h) {
    size_t n = strlen(h) / 2;
    char *b = malloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        unsigned v;
        if (sscanf(h + 2 * i, "%2x", &v) != 1) { fprintf(stderr, "mkname: bad hex\n"); exit(1); }
        b[i] = (char)v;
    }
    b[n] = 0;
    return b;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "file") == 0) {
        char *name = unhex(argv[3]);
        size_t len = strlen(argv[2]) + 1 + strlen(name) + 1;
        char *path = malloc(len);
        snprintf(path, len, "%s/%s", argv[2], name);
        int fd = open(path, O_CREAT | O_EXCL | O_WRONLY, 0644);
        if (fd < 0) { perror("mkname: open"); return 1; }
        close(fd);
        return 0;
    }
    if (argc == 5 && strcmp(argv[1], "exec") == 0) {
        char *args[] = {argv[2], argv[3], unhex(argv[4]), NULL};
        execv(argv[2], args);
        perror("mkname: execv");
        return 1;
    }
    fprintf(stderr, "usage: mkname file DIR HEX | mkname exec PROG LABEL HEX\n");
    return 1;
}

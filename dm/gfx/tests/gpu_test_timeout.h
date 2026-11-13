#ifndef GPU_TEST_TIMEOUT_H
#define GPU_TEST_TIMEOUT_H
#include <stdio.h>
#include <stdlib.h>
// Do not unwind ARC objects or run exit handlers after a GPU timeout: cleanup
// may itself wait forever. Only the isolated test process is terminated.
static inline _Noreturn void gpu_test_timeout(void) {
    fputs("FAIL: bounded GPU wait timed out; exiting without GPU cleanup\n", stderr);
    _Exit(1);
}
#endif

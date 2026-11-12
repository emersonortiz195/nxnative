#include "../nvn/nvn_mem_guard.h"
#include <assert.h>
// Model the same two identity sets used by the Metal integration.
static uint64_t total(unsigned committed, unsigned pending) {
    uint64_t sum = 0;
    for (unsigned i = 0; i < 3; i++) {
        unsigned bit = 1u << i;
        if (committed & bit) sum = nvn_mem_guard_add(sum, 100);
        if (pending & bit) sum = nvn_mem_guard_add(sum, nvn_mem_guard_extra(100, committed & bit));
    }
    return sum;
}
static void transitions(void) {
    unsigned committed = 0, pending = 0;
    assert(total(committed, pending) == 0);
    pending |= 1; assert(total(committed, pending) == 100);
    pending |= 1; assert(total(committed, pending) == 100); // repeated add
    pending &= ~1u; assert(total(committed, pending) == 0); // remove before first commit
    pending |= 1; assert(total(committed, pending) == 100);
    committed = pending; assert(total(committed, pending) == 100);
    pending &= ~1u; assert(total(committed, pending) == 100); // removal awaits commit
    pending |= 1; assert(total(committed, pending) == 100); // remove/re-add committed
    pending |= 2; assert(total(committed, pending) == 200); // distinct, possibly overlapping buffers
    pending &= ~2u; pending |= 2; assert(total(committed, pending) == 200);
    committed = pending; assert(total(committed, pending) == 200);
    pending = 0; assert(total(committed, pending) == 200);
    committed = pending; assert(total(committed, pending) == 0);
}
int main(void) {
    transitions();
    assert(nvn_mem_guard_limit(199) == 189);
    assert(nvn_mem_guard_limit(UINT64_MAX) < UINT64_MAX);
    assert(!nvn_mem_guard_low(199, 51, 101));
    assert(nvn_mem_guard_low(199, 50, 100));
    assert(nvn_mem_guard_limit(10000) == 9500);
    assert(!nvn_mem_guard_over(9499, 9500));
    assert(nvn_mem_guard_over(9500, 9500));
    assert(nvn_mem_guard_over(9501, 9500));
    assert(!nvn_mem_guard_over(UINT64_MAX, 0));
    assert(nvn_mem_guard_add(UINT64_MAX - 1, 2) == UINT64_MAX);
    assert(nvn_mem_guard_add(123, 456) == 579);
    assert(nvn_mem_guard_low(8000, 12, 1000));
    assert(!nvn_mem_guard_low(8000, 13, 1000));
    assert(!nvn_mem_guard_low(10000, 10, 1000));
    assert(nvn_mem_guard_low(8000, 0, 1000));
    assert(!nvn_mem_guard_low(8000, -1, 1000));
    assert(!nvn_mem_guard_low(8000, 101, 1000));
    assert(!nvn_mem_guard_low(0, 0, 1000));
    return 0;
}

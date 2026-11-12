#ifndef NVN_MEM_GUARD_H
#define NVN_MEM_GUARD_H
#include <stdint.h>
// A pending allocation contributes only if its identity is absent from the
// committed snapshot. Distinct overlapping allocations still contribute separately.
static inline uint64_t nvn_mem_guard_extra(uint64_t bytes, int committed) {
    return committed ? 0 : bytes;
}
// Pure policy helpers, shared with the CPU-only boundary tests.
static inline uint64_t nvn_mem_guard_add(uint64_t a, uint64_t b) {
    return b > UINT64_MAX - a ? UINT64_MAX : a + b;
}
static inline uint64_t nvn_mem_guard_limit(uint64_t working_set) {
    return working_set / 100 * 95 + working_set % 100 * 95 / 100;
}
static inline int nvn_mem_guard_over(uint64_t resident, uint64_t limit) {
    return limit && resident >= limit;
}
static inline int nvn_mem_guard_low(uint64_t physical, int percent, uint64_t margin) {
    return physical && percent >= 0 && percent <= 100 && physical / 100 * (uint64_t)percent + physical % 100 * (uint64_t)percent / 100 < margin;
}
#endif

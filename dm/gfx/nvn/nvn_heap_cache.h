// Idle placement-heap metadata only. The caller holds the recycle lock, owns
// every entry, and removes residency/releases evicted heaps AFTER unlocking.
#ifndef NVN_HEAP_CACHE_H
#define NVN_HEAP_CACHE_H
#include <stdint.h>

typedef struct { void *heap; uint64_t size, t; } rh_ent;
static inline rh_ent rh_cache_remove(rh_ent *entries, unsigned *count, uint64_t *bytes, unsigned i) {
    rh_ent e = entries[i]; *bytes -= e.size; entries[i] = entries[--*count]; return e;
}
static inline unsigned rh_cache_oldest(const rh_ent *entries, unsigned count) {
    unsigned old = 0;
    for (unsigned i = 1; i < count; i++) if (entries[i].t < entries[old].t) old = i;
    return old;
}
// Make room for an incoming completed heap, evicting oldest idle entries. Plan
// first: if more than limit evictions would be needed, reject without disturbing
// the cache. At most limit scans; no allocation or driver calls under the lock.
static inline int rh_cache_room(rh_ent *entries, unsigned *count, uint64_t *bytes,
                                uint64_t size, uint64_t cap, rh_ent *drop,
                                unsigned *ndrop, unsigned limit) {
    *ndrop = 0;
    if (size > cap) return 0;
    if (*bytes <= cap - size) return 1;
    uint64_t left = *bytes, last_t = 0;
    unsigned last_i = 0, selected = 0;
    while (left > cap - size && selected < limit) {
        unsigned best = *count;
        for (unsigned i = 0; i < *count; i++) {
            if (selected && (entries[i].t < last_t || (entries[i].t == last_t && i <= last_i))) continue;
            if (best == *count || entries[i].t < entries[best].t || (entries[i].t == entries[best].t && i < best)) best = i;
        }
        if (best == *count) return 0;
        left -= entries[best].size; last_t = entries[best].t; last_i = best; selected++;
    }
    if (left > cap - size) return 0;
    // Descending original indices keep the cutoff stable despite swap removal:
    // an entry moved from the already visited tail is never examined again.
    for (unsigned i = *count; i-- > 0;) {
        if (entries[i].t < last_t || (entries[i].t == last_t && i <= last_i))
            drop[(*ndrop)++] = rh_cache_remove(entries, count, bytes, i);
    }
    return 1;
}
#endif

// Lifetime/lock check for diagnostics; fake allocations, no Metal device needed.
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int deallocs, unlocked;
static id keep;
@interface SnapshotAllocation : NSObject
@property(nonatomic, readonly) NSUInteger allocatedSize;
@end
@implementation SnapshotAllocation
- (NSUInteger)allocatedSize {
    // The allocation can retire while the snapshot is being queried. Its own
    // reference must keep it alive, and queries must permit residency locking.
    if (!pthread_mutex_trylock(&g_res_mu)) {
        unlocked++;
        [g_res_objects removeObject:self]; keep = nil;
        pthread_mutex_unlock(&g_res_mu);
    }
    return 12345;
}
- (void)dealloc { deallocs++; }
@end
int main(void) { @autoreleasepool {
    @autoreleasepool {
        g_res_objects = [NSHashTable weakObjectsHashTable];
        keep = [SnapshotAllocation new]; [g_res_objects addObject:keep];
    }
    unsigned long count = 0;
    uint64_t bytes = res_capacity_snapshot(&count);
    int ok = bytes == 12345 && count == 1 && unlocked == 1 && deallocs == 1 && !keep;
    // Repeat empty snapshots to ensure no stale retained snapshot survives.
    ok = ok && res_capacity_snapshot(&count) == 0 && count == 0;
    printf("t_res_snapshot: %s\n", ok ? "passed" : "FAILED");
    return !ok;
} }

// Exercise the actual recycle admission path, including a completion delayed
// behind a GPU event. No game data or shader archive is needed.
#include "../nvn/nvn_mtl.m"
#include "gpu_test_timeout.h"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int checks, failed;
#define CHECK(c, label) do { checks++; if (!(c)) { failed++; fprintf(stderr, "FAIL: %s (line %d)\n", label, __LINE__); } } while (0)
static int resident(id o) { pthread_mutex_lock(&g_res_mu); int r = [g_res_objects containsObject:o]; pthread_mutex_unlock(&g_res_mu); return r; }
static uint64_t idle(void) { os_unfair_lock_lock(&g_rh_lk); uint64_t n = g_rh_bytes; os_unfair_lock_unlock(&g_rh_lk); return n; }
static id<MTLHeap> heap(NSUInteger size) {
    MTLHeapDescriptor *d = [MTLHeapDescriptor new]; d.type = MTLHeapTypePlacement;
    d.storageMode = MTLStorageModePrivate; d.size = size;
    id<MTLHeap> h = [g_dev newHeapWithDescriptor:d];
    if (!h) { fputs("FAIL: test heap allocation failed\n", stderr); _Exit(1); }
    CHECK(h.size == size, "test heap has the requested aligned capacity");
    res_add(h); return h;
}
static void expire(void) {
    os_unfair_lock_lock(&g_rh_lk);
    for (unsigned i = 0; i < g_rh_n; i++) g_rh[i].t = 0;
    os_unfair_lock_unlock(&g_rh_lk);
    rh_trim();
}
int main(void) { @autoreleasepool {
    mtl_init(); mtl_sub_begin();
    enum { CHUNK = 4u << 20, COUNT = RH_CAP / CHUNK };
    NSMutableArray<id<MTLHeap>> *heaps = [NSMutableArray array];
    for (unsigned i = 0; i < COUNT + 1; i++) [heaps addObject:heap(CHUNK)];
    for (unsigned i = 0; i < COUNT; i++) rh_wait(heaps[i]);
    CHECK(idle() == RH_CAP, "exact budget is admitted");
    uint64_t rejected = g_rh_rejected, evicted = g_rh_evicted;
    rh_wait(heaps[COUNT]);
    CHECK(idle() == RH_CAP && g_rh_n == COUNT, "a return evicts within the budget before a submission");
    CHECK(resident(heaps[COUNT]) && !resident(heaps[0]), "incoming heap replaces the oldest idle heap");
    CHECK(g_rh_rejected == rejected && g_rh_evicted == evicted + 1, "eviction and rejection are counted separately");
    int reused = 0;
    id<MTLHeap> taken = rh_heap(CHUNK, MTLStorageModePrivate, MTLCPUCacheModeDefaultCache, MTLHazardTrackingModeDefault, &reused);
    CHECK(reused && idle() == RH_CAP - CHUNK && resident(taken), "reuse removes capacity from the idle budget without removing residency");
    rh_wait(taken); taken = nil;
    CHECK(idle() == RH_CAP && g_rh_rejected == rejected, "a taken heap can return to the exact budget");

    // Make a live texture while idle capacity is full. Its heap must stay
    // resident until the GPU copy finishes, then replace an idle heap.
    id<MTLHeap> live;
    id<MTLBuffer> output = [g_dev newBufferWithLength:64 * 64 * 8 options:MTLResourceStorageModeShared]; res_add(output);
    memset(output.contents, 0x5a, output.length);
    id<MTLSharedEvent> gate = [g_dev newSharedEvent];
    @autoreleasepool {
        MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:64 height:64 mipmapped:NO];
        d.storageMode = MTLStorageModePrivate; d.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        id<MTLTexture> t = rh_place(d); CHECK(t != nil, "live texture can allocate when the idle budget is full");
        live = t.heap; res_add(t); tex_zero_fill(t); up_flush(); rec_publish();
        [g_q4 waitForEvent:gate value:1];
        enc_b_copy_texture_buffer(blit(), t, 0, 0, MTLOriginMake(0, 0, 0), MTLSizeMake(64, 64, 1), output, 0, 64 * 8, output.length);
        defer_obj_release(t); t = nil;
    }
    uint64_t fence = mtl_sub_commit(); rec_publish(); defer_drain();
    CHECK(atomic_load(&g_done) < fence && resident(live), "delayed GPU completion keeps the retired texture's heap resident");
    CHECK(idle() == RH_CAP && g_rh_rejected == rejected, "in-flight texture has not entered recycle admission");
    int force_timeout = getenv("DM_TEST_RH_TIMEOUT") != NULL;
    if (!force_timeout) gate.signaledValue = 1;
    if (!mtl_wait(fence, force_timeout ? 50000000ull : 5000000000ull)) gpu_test_timeout();
    if (force_timeout) { fputs("FAIL: unsignaled GPU gate completed\n", stderr); _Exit(2); }
    mtl_drain(); dispatch_sync(g_feedback_q, ^{}); defer_drain();
    CHECK(!mtl_last_commit_error(), "no GPU error after delayed retirement");
    CHECK(resident(live) && idle() == RH_CAP - CHUNK + live.size, "completed texture's heap replaces an older idle heap");
    CHECK(g_rh_rejected == rejected && g_rh_evicted == evicted + 2, "completed heap admitted with one eviction");
    const uint8_t *p = output.contents; int zero = 1;
    for (NSUInteger i = 0; i < output.length; i++) if (p[i]) { zero = 0; break; }
    CHECK(zero, "GPU readback preserved the retired texture's zero contents");
    res_remove(output); expire();
    CHECK(!idle() && !g_rh_n, "trim drains the full idle list");

    id<MTLHeap> large = heap(RH_CAP + CHUNK); rh_wait(large);
    CHECK(!idle() && !resident(large), "an oversized heap is rejected even from an empty list");
    // The review's size-change trace: one new size survives a full cache of
    // incompatible 4 MiB heaps, then all subsequent requests reuse it.
    for (unsigned i = 0; i < COUNT; i++) { res_add(heaps[i]); rh_wait(heaps[i]); }
    uint64_t made = g_rh_made;
    for (unsigned i = 0; i < 60; i++) { @autoreleasepool {
        int reused = 0;
        id<MTLHeap> h = rh_heap(5u << 20, MTLStorageModePrivate, MTLCPUCacheModeDefaultCache, MTLHazardTrackingModeDefault, &reused);
        CHECK(h && (i == 0 ? !reused : reused), "new size is allocated once then reused");
        res_add(h); rh_wait(h); CHECK(idle() <= RH_CAP, "changed-size returns respect capacity");
    } }
    CHECK(g_rh_made == made + 1, "sixty changed-size requests allocate one heap");
    expire();
    // Race distinct admissions against actual reuse and expiration/removal.
    // Each original heap is returned exactly once by its admission worker.
    dispatch_apply(3, dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^(size_t role) {
        for (unsigned i = 0; i < COUNT; i++) { @autoreleasepool {
            if (role == 0) { res_add(heaps[i]); rh_wait(heaps[i]); }
            else if (role == 1) {
                int reused = 0;
                id<MTLHeap> h = rh_heap(CHUNK, MTLStorageModePrivate, MTLCPUCacheModeDefaultCache, MTLHazardTrackingModeDefault, &reused);
                res_add(h); rh_wait(h);
            } else expire();
        } }
    });
    CHECK(idle() <= RH_CAP, "concurrent admission/reuse/trim respects capacity");
    expire(); CHECK(!idle(), "concurrent operations can be drained"); res_commit();
    printf("t_rt_recycle_budget: %d checks, %d failed\n", checks, failed); return failed != 0;
} }

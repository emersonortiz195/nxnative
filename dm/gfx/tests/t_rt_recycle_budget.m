// Exercise the actual recycle admission path, including a completion delayed
// behind a GPU event. No game data or shader archive is needed.
#include "../nvn/nvn_mtl.m"
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
    CHECK(h && h.size == size, "test heap has the requested aligned capacity");
    res_add(h); return h;
}
static void expire(void) {
    os_unfair_lock_lock(&g_rh_lk);
    for (unsigned i = 0; i < g_rh_n; i++) g_rh[i].t -= RH_IDLE_NS;
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
    uint64_t rejected = g_rh_rejected, bytes = g_rh_rejected_bytes;
    rh_wait(heaps[COUNT]);
    CHECK(idle() == RH_CAP && g_rh_n == COUNT, "one more heap cannot exceed the budget before a submission");
    CHECK(!resident(heaps[COUNT]) && resident(heaps[0]), "only the rejected heap leaves residency");
    CHECK(g_rh_rejected == rejected + 1 && g_rh_rejected_bytes == bytes + CHUNK, "rejection counters are cumulative capacity");
    int reused = 0;
    id<MTLHeap> taken = rh_heap(CHUNK, MTLStorageModePrivate, MTLCPUCacheModeDefaultCache, MTLHazardTrackingModeDefault, &reused);
    CHECK(reused && idle() == RH_CAP - CHUNK && resident(taken), "reuse removes capacity from the idle budget without removing residency");
    rh_wait(taken); taken = nil;
    CHECK(idle() == RH_CAP && g_rh_rejected == rejected + 1, "a taken heap can return to the exact budget");

    // Make a live texture while idle capacity is full. Its heap must stay
    // resident until the GPU copy finishes, then be rejected from the idle list.
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
    CHECK(idle() == RH_CAP && g_rh_rejected == rejected + 1, "in-flight texture has not entered recycle admission");
    gate.signaledValue = 1;
    CHECK(mtl_wait(fence, 5000000000ull), "delayed copy completes");
    mtl_drain(); dispatch_sync(g_feedback_q, ^{}); defer_drain();
    CHECK(!mtl_last_commit_error(), "no GPU error after delayed retirement");
    CHECK(!resident(live) && idle() == RH_CAP, "completed texture's heap is rejected without growing idle capacity");
    CHECK(g_rh_rejected == rejected + 2, "completed heap rejected once");
    const uint8_t *p = output.contents; int zero = 1;
    for (NSUInteger i = 0; i < output.length; i++) if (p[i]) { zero = 0; break; }
    CHECK(zero, "GPU readback preserved the retired texture's zero contents");
    res_remove(output); expire();
    CHECK(!idle() && !g_rh_n, "trim drains the full idle list");

    id<MTLHeap> large = heap(RH_CAP + CHUNK); rh_wait(large);
    CHECK(!idle() && !resident(large), "an oversized heap is rejected even from an empty list");
    // Concurrent completion handlers must share the admission budget.
    dispatch_apply(heaps.count, dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^(size_t i) {
        res_add(heaps[i]); rh_wait(heaps[i]);
    });
    CHECK(idle() == RH_CAP && g_rh_n == COUNT, "concurrent returns stay within the budget");
    expire(); CHECK(!idle(), "concurrent returns can be drained"); res_commit();
    printf("t_rt_recycle_budget: %d checks, %d failed\n", checks, failed); return failed != 0;
} }

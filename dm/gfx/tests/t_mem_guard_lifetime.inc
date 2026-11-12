#import <Foundation/Foundation.h>
#include <pthread.h>
#include <stdatomic.h>
#include <assert.h>
#include <time.h>
#include "nvn_mem_guard.h"
@protocol MTLAllocation
@property(readonly) NSUInteger allocatedSize;
@end
static pthread_mutex_t g_res_mu = PTHREAD_MUTEX_INITIALIZER;
// Return snapshots at +1, draining Foundation's temporary ownership before the
// caller receives them. Only res_commit's locals can keep these arrays alive.
// ARC's ownership qualifier applies to one declarator, not the whole list:
// declaring these together would leave pending_snapshot strong and retain the
// allocations being tested, masking its negative control's intended failure.
static __weak NSArray *committed_snapshot;
static __weak NSArray *pending_snapshot;
@interface SnapshotTable : NSObject {
    NSHashTable *objects;
}
@property BOOL isCommitted;
- (NSArray *)allObjects __attribute__((ns_returns_retained));
- (void)addObject:(id)object;
- (BOOL)containsObject:(id)object;
- (void)removeAllObjects;
- (NSUInteger)count;
+ (instancetype)weakObjectsHashTable;
@end
@implementation SnapshotTable
+ (instancetype)weakObjectsHashTable { return [self new]; }
- (instancetype)init {
    if ((self = [super init])) objects = [NSHashTable weakObjectsHashTable];
    return self;
}
- (NSArray *)allObjects { @autoreleasepool {
    NSArray *snapshot = [[NSArray alloc] initWithArray:objects.allObjects];
    if (self.isCommitted) committed_snapshot = snapshot;
    else pending_snapshot = snapshot;
    return snapshot;
} }
- (void)addObject:(id)object { [objects addObject:object]; }
- (BOOL)containsObject:(id)object { return [objects containsObject:object]; }
- (void)removeAllObjects { [objects removeAllObjects]; }
- (NSUInteger)count { return objects.count; }
@end
static SnapshotTable *g_res_objects, *g_mem_guard_committed;
static int g_mem_guard, g_res_dirty;
static uint64_t g_rs_commits, g_rs_commit_ns;
static _Atomic uint64_t g_mem_guard_resident;
static id owner;
static unsigned destroyed, checked, commit_calls;
static BOOL drop_on_read;
static void mem_guard_check(uint64_t value) { (void)value; checked++; }
@interface Residency : NSObject
- (void)commit;
@end
@implementation Residency
- (void)commit { commit_calls++; }
@end
static Residency *g_res;
@interface Allocation : NSObject <MTLAllocation>
@end
@implementation Allocation
- (NSUInteger)allocatedSize {
    if (drop_on_read) owner = nil; // simulate the last external owner releasing during the scan
    return 100;
}
- (void)dealloc {
    // A real heap-owner destructor calls res_remove. Fail rather than hang if
    // the diagnostic releases its last reference while holding the mutex.
    assert(pthread_mutex_trylock(&g_res_mu) == 0);
    g_res_dirty = 1; // reentrant removal must survive res_commit's dirty reset
    pthread_mutex_unlock(&g_res_mu);
    destroyed++;
}
@end
static BOOL require_snapshots = YES;
static int checked_unlock(pthread_mutex_t *mutex) {
    if (g_mem_guard && require_snapshots) {
        assert(committed_snapshot != nil);
        assert(pending_snapshot != nil);
    }
    int result = pthread_mutex_unlock(mutex);
    if (g_mem_guard && require_snapshots) {
        assert(committed_snapshot != nil);
        assert(pending_snapshot != nil);
    }
    return result;
}
// Intercept only the production body's unlock and lazy table creation.
#define pthread_mutex_unlock checked_unlock
#define NSHashTable SnapshotTable
/* COMMIT_BODY */
#undef NSHashTable
#undef pthread_mutex_unlock
static void checked_commit(int dirty) {
    unsigned before = commit_calls;
    res_commit();
    assert(commit_calls == before + dirty);
}
static void prepare(BOOL committed, BOOL pending) { @autoreleasepool {
    g_res_objects = [SnapshotTable weakObjectsHashTable];
    g_mem_guard_committed = [SnapshotTable weakObjectsHashTable];
    g_mem_guard_committed.isCommitted = YES;
    owner = [Allocation new];
    if (committed) [g_mem_guard_committed addObject:owner];
    if (pending) [g_res_objects addObject:owner];
} }
int main(void) { @autoreleasepool {
    g_res = [Residency new];
    g_mem_guard = 1;
    // Both scans, overlap, pending-only, committed-only, clean and dirty calls.
    for (int sets = 1; sets <= 3; sets++) for (int dirty = 0; dirty <= 1; dirty++) {
        prepare(sets & 1, sets & 2);
        unsigned before = destroyed;
        g_res_dirty = dirty;
        drop_on_read = YES;
        checked_commit(dirty);
        assert(owner == nil);
        assert(destroyed == before + 1); // before the surrounding guest-thread pool drains
        assert(g_res_dirty == 1);
        assert(g_mem_guard_resident == (dirty && !(sets & 2) ? 0 : 100));
    }
    // Snapshot insertion must leave no autoreleased ownership in the outer pool.
    drop_on_read = NO;
    prepare(NO, YES);
    g_mem_guard_committed = nil; // exercise lazy snapshot creation too
    require_snapshots = NO;
    unsigned before = destroyed;
    g_res_dirty = 1;
    checked_commit(1);
    owner = nil;
    assert(destroyed == before + 1);
    assert(g_mem_guard_committed.allObjects.count == 0);
    require_snapshots = YES;
    // Opt-out: dirty calls still commit once; clean calls never commit.
    for (int dirty = 0; dirty <= 1; dirty++) {
        prepare(NO, YES);
        before = checked;
        unsigned deaths = destroyed;
        g_mem_guard = 0;
        g_res_dirty = dirty;
        checked_commit(dirty);
        assert(checked == before);
        assert(g_mem_guard_committed.count == 0);
        assert(g_res_dirty == 0);
        owner = nil;
        assert(destroyed == deaths + 1);
    }
} return 0; }

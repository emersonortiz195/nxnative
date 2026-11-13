// Actual production metadata policy; no Objective-C, driver or GPU required.
#include "../nvn/nvn_heap_cache.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int checks, failed;
#define CHECK(c) do { checks++; if (!(c)) { failed++; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
enum { CAP = 256, MAX = 2048 };
static rh_ent entries[MAX]; static unsigned count; static uint64_t bytes, serial, tick;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t start = PTHREAD_COND_INITIALIZER; static unsigned ready, turn;
static unsigned admitted, taken, trimmed;
static void invariant(void) {
    uint64_t sum = 0;
    for (unsigned i = 0; i < count; i++) {
        sum += entries[i].size;
        for (unsigned j = 0; j < i; j++) CHECK(entries[i].heap != entries[j].heap);
    }
    CHECK(sum == bytes && bytes <= CAP && count <= MAX);
}
static int put(uint64_t size) {
    rh_ent drop[64] = {0}; unsigned nd;
    int ok = rh_cache_room(entries, &count, &bytes, size, CAP, drop, &nd, 64);
    CHECK(nd <= 64);
    if (ok) { entries[count++] = (rh_ent){(void *)(uintptr_t)++serial, size, ++tick}; bytes += size; admitted++; }
    for (unsigned j = 0; j < nd; j++) for (unsigned i = 0; i < count; i++) CHECK(drop[j].heap != entries[i].heap);
    invariant(); return ok;
}
static int take(uint64_t size) {
    unsigned best = count;
    for (unsigned i = 0; i < count; i++)
        if (entries[i].size >= size && entries[i].size <= size + size / 2 && (best == count || entries[i].size < entries[best].size)) best = i;
    if (best == count) return 0;
    rh_ent e = rh_cache_remove(entries, &count, &bytes, best); taken++;
    invariant();
    // Return the same object, as a completed reuse would do.
    rh_ent drop[64] = {0}; unsigned nd;
    CHECK(rh_cache_room(entries, &count, &bytes, e.size, CAP, drop, &nd, 64));
    e.t = ++tick; entries[count++] = e; bytes += e.size;
    invariant(); return 1;
}
static void *worker(void *arg) {
    uintptr_t role = (uintptr_t)arg;
    pthread_mutex_lock(&lock);
    ready++; pthread_cond_broadcast(&start);
    while (ready < 4) pthread_cond_wait(&start, &lock);
    // Reproducible first interleaving, before the unconstrained stress phase.
    while (turn != role) pthread_cond_wait(&start, &lock);
    if (role == 0 || role == 3) put(8);
    else if (role == 1) CHECK(take(8));
    else { rh_cache_remove(entries, &count, &bytes, rh_cache_oldest(entries, count)); trimmed++; }
    invariant(); turn++; pthread_cond_broadcast(&start);
    while (turn < 4) pthread_cond_wait(&start, &lock);
    pthread_mutex_unlock(&lock);
    for (unsigned i = 0; i < 200; i++) {
        pthread_mutex_lock(&lock);
        if (role == 0 || role == 3) put(4 + i % 17);
        else if (role == 1) take(4 + i % 17);
        else if (count) { rh_cache_remove(entries, &count, &bytes, rh_cache_oldest(entries, count)); trimmed++; }
        invariant(); pthread_mutex_unlock(&lock);
    }
    return NULL;
}
int main(void) {
    for (unsigned i = 0; i < 64; i++) CHECK(put(4));
    CHECK(bytes == CAP);
    unsigned allocated = 0;
    for (unsigned i = 0; i < 60; i++) if (!take(5)) { allocated++; CHECK(put(6)); }
    CHECK(allocated == 1 && taken == 59 && bytes <= CAP);
    CHECK(take(4) && take(5));   // both retained sizes still reuse

    // Planning is transactional when the fixed work budget cannot make room.
    count = 0; bytes = 0;
    for (unsigned i = 0; i < 128; i++) CHECK(put(2));
    rh_ent saved[MAX]; memcpy(saved, entries, count * sizeof *entries);
    CHECK(!put(200) && count == 128 && bytes == CAP);
    CHECK(memcmp(saved, entries, count * sizeof *entries) == 0);
    CHECK(!put(CAP + 1) && bytes == CAP);
    // Exact work budget, timestamp ties, and non-sorted storage.
    count = 3; bytes = 240;
    entries[0] = (rh_ent){(void *)1, 80, 30};
    entries[1] = (rh_ent){(void *)2, 80, 10};
    entries[2] = (rh_ent){(void *)3, 80, 20};
    rh_ent drop[64] = {0}; unsigned nd;
    CHECK(rh_cache_room(entries, &count, &bytes, 100, CAP, drop, &nd, 2));
    CHECK(nd == 2 && count == 1 && bytes == 80 && entries[0].heap == (void *)1);
    CHECK((drop[0].heap == (void *)2 || drop[1].heap == (void *)2) && (drop[0].heap == (void *)3 || drop[1].heap == (void *)3));
    count = 0; bytes = 0;
    for (unsigned i = 0; i < 128; i++) CHECK(put(2));
    CHECK(rh_cache_room(entries, &count, &bytes, 128, CAP, drop, &nd, 64) && nd == 64 && bytes == 128);
    for (unsigned i = 0; i < count; i++) entries[i].t = 1;
    CHECK(rh_cache_room(entries, &count, &bytes, 200, CAP, drop, &nd, 64) && nd == 36 && bytes == 56);

    count = 0; bytes = 0; admitted = taken = trimmed = 0;
    for (unsigned i = 0; i < 20; i++) CHECK(put(8));
    pthread_t threads[4];
    for (uintptr_t i = 0; i < 4; i++) if (pthread_create(&threads[i], NULL, worker, (void *)i)) abort();
    for (unsigned i = 0; i < 4; i++) pthread_join(threads[i], NULL);
    invariant(); CHECK(admitted >= 400 && taken >= 1 && trimmed >= 1);
    printf("t_heap_cache: %d checks, %d failed; concurrent take %u, trim %u\n", checks, failed, taken, trimmed);
    return failed != 0;
}

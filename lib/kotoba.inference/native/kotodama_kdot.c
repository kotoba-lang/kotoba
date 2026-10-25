#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

#define QK_K 256

#if defined(_WIN32)
#define KOTODAMA_API __declspec(dllexport)
#else
#define KOTODAMA_API __attribute__((visibility("default")))
#endif

typedef struct {
    float d;
    int8_t qs[QK_K];
    int16_t bsums[QK_K/16];
} block_q8_K;

static inline float fp16_to_float(uint16_t h) {
    const uint32_t sign = (uint32_t)(h & 0x8000u) << 16;
    uint32_t exp = (h >> 10) & 0x1fu;
    uint32_t mant = h & 0x03ffu;
    uint32_t bits;
    if (exp == 0) {
        if (mant == 0) bits = sign;
        else {
            exp = 1;
            while ((mant & 0x0400u) == 0) { mant <<= 1; --exp; }
            mant &= 0x03ffu;
            bits = sign | ((exp + 112u) << 23) | (mant << 13);
        }
    } else if (exp == 31) {
        bits = sign | 0x7f800000u | (mant << 13);
    } else {
        bits = sign | ((exp + 112u) << 23) | (mant << 13);
    }
    float f;
    memcpy(&f, &bits, sizeof(f));
    return f;
}

static inline uint16_t le16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static inline int nearest_int(float fval) {
    float val = fval + 12582912.f;
    int i;
    memcpy(&i, &val, sizeof(i));
    return (i & 0x007fffff) - 0x00400000;
}

static void quantize_q8_K(const float *x, block_q8_K *y, int64_t k) {
    const int64_t nb = k/QK_K;
    for (int64_t i = 0; i < nb; ++i) {
        float max = 0, amax = 0;
        for (int j = 0; j < QK_K; ++j) {
            const float ax = fabsf(x[j]);
            if (ax > amax) { amax = ax; max = x[j]; }
        }
        if (!amax) {
            y[i].d = 0;
            memset(y[i].qs, 0, QK_K);
            memset(y[i].bsums, 0, sizeof(y[i].bsums));
            x += QK_K;
            continue;
        }
        const float iscale = -127.f/max;
        for (int j = 0; j < QK_K; ++j) {
            const int v = nearest_int(iscale*x[j]);
            y[i].qs[j] = (int8_t)(v < 127 ? v : 127);
        }
        for (int j = 0; j < QK_K/16; ++j) {
            int sum = 0;
            for (int l = 0; l < 16; ++l) sum += y[i].qs[j*16+l];
            y[i].bsums[j] = (int16_t)sum;
        }
        y[i].d = 1.f/iscale;
        x += QK_K;
    }
}

static inline int q4_scale(const uint8_t *s, int j) {
    return j < 4 ? s[j] & 63 : (s[j+4] & 15) | ((s[j-4] >> 6) << 4);
}

static inline int q4_min(const uint8_t *s, int j) {
    return j < 4 ? s[j+4] & 63 : (s[j+4] >> 4) | ((s[j] >> 6) << 4);
}

static float dot_q4_q8(const uint8_t *x, const block_q8_K *y, int64_t n) {
    const int nb = (int)(n/QK_K);
    float sums[8] = {0};
    float sumf = 0;
    for (int ib = 0; ib < nb; ++ib, x += 144, ++y) {
        const uint8_t *sc = x+4, *q4 = x+16;
        int8_t aux8[QK_K];
        int32_t aux32[8] = {0};
        int8_t *a = aux8;
        for (int j = 0; j < 4; ++j) {
            for (int l = 0; l < 32; ++l) a[l] = q4[l] & 15;
            a += 32;
            for (int l = 0; l < 32; ++l) a[l] = q4[l] >> 4;
            a += 32; q4 += 32;
        }
        int sumi = 0;
        for (int j = 0; j < 16; ++j) sumi += y->bsums[j]*q4_min(sc, j/2);
        const int8_t *q8 = y->qs;
        a = aux8;
        for (int j = 0; j < 8; ++j) {
            const int scale = q4_scale(sc, j);
            for (int chunk = 0; chunk < 4; ++chunk) {
                for (int l = 0; l < 8; ++l) aux32[l] += scale*q8[l]*a[l];
                q8 += 8; a += 8;
            }
        }
        const float d = fp16_to_float(le16(x))*y->d;
        for (int l = 0; l < 8; ++l) sums[l] += d*aux32[l];
        sumf -= fp16_to_float(le16(x+2))*y->d*sumi;
    }
    for (int l = 0; l < 8; ++l) sumf += sums[l];
    return sumf;
}

static float dot_q6_q8(const uint8_t *x, const block_q8_K *y, int64_t n) {
    const int nb = (int)(n/QK_K);
    float sums[8] = {0};
    for (int ib = 0; ib < nb; ++ib, x += 210, ++y) {
        int8_t aux8[QK_K];
        int32_t aux32[8] = {0};
        int8_t *a = aux8;
        const uint8_t *ql = x, *qh = x+128;
        for (int j = 0; j < QK_K; j += 128) {
            for (int l = 0; l < 32; ++l) {
                a[l+0]  = (int8_t)((ql[l]&15) | (((qh[l]>>0)&3)<<4))-32;
                a[l+32] = (int8_t)((ql[l+32]&15) | (((qh[l]>>2)&3)<<4))-32;
                a[l+64] = (int8_t)((ql[l]>>4) | (((qh[l]>>4)&3)<<4))-32;
                a[l+96] = (int8_t)((ql[l+32]>>4) | (((qh[l]>>6)&3)<<4))-32;
            }
            a += 128; ql += 64; qh += 32;
        }
        const int8_t *q8 = y->qs;
        a = aux8;
        for (int j = 0; j < 16; ++j) {
            const int scale = (int8_t)x[192+j];
            for (int chunk = 0; chunk < 2; ++chunk) {
                for (int l = 0; l < 8; ++l) aux32[l] += scale*q8[l]*a[l];
                q8 += 8; a += 8;
            }
        }
        const float d = fp16_to_float(le16(x+208))*y->d;
        for (int l = 0; l < 8; ++l) sums[l] += d*aux32[l];
    }
    float sumf = 0;
    for (int l = 0; l < 8; ++l) sumf += sums[l];
    return sumf;
}

typedef struct {
    int tensor_type;
    const uint8_t *weights;
    const block_q8_K *q8;
    float *outputs;
    int64_t rows, cols, positions, row_begin, row_end;
} matvec_task;

static void *matvec_rows(void *opaque) {
    const matvec_task *t = (const matvec_task *)opaque;
    const int64_t blocks = t->cols/QK_K;
    const int64_t row_bytes = blocks*(t->tensor_type == 12 ? 144 : 210);
    for (int64_t r = t->row_begin; r < t->row_end; ++r) {
        const uint8_t *row = t->weights+r*row_bytes;
        for (int64_t p = 0; p < t->positions; ++p) {
            t->outputs[p*t->rows+r] = t->tensor_type == 12
                ? dot_q4_q8(row, t->q8+p*blocks, t->cols)
                : dot_q6_q8(row, t->q8+p*blocks, t->cols);
        }
    }
    return NULL;
}

static int requested_threads(int64_t rows) {
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    const char *env = getenv("KOTODAMA_KDOT_THREADS");
    if (env && *env) {
        const long requested = strtol(env, NULL, 10);
        if (requested > 0) n = requested;
    }
    if (n < 1) n = 1;
    if (n > 16) n = 16;
    if (n > rows) n = (long)rows;
    return (int)n;
}

KOTODAMA_API int kotodama_kdot_matvec(
        int tensor_type, const uint8_t *weights, int64_t rows, int64_t cols,
        const float *inputs, int64_t positions, float *outputs) {
    if (!weights || !inputs || !outputs || rows < 0 || positions < 0 || cols <= 0 || cols%QK_K) return -1;
    if (tensor_type != 12 && tensor_type != 14) return -2;
    const int64_t blocks = cols/QK_K;
    block_q8_K *q8 = (block_q8_K *)malloc((size_t)(positions*blocks)*sizeof(block_q8_K));
    if (!q8) return -3;
    for (int64_t p = 0; p < positions; ++p) quantize_q8_K(inputs+p*cols, q8+p*blocks, cols);
    const int nthreads = requested_threads(rows);
    pthread_t *threads = nthreads > 1 ? (pthread_t *)malloc((size_t)(nthreads-1)*sizeof(pthread_t)) : NULL;
    matvec_task *tasks = (matvec_task *)calloc((size_t)nthreads, sizeof(matvec_task));
    if (!tasks || (nthreads > 1 && !threads)) { free(threads); free(tasks); free(q8); return -4; }
    for (int i = 0; i < nthreads; ++i) {
        tasks[i] = (matvec_task){tensor_type, weights, q8, outputs, rows, cols, positions,
                                 rows*i/nthreads, rows*(i+1)/nthreads};
    }
    for (int i = 1; i < nthreads; ++i) {
        if (pthread_create(&threads[i-1], NULL, matvec_rows, &tasks[i]) != 0) {
            for (int j = 1; j < i; ++j) pthread_join(threads[j-1], NULL);
            free(threads); free(tasks); free(q8); return -5;
        }
    }
    matvec_rows(&tasks[0]);
    for (int i = 1; i < nthreads; ++i) pthread_join(threads[i-1], NULL);
    free(threads);
    free(tasks);
    free(q8);
    return 0;
}

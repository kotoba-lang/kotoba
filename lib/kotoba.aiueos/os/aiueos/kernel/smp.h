/* SPDX-License-Identifier: Apache-2.0 */
#ifndef AIUEOS_SMP_H
#define AIUEOS_SMP_H

#include <stdint.h>

typedef void (*aiueos_smp_work_fn)(void *context);

int aiueos_smp_start_application_processor(void);
uint32_t aiueos_smp_worker_threads(void);
int aiueos_smp_dispatch(aiueos_smp_work_fn work, void *context);
int aiueos_smp_join(void);
int aiueos_smp_dispatch_selftest(void);

#endif

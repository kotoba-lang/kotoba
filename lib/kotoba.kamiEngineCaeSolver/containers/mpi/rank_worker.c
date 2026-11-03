/*
 * Clean-room MPI runtime verification worker for Kotoba CAE.
 * It performs a distributed midpoint integration of 4/(1+x^2) over [0,1],
 * uses MPI_Allreduce for the global result, and gathers rank-local audit data.
 */
#include <errno.h>
#include <math.h>
#include <mpi.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
  long long samples;
  double partial_sum;
} rank_record;

static long long sample_count(const char *text, int rank) {
  char *end = NULL;
  errno = 0;
  const long long value = strtoll(text, &end, 10);
  if (errno != 0 || end == text || *end != '\0' || value < 1) {
    if (rank == 0) fprintf(stderr, "invalid sample count: %s\n", text);
    MPI_Abort(MPI_COMM_WORLD, 2);
  }
  return value;
}

int main(int argc, char **argv) {
  int rank = 0, size = 0;
  MPI_Init(&argc, &argv);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &size);
  if (argc != 2) {
    if (rank == 0) fprintf(stderr, "usage: kotoba-mpi-worker SAMPLE_COUNT\n");
    MPI_Abort(MPI_COMM_WORLD, 2);
  }

  const long long n = sample_count(argv[1], rank);
  long long local_samples = 0;
  double local_sum = 0.0;
  for (long long i = rank; i < n; i += size) {
    const double x = ((double)i + 0.5) / (double)n;
    local_sum += 4.0 / (1.0 + x * x);
    local_samples++;
  }

  double global_sum = 0.0;
  long long global_samples = 0;
  MPI_Allreduce(&local_sum, &global_sum, 1, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD);
  MPI_Allreduce(&local_samples, &global_samples, 1, MPI_LONG_LONG, MPI_SUM, MPI_COMM_WORLD);

  rank_record local = {local_samples, local_sum};
  rank_record *records = rank == 0 ? calloc((size_t)size, sizeof(rank_record)) : NULL;
  MPI_Datatype record_type;
  const int lengths[2] = {1, 1};
  const MPI_Aint offsets[2] = {offsetof(rank_record, samples), offsetof(rank_record, partial_sum)};
  const MPI_Datatype types[2] = {MPI_LONG_LONG, MPI_DOUBLE};
  MPI_Type_create_struct(2, lengths, offsets, types, &record_type);
  MPI_Type_commit(&record_type);
  MPI_Gather(&local, 1, record_type, records, 1, record_type, 0, MPI_COMM_WORLD);

  if (rank == 0) {
    for (int r = 0; r < size; r++)
      printf("KOTOBA_MPI_RANK rank=%d size=%d samples=%lld partial=%.17g\n",
             r, size, records[r].samples, records[r].partial_sum);
    const double pi = global_sum / (double)n;
    printf("KOTOBA_MPI_RESULT size=%d samples=%lld pi=%.17g error=%.17g\n",
           size, global_samples, pi, fabs(pi - acos(-1.0)));
    free(records);
  }

  MPI_Type_free(&record_type);
  MPI_Finalize();
  return global_samples == n ? 0 : 3;
}

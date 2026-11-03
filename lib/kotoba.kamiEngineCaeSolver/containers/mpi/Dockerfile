FROM ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG DEBIAN_FRONTEND=noninteractive
ARG OPENMPI_VERSION=4.1.6-7ubuntu2
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      openmpi-bin=${OPENMPI_VERSION} libopenmpi-dev=${OPENMPI_VERSION} gcc=4:13.2.0-7ubuntu1 \
 && rm -rf /var/lib/apt/lists/*

COPY rank_worker.c /src/rank_worker.c
RUN mpicc -O2 -std=c11 -Wall -Wextra -Werror /src/rank_worker.c -lm -o /usr/local/bin/kotoba-mpi-worker \
 && mpirun --version | grep 'Open MPI' \
 && test "$(mpirun --allow-run-as-root -np 2 /usr/local/bin/kotoba-mpi-worker 1000 | grep -c '^KOTOBA_MPI_RANK')" -eq 2

WORKDIR /work
ENTRYPOINT ["mpirun", "--allow-run-as-root", "--oversubscribe"]

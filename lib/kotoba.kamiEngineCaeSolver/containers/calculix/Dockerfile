FROM ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends calculix-ccx=2.21-1 ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && (ccx -v || [ "$?" -eq 201 ])

WORKDIR /work
ENTRYPOINT ["ccx"]

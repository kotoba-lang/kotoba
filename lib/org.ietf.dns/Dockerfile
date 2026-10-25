# Runs from source via the Clojure CLI (no uberjar step) -- same pattern
# as this org's other deployed Clojure services (e.g. ai-gftd-syosetsuka).
FROM clojure:temurin-21-tools-deps-bookworm
WORKDIR /app
COPY deps.edn /app/
COPY src /app/src
COPY examples/zones /app/zones
COPY deploy/docker-config.edn /app/config.edn
EXPOSE 53/udp 53/tcp
CMD ["kbb", "-M", "-m", "nameserver.main"]

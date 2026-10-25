#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif

#ifndef KOTOBA_POLICY_OFFSET
#error KOTOBA_POLICY_OFFSET must be supplied by the build
#endif
#ifndef KOTOBA_POLICY_ISA
#define KOTOBA_POLICY_ISA "x86_64"
#endif

#define RESPONSE_LIMIT (4u * 1024u * 1024u)

struct buffer { char *data; size_t length; size_t capacity; };

static void die(const char *message) {
  fprintf(stderr, "kotoba-vllm-infer: %s\n", message);
  exit(2);
}

static void *checked_realloc(void *p, size_t size) {
  void *next = realloc(p, size);
  if (next == NULL) die("out of memory");
  return next;
}

static void append(struct buffer *b, const char *bytes, size_t count) {
  if (count > RESPONSE_LIMIT || b->length > RESPONSE_LIMIT - count)
    die("response exceeds 4 MiB limit");
  if (b->length + count + 1 > b->capacity) {
    size_t capacity = b->capacity == 0 ? 4096 : b->capacity;
    while (capacity < b->length + count + 1) capacity *= 2;
    b->data = checked_realloc(b->data, capacity);
    b->capacity = capacity;
  }
  memcpy(b->data + b->length, bytes, count);
  b->length += count;
  b->data[b->length] = '\0';
}

static double monotonic_ms(void) {
  struct timespec now;
  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) die("clock_gettime failed");
  return (double)now.tv_sec * 1000.0 + (double)now.tv_nsec / 1000000.0;
}

static int executable_dir(char *out, size_t size) {
#if defined(__linux__)
  ssize_t n = readlink("/proc/self/exe", out, size - 1);
  if (n <= 0 || (size_t)n >= size - 1) return -1;
  out[n] = '\0';
#elif defined(__APPLE__)
  uint32_t n = (uint32_t)size;
  if (_NSGetExecutablePath(out, &n) != 0) return -1;
#else
  return -1;
#endif
  char *slash = strrchr(out, '/');
  if (slash == NULL) return -1;
  *slash = '\0';
  return 0;
}

static int read_child(char *const argv[], const char *input, struct buffer *output) {
  int in_pipe[2], out_pipe[2];
  if (pipe(in_pipe) != 0 || pipe(out_pipe) != 0) die("pipe failed");
  pid_t child = fork();
  if (child < 0) die("fork failed");
  if (child == 0) {
    if (dup2(in_pipe[0], STDIN_FILENO) < 0 ||
        dup2(out_pipe[1], STDOUT_FILENO) < 0) _exit(126);
    close(in_pipe[0]); close(in_pipe[1]); close(out_pipe[0]); close(out_pipe[1]);
    execvp(argv[0], argv);
    _exit(127);
  }
  close(in_pipe[0]); close(out_pipe[1]);
  if (input != NULL) {
    size_t left = strlen(input); const char *p = input;
    while (left > 0) {
      ssize_t n = write(in_pipe[1], p, left);
      if (n < 0 && errno == EINTR) continue;
      if (n <= 0) break;
      p += n; left -= (size_t)n;
    }
  }
  close(in_pipe[1]);
  char chunk[4096];
  for (;;) {
    ssize_t n = read(out_pipe[0], chunk, sizeof(chunk));
    if (n < 0 && errno == EINTR) continue;
    if (n < 0) die("read from child failed");
    if (n == 0) break;
    append(output, chunk, (size_t)n);
  }
  close(out_pipe[0]);
  int status;
  while (waitpid(child, &status, 0) < 0)
    if (errno != EINTR) die("waitpid failed");
  return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
}

static int64_t parse_policy_result(const char *text) {
  const char *marker = strstr(text, ":result ");
  if (marker == NULL) die("Kotoba policy returned no result");
  char *end = NULL;
  long long value = strtoll(marker + 8, &end, 10);
  if (end == marker + 8) die("Kotoba policy result is malformed");
  return (int64_t)value;
}

static void join_path(char *out, size_t size, const char *dir, const char *name) {
  size_t dir_length = strlen(dir), name_length = strlen(name);
  if (dir_length + 1 + name_length + 1 > size) die("sidecar path is too long");
  memcpy(out, dir, dir_length);
  out[dir_length] = '/';
  memcpy(out + dir_length + 1, name, name_length + 1);
}

static int64_t bounded_max_tokens(const char *dir, int64_t requested) {
  char loader[PATH_MAX], policy[PATH_MAX], offset[32], value[32];
  join_path(loader, sizeof(loader), dir, "kotoba-loader");
  join_path(policy, sizeof(policy), dir, "vllm-infer-core.bin");
  snprintf(offset, sizeof(offset), "%d", KOTOBA_POLICY_OFFSET);
  snprintf(value, sizeof(value), "%" PRId64, requested);
  char *const argv[] = {loader, policy, offset, "1", KOTOBA_POLICY_ISA,
                        "-", value, NULL};
  struct buffer output = {0};
  if (setenv("KEXE_STRUCTURED_REPORT", "1", 1) != 0) die("setenv failed");
  int status = read_child(argv, NULL, &output);
  if (status != 0) die("Kotoba policy execution failed");
  int64_t result = parse_policy_result(output.data == NULL ? "" : output.data);
  free(output.data);
  return result;
}

static char *json_escape(const char *source) {
  struct buffer out = {0};
  append(&out, "\"", 1);
  for (const unsigned char *p = (const unsigned char *)source; *p; p++) {
    char escaped[7];
    switch (*p) {
      case '"': append(&out, "\\\"", 2); break;
      case '\\': append(&out, "\\\\", 2); break;
      case '\b': append(&out, "\\b", 2); break;
      case '\f': append(&out, "\\f", 2); break;
      case '\n': append(&out, "\\n", 2); break;
      case '\r': append(&out, "\\r", 2); break;
      case '\t': append(&out, "\\t", 2); break;
      default:
        if (*p < 0x20) {
          snprintf(escaped, sizeof(escaped), "\\u%04x", *p);
          append(&out, escaped, 6);
        } else append(&out, (const char *)p, 1);
    }
  }
  append(&out, "\"", 1);
  return out.data;
}

static long json_integer(const char *body, const char *field) {
  char marker[96];
  snprintf(marker, sizeof(marker), "\"%s\":", field);
  const char *p = strstr(body, marker);
  if (p == NULL) return 0;
  return strtol(p + strlen(marker), NULL, 10);
}

static int loopback_endpoint(const char *endpoint) {
  const char *p = NULL;
  if (strncmp(endpoint, "http://127.0.0.1:", 17) == 0) p = endpoint + 17;
  else if (strncmp(endpoint, "http://[::1]:", 13) == 0) p = endpoint + 13;
  else return 0;
  if (*p < '0' || *p > '9') return 0;
  unsigned long port = 0;
  while (*p >= '0' && *p <= '9') {
    port = port * 10 + (unsigned long)(*p - '0');
    if (port > 65535) return 0;
    p++;
  }
  return port > 0 && *p == '/';
}

int main(int argc, char **argv) {
  const char *endpoint = "http://127.0.0.1:8090/v1/chat/completions";
  const char *model = "qwen3.8-27b";
  const char *prompt = NULL;
  int64_t requested_max = 64;
  double temperature = 0.0;
  for (int i = 1; i < argc; i += 2) {
    if (i + 1 >= argc) die("every option requires a value");
    if (strcmp(argv[i], "--endpoint") == 0) endpoint = argv[i + 1];
    else if (strcmp(argv[i], "--model") == 0) model = argv[i + 1];
    else if (strcmp(argv[i], "--prompt") == 0) prompt = argv[i + 1];
    else if (strcmp(argv[i], "--max-tokens") == 0)
      requested_max = strtoll(argv[i + 1], NULL, 10);
    else if (strcmp(argv[i], "--temperature") == 0)
      temperature = strtod(argv[i + 1], NULL);
    else die("unknown option");
  }
  if (prompt == NULL || *prompt == '\0') die("--prompt is required");
  if (!loopback_endpoint(endpoint)) die("endpoint must be loopback http");
  char dir[PATH_MAX];
  if (executable_dir(dir, sizeof(dir)) != 0) die("cannot locate executable directory");
  int64_t max_tokens = bounded_max_tokens(dir, requested_max);
  char *escaped_model = json_escape(model), *escaped_prompt = json_escape(prompt);
  size_t request_size = strlen(escaped_model) + strlen(escaped_prompt) + 256;
  char *request = checked_realloc(NULL, request_size);
  snprintf(request, request_size,
           "{\"model\":%s,\"messages\":[{\"role\":\"user\",\"content\":%s}],"
           "\"max_tokens\":%" PRId64 ",\"temperature\":%.3f,\"stream\":false}",
           escaped_model, escaped_prompt, max_tokens, temperature);
  free(escaped_model); free(escaped_prompt);

  char *const curl_argv[] = {"/usr/bin/curl", "--silent", "--show-error", "--fail-with-body",
                             "--max-time", "300", "--header", "content-type: application/json",
                             "--data-binary", "@-", "--write-out", "\n%{http_code}",
                             (char *)endpoint, NULL};
  struct buffer response = {0};
  double started = monotonic_ms();
  int curl_status = read_child(curl_argv, request, &response);
  double request_ms = monotonic_ms() - started;
  free(request);
  if (response.data == NULL) die("empty response from vLLM");
  char *last_newline = strrchr(response.data, '\n');
  if (last_newline == NULL) die("curl response has no HTTP status");
  long http_status = strtol(last_newline + 1, NULL, 10);
  *last_newline = '\0';
  long tokens = json_integer(response.data, "completion_tokens");
  puts(response.data);
  fprintf(stderr,
          "{\"client\":\"native\",\"http_status\":%ld,\"request_ms\":%.3f,"
          "\"completion_tokens\":%ld,\"tokens_per_second\":%.3f}\n",
          http_status, request_ms, tokens,
          request_ms > 0.0 ? 1000.0 * (double)tokens / request_ms : 0.0);
  free(response.data);
  return curl_status == 0 && http_status >= 200 && http_status < 300 ? 0 : 1;
}

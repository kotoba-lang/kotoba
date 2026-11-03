/* kernel/pci.c's ssh_take_string, ssh_text_equal, ssh_userauth_method_is, ssh_userauth_publickey_fields and
   ssh_authorized_publickey_blob before JUN-552 moved them to kotoba/ssh-userauth.o, verbatim, over the built-in authorized key
   (the parsers renamed old_ and made external). */
#include <stdint.h>
static const uint8_t ssh_auth_x[32] = {
  0x46,0x87,0x0e,0x7c,0xe7,0x9b,0xcb,0xc6,0x01,0x47,0x14,0x61,0x8f,0x35,0x43,0xdc,
  0x1e,0x6d,0x67,0xcb,0xc5,0xda,0x37,0x8d,0x91,0xc8,0xd7,0x17,0x11,0xaf,0x1a,0xbf};
static const uint8_t ssh_auth_y[32] = {
  0x04,0xae,0xd0,0x99,0x59,0x46,0xfb,0x24,0x4e,0x15,0x10,0x9e,0xe2,0x76,0xc5,0x79,
  0xfa,0x0b,0x14,0x40,0x5b,0xf9,0x50,0x75,0x22,0xee,0xe2,0x65,0x68,0xd2,0xc0,0xf3};
static uint32_t ssh_be32p(const uint8_t *p) {
  return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
static int ssh_take_string(const uint8_t *bytes, uint32_t bytes_length,
                           uint32_t *offset, const uint8_t **value,
                           uint32_t *value_length) {
  if (!bytes || !offset || !value || !value_length ||
      *offset > bytes_length || bytes_length - *offset < 4) return 0;
  uint32_t length = ssh_be32p(bytes + *offset);
  *offset += 4;
  if (length > bytes_length - *offset) return 0;
  *value = bytes + *offset;
  *value_length = length;
  *offset += length;
  return 1;
}
static int ssh_text_equal(const uint8_t *value, uint32_t value_length,
                          const char *expected) {
  uint32_t expected_length = 0;
  if (!value || !expected) return 0;
  while (expected[expected_length]) expected_length++;
  if (value_length != expected_length) return 0;
  for (uint32_t i = 0; i < value_length; i++)
    if (value[i] != (uint8_t)expected[i]) return 0;
  return 1;
}
int old_method_is(const uint8_t *payload,
                                  uint32_t payload_length,
                                  const char *expected) {
  uint32_t offset = 1;
  const uint8_t *username, *service, *method;
  uint32_t username_length, service_length, method_length;
  return payload && payload_length > 1U && payload[0] == 50U &&
    ssh_take_string(payload, payload_length, &offset,
                    &username, &username_length) &&
    ssh_take_string(payload, payload_length, &offset,
                    &service, &service_length) &&
    ssh_take_string(payload, payload_length, &offset,
                    &method, &method_length) &&
    ssh_text_equal(username, username_length, "runtime") &&
    ssh_text_equal(service, service_length, "ssh-connection") &&
    ssh_text_equal(method, method_length, expected);
}

int old_publickey_fields(
    const uint8_t *payload, uint32_t payload_length,
    int *has_signature, const uint8_t **algorithm,
    uint32_t *algorithm_length, const uint8_t **public_key_blob,
    uint32_t *public_key_blob_length, uint32_t *after_key) {
  uint32_t offset = 1;
  const uint8_t *username, *service, *method;
  uint32_t username_length, service_length, method_length;
  if (!has_signature || !algorithm || !algorithm_length ||
      !public_key_blob || !public_key_blob_length || !after_key ||
      !payload || payload_length <= 1U || payload[0] != 50U ||
      !ssh_take_string(payload, payload_length, &offset,
                       &username, &username_length) ||
      !ssh_take_string(payload, payload_length, &offset,
                       &service, &service_length) ||
      !ssh_take_string(payload, payload_length, &offset,
                       &method, &method_length) ||
      !ssh_text_equal(username, username_length, "runtime") ||
      !ssh_text_equal(service, service_length, "ssh-connection") ||
      !ssh_text_equal(method, method_length, "publickey") ||
      offset >= payload_length) return 0;
  *has_signature = payload[offset++] != 0;
  if (!ssh_take_string(payload, payload_length, &offset,
                       algorithm, algorithm_length) ||
      !ssh_text_equal(*algorithm, *algorithm_length,
                      "ecdsa-sha2-nistp256") ||
      !ssh_take_string(payload, payload_length, &offset,
                       public_key_blob, public_key_blob_length)) return 0;
  *after_key = offset;
  return 1;
}

int old_authorized_blob(const uint8_t *blob,
                                         uint32_t blob_length,
                                         uint8_t public_point[64]) {
  uint32_t offset = 0;
  const uint8_t *algorithm, *curve, *point;
  uint32_t algorithm_length, curve_length, point_length;
  if (!blob || !public_point ||
      !ssh_take_string(blob, blob_length, &offset,
                       &algorithm, &algorithm_length) ||
      !ssh_take_string(blob, blob_length, &offset,
                       &curve, &curve_length) ||
      !ssh_take_string(blob, blob_length, &offset,
                       &point, &point_length) ||
      offset != blob_length || point_length != 65U || point[0] != 4U ||
      !ssh_text_equal(algorithm, algorithm_length,
                      "ecdsa-sha2-nistp256") ||
      !ssh_text_equal(curve, curve_length, "nistp256")) return 0;
  for (uint32_t i = 0; i < 32U; i++) {
    public_point[i] = point[1U + i];
    public_point[32U + i] = point[33U + i];
    if (public_point[i] != ssh_auth_x[i] ||
        public_point[32U + i] != ssh_auth_y[i]) return 0;
  }
  return 1;
}


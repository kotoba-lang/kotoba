#define _DARWIN_C_SOURCE
#include <libusb-1.0/libusb.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define AIUEOS_DBC_VENDOR_ID 0xffff
#define AIUEOS_DBC_PRODUCT_ID 0xa11e
#define AIUEOS_DBC_IN_ENDPOINT 0x81
#define AIUEOS_DBC_OUT_ENDPOINT 0x01

static volatile sig_atomic_t running = 1;

static void stop_running(int signal_number) {
  (void)signal_number;
  running = 0;
}

static int selftest(void) {
  if (AIUEOS_DBC_IN_ENDPOINT != (uint8_t)(AIUEOS_DBC_OUT_ENDPOINT | 0x80))
    return 1;
  puts("AIUEOS_DBC_RECEIVER_SELFTEST_OK vid=ffff pid=a11e endpoints=01,81");
  return 0;
}

static libusb_device_handle *open_target(libusb_context *context) {
  libusb_device **devices = NULL;
  ssize_t count = libusb_get_device_list(context, &devices);
  if (count < 0) return NULL;
  libusb_device_handle *handle = NULL;
  for (ssize_t index = 0; index < count; index++) {
    struct libusb_device_descriptor descriptor;
    if (libusb_get_device_descriptor(devices[index], &descriptor) != 0 ||
        descriptor.idVendor != AIUEOS_DBC_VENDOR_ID ||
        descriptor.idProduct != AIUEOS_DBC_PRODUCT_ID) continue;
    if (libusb_open(devices[index], &handle) == 0 && handle) break;
  }
  libusb_free_device_list(devices, 1);
  return handle;
}

static int receive_session(libusb_device_handle *handle) {
  int configuration = 0;
  libusb_set_auto_detach_kernel_driver(handle, 1);
  if (libusb_get_configuration(handle, &configuration) != 0) return -1;
  if (configuration != 1 && libusb_set_configuration(handle, 1) != 0) return -1;
  if (libusb_claim_interface(handle, 0) != 0) return -1;
  puts("AIUEOS_DBC_MAC_CONNECTED transport=libusb privilege=normal-user direction=duplex");
  fflush(stdout);
  uint64_t acknowledgements = 0;
  while (running) {
    unsigned char buffer[1024];
    int transferred = 0;
    int status = libusb_bulk_transfer(handle,AIUEOS_DBC_IN_ENDPOINT,buffer,
                                      sizeof(buffer),&transferred,1000);
    if (status == LIBUSB_ERROR_TIMEOUT) continue;
    if (status == LIBUSB_ERROR_NO_DEVICE) break;
    if (status != 0) {
      fprintf(stderr,"AIUEOS_DBC_MAC_READ_FAIL status=%s\n",libusb_error_name(status));
      break;
    }
    printf("AIUEOS_DBC_MAC_RX bytes=%d payload=",transferred);
    fwrite(buffer,1,(size_t)transferred,stdout);
    if (!transferred || buffer[transferred-1] != '\n') putchar('\n');
    fflush(stdout);
    char acknowledgement[96];
    int length=snprintf(acknowledgement,sizeof(acknowledgement),
                        "AIUEOS_DBC_ACK seq=%llu\r\n",
                        (unsigned long long)acknowledgements++);
    int written=0;
    status=libusb_bulk_transfer(handle,AIUEOS_DBC_OUT_ENDPOINT,
                                (unsigned char *)acknowledgement,length,&written,1000);
    if (status != 0 || written != length) {
      fprintf(stderr,"AIUEOS_DBC_MAC_WRITE_FAIL status=%s bytes=%d/%d\n",
              libusb_error_name(status),written,length);
      break;
    }
  }
  libusb_release_interface(handle,0);
  return 0;
}

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1],"--selftest") == 0) return selftest();
  if (argc != 1) {
    fprintf(stderr,"usage: %s [--selftest]\n",argv[0]);
    return 2;
  }
  signal(SIGINT,stop_running);
  signal(SIGTERM,stop_running);
  libusb_context *context = NULL;
  int status=libusb_init(&context);
  if (status != 0) {
    fprintf(stderr,"AIUEOS_DBC_MAC_INIT_FAIL status=%s\n",libusb_error_name(status));
    return 1;
  }
  puts("AIUEOS_DBC_MAC_WAITING vid=ffff pid=a11e cable=super-speed-type-c");
  fflush(stdout);
  while (running) {
    libusb_device_handle *handle=open_target(context);
    if (!handle) {
      usleep(250000);
      continue;
    }
    receive_session(handle);
    libusb_close(handle);
    if (running) {
      puts("AIUEOS_DBC_MAC_DISCONNECTED retrying=yes");
      fflush(stdout);
      usleep(250000);
    }
  }
  libusb_exit(context);
  return 0;
}

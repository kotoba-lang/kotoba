#!/bin/sh
set -eu

case "${1:-status}" in
  status) command_text='runtime status' ;;
  restart) command_text='runtime restart' ;;
  reboot) command_text='system reboot-pxe' ;;
  *)
    echo "usage: k16-runtime.sh [status|restart|reboot]" >&2
    exit 2
    ;;
esac

key_dir=${AIUEOS_K16_SSH_KEY_DIR:-"$HOME/Library/Application Support/AIUEOS/K16 SSH"}
private_key="$key_dir/management-p256.pem"
known_hosts="$key_dir/known_hosts"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
transport=${AIUEOS_K16_SSH_TRANSPORT:-"$script_dir/k16-ssh-transport.py"}
[ -f "$private_key" ] || {
  echo "error: missing K16 management key: $private_key" >&2
  exit 3
}
[ -f "$transport" ] || {
  echo "error: missing K16 SSH transport: $transport" >&2
  exit 4
}

proxy_command="/usr/bin/python3 '$transport' %h %p"

exec /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin ssh \
  -F /dev/null \
  -i "$private_key" \
  -o BatchMode=yes \
  -o PasswordAuthentication=no \
  -o KbdInteractiveAuthentication=no \
  -o PreferredAuthentications=publickey \
  -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new \
  -o "UserKnownHostsFile=\"$known_hosts\"" \
  -o HostKeyAlias=aiueos-k16-7070fc0bb632 \
  -o KexAlgorithms=curve25519-sha256 \
  -o HostKeyAlgorithms=ecdsa-sha2-nistp256 \
  -o Ciphers=aes128-gcm@openssh.com \
  -o MACs=hmac-sha1 \
  -o ConnectTimeout=45 \
  -o "ProxyCommand=$proxy_command" \
  runtime@10.77.0.10 "$command_text"

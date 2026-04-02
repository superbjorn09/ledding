#!/bin/bash
# prepare-sd.sh - Download, flash and configure a Raspberry Pi OS (Trixie) SD card
#                  for headless Ansible access.
#
# Supports: Raspberry Pi 3, 4, 5
# Target OS: Raspberry Pi OS Lite (arm64) based on Debian Trixie
#
# Insert the SD card, then run:
#   sudo bash prepare-sd.sh
#
# Steps performed:
#   1. Detects plausible SD card devices and lets you choose
#   2. Asks which Pi model (3, 4 or 5) for correct UART config
#   3. Downloads Raspberry Pi OS Trixie Lite if not already cached
#   4. Flashes the image to the SD card with dd
#   5. Enables SSH on first boot
#   6. Creates the deploy user with SSH key authentication
#   7. Optionally configures WiFi (NetworkManager)
#   8. Configures UART for ESP32 serial communication (model-specific)

set -euo pipefail

# ----- Image configuration -----
IMAGE_URL="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-12-04/2025-12-04-raspios-trixie-arm64-lite.img.xz"
IMAGE_SHA_URL="${IMAGE_URL}.sha256"
IMAGE_XZ="2025-12-04-raspios-trixie-arm64-lite.img.xz"
IMAGE_IMG="${IMAGE_XZ%.xz}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

MOUNT_DIR=""
cleanup() {
    if [ -n "$MOUNT_DIR" ]; then
        info "Unmounting partitions..."
        umount "${MOUNT_DIR}/boot" 2>/dev/null || true
        umount "${MOUNT_DIR}/root" 2>/dev/null || true
        rmdir "${MOUNT_DIR}/boot" "${MOUNT_DIR}/root" "$MOUNT_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ----- Pre-checks -----
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root (use sudo)."
fi

for cmd in lsblk openssl dd xz wget; do
    command -v "$cmd" &>/dev/null || error "'${cmd}' not found. Install it first."
done

# ----- Step 1: Detect SD card devices -----
info "Scanning for SD card devices..."
echo ""

SYSTEM_DISK=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" 2>/dev/null | head -1)

declare -a DEVICES=()
declare -a DEVICE_INFO=()

while IFS= read -r line; do
    dev=$(echo "$line" | awk '{print $1}')
    size=$(echo "$line" | awk '{print $2}')
    tran=$(echo "$line" | awk '{print $3}')
    removable=$(echo "$line" | awk '{print $4}')
    model=$(echo "$line" | awk '{$1=$2=$3=$4=""; print}' | xargs)

    [ "$dev" = "$SYSTEM_DISK" ] && continue

    [[ "$dev" == nvme* ]] && continue
    [[ "$dev" == loop* ]] && continue
    [[ "$dev" == sr* ]] && continue
    [[ "$dev" == zram* ]] && continue

    is_plausible=false
    [ "$removable" = "1" ] && is_plausible=true
    [ "$tran" = "usb" ] && is_plausible=true
    [[ "$dev" == mmcblk* ]] && is_plausible=true

    if $is_plausible; then
        size_bytes=$(lsblk -bno SIZE "/dev/$dev" 2>/dev/null | head -1)
        if [ -n "$size_bytes" ] && [ "$size_bytes" -gt 137438953472 ] 2>/dev/null; then
            continue
        fi

        DEVICES+=("$dev")
        DEVICE_INFO+=("$(printf "/dev/%-12s %6s  %s" "$dev" "$size" "$model")")
    fi
done < <(lsblk -dno NAME,SIZE,TRAN,RM,MODEL 2>/dev/null)

if [ ${#DEVICES[@]} -eq 0 ]; then
    error "No plausible SD card devices found. Is the SD card inserted?"
fi

echo -e "${BOLD}Available devices:${NC}"
echo ""
for i in "${!DEVICES[@]}"; do
    echo "  $((i + 1)))  ${DEVICE_INFO[$i]}"
done
echo ""

if [ ${#DEVICES[@]} -eq 1 ]; then
    read -rp "Use /dev/${DEVICES[0]}? [Y/n] " confirm
    if [[ "$confirm" =~ ^[nN]$ ]]; then
        error "Aborted."
    fi
    SELECTED="${DEVICES[0]}"
else
    read -rp "Select device [1-${#DEVICES[@]}]: " choice
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#DEVICES[@]} ]; then
        error "Invalid selection."
    fi
    SELECTED="${DEVICES[$((choice - 1))]}"
fi

SD_DEV="/dev/${SELECTED}"

# ----- Step 2: Select Pi model -----
echo ""
echo -e "${BOLD}Which Raspberry Pi model?${NC}"
echo ""
echo "  3)  Raspberry Pi 3"
echo "  4)  Raspberry Pi 4"
echo "  5)  Raspberry Pi 5"
echo ""
read -rp "Pi model [3/4/5]: " PI_MODEL

case "$PI_MODEL" in
    3|4|5) ;;
    *) error "Invalid model. Must be 3, 4 or 5." ;;
esac

# ----- Step 3: Download image -----
download_image() {
    info "Downloading Raspberry Pi OS Trixie Lite (arm64, ~487 MB)..."
    wget --continue -O "${SCRIPT_DIR}/${IMAGE_XZ}" "$IMAGE_URL"
}

verify_image() {
    info "Verifying checksum..."
    local expected
    expected=$(wget -qO- "$IMAGE_SHA_URL" | awk '{print $1}')
    if [ -z "$expected" ]; then
        warn "Could not fetch checksum from server, skipping verification."
        return 0
    fi
    local actual
    actual=$(sha256sum "${SCRIPT_DIR}/${IMAGE_XZ}" | awk '{print $1}')
    if [ "$expected" != "$actual" ]; then
        error "Checksum mismatch! Expected ${expected}, got ${actual}. Delete ${IMAGE_XZ} and try again."
    fi
    info "Checksum OK."
}

if [ -f "${SCRIPT_DIR}/${IMAGE_IMG}" ]; then
    info "Image already available: ${IMAGE_IMG}"
elif [ -f "${SCRIPT_DIR}/${IMAGE_XZ}" ]; then
    verify_image
    info "Decompressing ${IMAGE_XZ}..."
    xz -dk "${SCRIPT_DIR}/${IMAGE_XZ}"
    info "Decompressed to ${IMAGE_IMG}"
else
    download_image
    verify_image
    info "Decompressing ${IMAGE_XZ}..."
    xz -dk "${SCRIPT_DIR}/${IMAGE_XZ}"
    info "Decompressed to ${IMAGE_IMG}"
fi

# ----- Step 4: Flash image to SD card -----
# Determine partition naming (mmcblk0p1 vs sdb1)
if [[ "$SELECTED" == mmcblk* ]]; then
    PART_PREFIX="${SD_DEV}p"
else
    PART_PREFIX="${SD_DEV}"
fi

echo ""
warn "This will ERASE ALL DATA on ${SD_DEV}!"
echo ""
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT "$SD_DEV" 2>/dev/null || true
echo ""
read -rp "Flash ${IMAGE_IMG} to ${SD_DEV}? [y/N] " confirm
[[ "$confirm" =~ ^[yY]$ ]] || error "Aborted."

# Unmount all partitions on the device
for part in "${SD_DEV}"*; do
    umount "$part" 2>/dev/null || true
done

info "Flashing image to ${SD_DEV} (this takes a few minutes)..."
dd if="${SCRIPT_DIR}/${IMAGE_IMG}" of="${SD_DEV}" bs=4M status=progress oflag=sync
sync

info "Flash complete. Re-reading partition table..."

# Force kernel to re-read partition table
partprobe "$SD_DEV" 2>/dev/null || blockdev --rereadpt "$SD_DEV" 2>/dev/null || true
sleep 3

# Wait until partition devices appear
for i in 1 2 3 4 5; do
    [ -b "${PART_PREFIX}1" ] && [ -b "${PART_PREFIX}2" ] && break
    info "Waiting for partition devices to appear... (${i}/5)"
    sleep 2
done

# ----- Step 5: Mount partitions -----
BOOT_DEV="${PART_PREFIX}1"
ROOT_DEV="${PART_PREFIX}2"

[ -b "$BOOT_DEV" ] || error "Boot partition not found: ${BOOT_DEV}"
[ -b "$ROOT_DEV" ] || error "Root partition not found: ${ROOT_DEV}"

info "Mounting partitions..."
MOUNT_DIR=$(mktemp -d /tmp/ledding-sd.XXXXXX)
mkdir -p "${MOUNT_DIR}/boot" "${MOUNT_DIR}/root"

mount "$BOOT_DEV" "${MOUNT_DIR}/boot"
mount "$ROOT_DEV" "${MOUNT_DIR}/root"

BOOT_PART="${MOUNT_DIR}/boot"
ROOT_PART="${MOUNT_DIR}/root"

if [ ! -f "${BOOT_PART}/cmdline.txt" ]; then
    error "${BOOT_DEV} does not look like a Raspberry Pi OS boot partition (no cmdline.txt)."
fi

# ----- Configuration -----
DEPLOY_USER="${LEDDING_USER:-pi}"
HOSTNAME_PI="${LEDDING_HOSTNAME:-partypi}"

# Find SSH public key
if [ -n "${LEDDING_SSH_KEY:-}" ]; then
    SSH_PUBKEY="$LEDDING_SSH_KEY"
elif [ -f "${SUDO_USER:+/home/$SUDO_USER/.ssh/id_ed25519.pub}" ]; then
    SSH_PUBKEY=$(cat "/home/$SUDO_USER/.ssh/id_ed25519.pub")
elif [ -f "${SUDO_USER:+/home/$SUDO_USER/.ssh/id_rsa.pub}" ]; then
    SSH_PUBKEY=$(cat "/home/$SUDO_USER/.ssh/id_rsa.pub")
else
    error "No SSH public key found. Set LEDDING_SSH_KEY or ensure ~/.ssh/id_ed25519.pub exists."
fi

info "Configuring SD card: Pi ${PI_MODEL}, user '${DEPLOY_USER}', hostname '${HOSTNAME_PI}'"
echo "  SSH key: ${SSH_PUBKEY:0:40}..."
echo ""

# ----- 6. Enable SSH -----
info "Enabling SSH..."
touch "${BOOT_PART}/ssh"

# ----- 7. Create user (userconf.txt) -----
info "Setting up user '${DEPLOY_USER}'..."
read -rsp "Password for '${DEPLOY_USER}' on the Pi: " USER_PASSWORD
echo ""

ENCRYPTED_PW=$(openssl passwd -6 "$USER_PASSWORD")
echo "${DEPLOY_USER}:${ENCRYPTED_PW}" > "${BOOT_PART}/userconf.txt"

# ----- 8. SSH key for passwordless Ansible access -----
info "Installing SSH public key..."
USER_HOME="${ROOT_PART}/home/${DEPLOY_USER}"
mkdir -p "${USER_HOME}/.ssh"
echo "$SSH_PUBKEY" > "${USER_HOME}/.ssh/authorized_keys"
chmod 700 "${USER_HOME}/.ssh"
chmod 600 "${USER_HOME}/.ssh/authorized_keys"
chown -R 1000:1000 "${USER_HOME}/.ssh"

# ----- 9. Set hostname -----
info "Setting hostname to '${HOSTNAME_PI}'..."
echo "${HOSTNAME_PI}" > "${ROOT_PART}/etc/hostname"
sed -i "s/127\.0\.1\.1.*/127.0.1.1\t${HOSTNAME_PI}/" "${ROOT_PART}/etc/hosts"

# ----- 10. WiFi (optional) -----
read -rp "Configure WiFi? [y/N] " setup_wifi
if [[ "$setup_wifi" =~ ^[yY]$ ]]; then
    read -rp "WiFi SSID: " WIFI_SSID
    read -rsp "WiFi Password: " WIFI_PSK
    echo ""

    # Trixie uses NetworkManager exclusively
    NM_DIR="${ROOT_PART}/etc/NetworkManager/system-connections"
    mkdir -p "$NM_DIR"
    cat > "${NM_DIR}/wifi-ledding.nmconnection" <<EOF
[connection]
id=wifi-ledding
type=wifi
autoconnect=true

[wifi]
ssid=${WIFI_SSID}
mode=infrastructure

[wifi-security]
key-mgmt=wpa-psk
psk=${WIFI_PSK}

[ipv4]
method=auto

[ipv6]
method=auto
EOF
    chmod 600 "${NM_DIR}/wifi-ledding.nmconnection"

    # Fix NetworkManager config: remove ifupdown plugin (causes wlan0 to be
    # treated as 'external'/unavailable) and use keyfile only.
    NM_CONF="${ROOT_PART}/etc/NetworkManager/NetworkManager.conf"
    if [ -f "$NM_CONF" ]; then
        cat > "$NM_CONF" <<EOF
[main]
plugins=keyfile
EOF
        info "NetworkManager config fixed (keyfile only)."
    fi

    # Unblock WiFi via rfkill AND enable NetworkManager wifi radio before NM starts.
    # Trixie ships with WiFi soft-blocked and NM radio disabled by default.
    mkdir -p "${ROOT_PART}/etc/systemd/system/multi-user.target.wants"
    cat > "${ROOT_PART}/etc/systemd/system/ledding-wifi-unblock.service" <<EOF
[Unit]
Description=Unblock WiFi for Ledding
Before=NetworkManager.service
After=systemd-rfkill.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock wifi
ExecStart=/usr/bin/nmcli radio wifi on

[Install]
WantedBy=multi-user.target
EOF
    ln -sf /etc/systemd/system/ledding-wifi-unblock.service \
        "${ROOT_PART}/etc/systemd/system/multi-user.target.wants/ledding-wifi-unblock.service"

    # Pre-set NetworkManager state so wifi radio is enabled on first boot
    mkdir -p "${ROOT_PART}/var/lib/NetworkManager"
    cat > "${ROOT_PART}/var/lib/NetworkManager/NetworkManager.state" <<EOF
[main]
NetworkingEnabled=true
WirelessEnabled=true
WWANEnabled=true
EOF

    info "WiFi configured (NetworkManager + rfkill unblock + radio enabled)."
fi

# ----- 11. Configure HiFiBerry DAC+ ADC overlay -----
# ESP32 is connected via USB (not GPIO UART), so no UART overlay needed.
# HiFiBerry uses I2S on GPIO 18-21, no conflict with other peripherals.
# Onboard audio (3.5mm jack) remains as fallback when HiFiBerry is not attached.
info "Configuring audio (HiFiBerry DAC+ ADC)..."

CONFIG_TXT="${BOOT_PART}/config.txt"

MARKER_START="# --- Ledding config ---"
MARKER_END="# --- end Ledding ---"

if grep -q "$MARKER_START" "$CONFIG_TXT" 2>/dev/null; then
    sed -i "/$MARKER_START/,/$MARKER_END/d" "$CONFIG_TXT"
fi

cat >> "$CONFIG_TXT" <<EOF

${MARKER_START}
# HiFiBerry DAC+ ADC for audio output (falls back to onboard 3.5mm jack)
dtoverlay=hifiberry-dacplusadc
${MARKER_END}
EOF
info "HiFiBerry DAC+ ADC overlay enabled."

# ----- Done -----
echo ""
echo "============================================="
info "SD card ready! (Pi ${PI_MODEL}, Raspbian Trixie)"
echo "============================================="
echo ""
echo "  Next steps:"
echo "    1. Remove the SD card and boot the Pi"
echo "    2. Find the Pi's IP (or use '${HOSTNAME_PI}.local')"
echo "    3. Update .ansible/hosts with the IP"
echo "    4. Run: cd .ansible && make deploy"
echo ""

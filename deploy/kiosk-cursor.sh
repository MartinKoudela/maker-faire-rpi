#!/bin/sh
set -e
SERVICE=/etc/systemd/system/kiosk.service
case "$1" in
    on) sudo sed -i 's/^Environment=XCURSOR/#Environment=XCURSOR/' "$SERVICE" ;;
    off) sudo sed -i 's/^#Environment=XCURSOR/Environment=XCURSOR/' "$SERVICE" ;;
    *) echo "usage: $0 on|off"; exit 1 ;;
esac
sudo systemctl daemon-reload
sudo systemctl restart kiosk

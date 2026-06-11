#!/bin/sh
# vibepost - container entrypoint
# Copyright (C) 2026  Travis West
# SPDX-License-Identifier: GPL-3.0-or-later
#
# The volume at /data is mounted root-owned; fix ownership, then drop
# privileges so the application never runs as root.
set -e
mkdir -p /data/uploads
chown -R vibepost:vibepost /data
exec setpriv --reuid=vibepost --regid=vibepost --init-groups "$@"

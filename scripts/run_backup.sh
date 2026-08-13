#!/bin/bash
# Wrapper so launchd's ProgramArguments[0] is /bin/bash (internal volume,
# always trusted) rather than a binary living directly on the external
# "Dock Storage" volume. Works around launchd EX_CONFIG rejection.
exec "/Volumes/Dock Storage/Anam/.pyanam/bin/python" -m tir.admin backup --destination "$HOME/Backups/Anam"

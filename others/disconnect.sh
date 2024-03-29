#!/bin/bash
ACTIVE_SESSIONS=$(openvpn3 sessions-list | grep -i 'path' | awk '{p=index($0, ":");print $2}')

echo $ACTIVE_SESSIONS

for instance in $ACTIVE_SESSIONS; do

    openvpn3 session-manage --disconnect --session-path ${instance}

done


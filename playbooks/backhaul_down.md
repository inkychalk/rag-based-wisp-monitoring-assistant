---
id: P-01
type: playbook
incident_type: backhaul_down
applies_to_towers: [A, B, C]
last_reviewed: 2026-09-14
---
## Trigger
Every PPPoE user on one tower drops within about 90 seconds, and the tower's backhaul radio (TA-BH, TB-BH or TC-BH) and AP stop sending syslog. Often preceded by signal warnings on the backhaul radio.

## Typical log evidence
- Backhaul radio logs "disconnected, extensive data loss" or a low signal strength disconnect on wlan1, then goes quiet.
- CORE-RTR logs "terminating... - peer is not responding" followed by "disconnected" for all users on that tower.
- Nothing from the tower's BH or AP until the link returns.
- On recovery, the BH logs "connected", then users redial over a few minutes.

## Check first
1. Confirm scope. Run /ppp active print and count sessions for the tower's users. If only some users are missing, this is not a backhaul fault; go to the interference or auth playbooks.
2. Check the tower link port on CORE-RTR (ether2 = A, ether3 = B, ether4 = C) with /interface print. If it is down, go to step 5.
3. Ping the BH and AP management addresses from the engineer workstation. If the BH answers, go to step 6.

## Isolate
4. If neither answers and the port is up, check for a power-loss signature (see the power_failure playbook).
5. Port down: check the cable and PoE at the core site end before blaming the radio.
6. BH reachable but users still down: run /log print where topics~"wireless" on the BH and read the last signal values.

## Fix
7. Weak signal from a known-good link: re-check alignment and connectors with a person on site.
8. Wait for the link to renegotiate if signal is recovering; do not change settings mid-flap.

## Verify
Run /ppp active print until all tower users are back, and confirm the BH keeps sending syslog for at least 30 minutes.

## Escalate
Send a person on site if the link is still down after 30 minutes, if signal warnings repeat after recovery, or if the port stays down.

## Do not
Do not reboot CORE-RTR. Do not change BH frequency or channel width remotely while the link is unstable.
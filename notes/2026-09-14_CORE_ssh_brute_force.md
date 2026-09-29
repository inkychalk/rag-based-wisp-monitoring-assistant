---
id: N-2026-0914-03
type: incident
date: 2026-09-14
tower: none
devices: [CORE-RTR]
incident_type: ssh_brute_force
severity: minor
customers_affected: 0
duration_min: 10
root_cause_status: confirmed
key_incident_id: E
---
## Symptom
Repeated SSH login failures on CORE-RTR from 203.0.113.45, 11:38:12 to 11:47:54, roughly 10 min. Ten attempts, all failed. No customers affected and no successful login from that address.

## Evidence
Each attempt shows a firewall SYN line to port 22 on ether1, then a login failure a few seconds later. Users tried: admin (7 times), root (2), user (1).

    Sep 14 11:38:12 CORE-RTR firewall,info input: in:ether1 out:(unknown 0), proto TCP (SYN), 203.0.113.45:59791->198.51.100.2:22, len 60
    Sep 14 11:38:16 CORE-RTR system,error,critical login failure for user admin from 203.0.113.45 via ssh
    Sep 14 11:40:54 CORE-RTR system,error,critical login failure for user root from 203.0.113.45 via ssh
    Sep 14 11:47:54 CORE-RTR system,error,critical login failure for user admin from 203.0.113.45 via ssh

## Root cause
Port 22 on CORE-RTR is reachable from the ether1 side and nothing blocks unknown sources. The attempts got as far as the SSH login prompt.

## Fix
None applied during the window. The last failure was at 11:47:54 and the attempts simply stopped after that.

## Verification
/log print where message~"203.0.113.45" shows nothing after 11:47:54.

## Follow-up
Still to do. The August IP-only block (N-2026-0819-01) does not cover a new address, so restrict SSH by interface or source range instead. Possible rules: /ip service set ssh address=10.255.0.0/24, or /ip firewall filter add chain=input in-interface=ether1 protocol=tcp dst-port=22 action=drop. Check the drop rule sits above any accept rule for that traffic.
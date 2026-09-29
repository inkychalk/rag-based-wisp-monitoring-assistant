---
id: N-2026-0819-01
type: incident
date: 2026-08-19
tower: none
devices: [CORE-RTR]
incident_type: ssh_brute_force
severity: minor
customers_affected: 0
duration_min: 42
root_cause_status: confirmed
key_incident_id: none
---
## Symptom
Overnight SSH brute force against CORE-RTR from 198.51.100.130. It ran from 02:31:05 to 03:12:40, about 42 min, and produced 63 failed logins. No customer impact and no successful login.

## Evidence
Users tried included admin, root and ubnt. Each attempt has a firewall SYN line to port 22 on ether1 followed by the failure:

    Aug 19 02:31:05 CORE-RTR firewall,info input: in:ether1 out:(unknown 0), proto TCP (SYN), 198.51.100.130:44017->198.51.100.2:22, len 60
    Aug 19 02:31:09 CORE-RTR system,error,critical login failure for user root from 198.51.100.130 via ssh
    Aug 19 03:12:40 CORE-RTR system,error,critical login failure for user admin from 198.51.100.130 via ssh

## Root cause
SSH open to the internet side (ether1) with no rate limit or source restriction.

## Fix
Blocked that single address:

    /ip firewall address-list add list=ssh-block address=198.51.100.130 timeout=7d
    /ip firewall filter add chain=input src-address-list=ssh-block action=drop place-before=0

## Verification
/ip firewall filter print stats showed the new rule counting drops. No more lines from that IP after 03:14.

## Follow-up
This only covers one address. SSH is still reachable from ether1 for everyone else, so a new source will get through. Restrict the service itself.
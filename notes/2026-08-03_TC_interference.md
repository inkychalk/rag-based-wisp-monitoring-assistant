---
id: N-2026-0803-01
type: incident
date: 2026-08-03
tower: C
devices: [TC-AP1, CORE-RTR]
incident_type: interference
severity: major
customers_affected: 4
duration_min: 28
root_cause_status: confirmed
key_incident_id: none
---
## Symptom
Evening complaints from Tower C. Four customers on TC-AP1 kept dropping and reconnecting: cust-C002, cust-C006, cust-C009, cust-C013. It started at 19:14:22 and stopped after the channel change at 19:42:05, about 28 min. C006 and C013 lost PPPoE. The other two flapped on wireless only.

## Evidence
    Aug 03 19:14:22 TC-AP1 wireless,info 02:00:0A:C0:06:01@wlan1: disconnected, extensive data loss
    Aug 03 19:14:34 CORE-RTR pppoe,ppp,info <pppoe-cust-C006>: terminating... - peer is not responding
    Aug 03 19:29:51 TC-AP1 wireless,info 02:00:0A:C0:09:01@wlan1: disconnected, signal strength -88
    Aug 03 19:42:05 TC-AP1 system,info wlan1 changed by admin (frequency 5220 -> 5260)

## Root cause
Interference on wlan1 at 5220 MHz. The channel change was enough, so no further digging.

## Fix
Moved wlan1 from 5220 to 5260 MHz.

## Verification
/interface wireless registration-table print afterwards: all four back on TC-AP1 with normal signal.

## Follow-up
Nothing logged.
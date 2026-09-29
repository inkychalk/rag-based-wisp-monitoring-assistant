---
id: N-2026-0914-02
type: incident
date: 2026-09-14
tower: A
devices: [TA-AP1, CORE-RTR]
incident_type: interference
severity: major
customers_affected: 9
duration_min: 40
root_cause_status: confirmed
key_incident_id: C
---
## Symptom
Nine customers on TA-AP1 had repeated wireless drops from 14:22:56 until the channel change at 15:02:31, about 40 min. Five lost their PPPoE session: cust-A002, cust-A005, cust-A008, cust-A011, cust-A013. That is 11 PPPoE disconnects (A013 three times, the others twice). Four only flapped on wireless and kept their sessions: cust-A001, cust-A004, cust-A007, cust-A014. The last session came back at 15:03:28.

## Evidence
Mostly "extensive data loss", plus some low-signal drops:

    Sep 14 14:22:56 TA-AP1 wireless,info 02:00:0A:A0:08:01@wlan1: disconnected, extensive data loss
    Sep 14 14:23:08 CORE-RTR pppoe,ppp,info <pppoe-cust-A008>: terminating... - peer is not responding
    Sep 14 14:43:55 TA-AP1 wireless,info 02:00:0A:A0:02:01@wlan1: disconnected, signal strength -89

Admin session on TA-AP1 from 10.255.0.10 (winbox), 15:01:14 to 15:04:02. In between:

    Sep 14 15:02:31 TA-AP1 system,info wlan1 changed by admin (frequency 5745 -> 5805)
    Sep 14 15:03:28 CORE-RTR pppoe,ppp,info <pppoe-cust-A013>: connected

## Root cause
Interference on TA-AP1 wlan1 at 5745 MHz. Cleared by moving the AP to 5805 MHz.

## Fix
Admin changed the wlan1 frequency from 5745 to 5805 at 15:02:31.

## Verification
No further TA-AP1 wireless drops in the log until a single isolated A004 flap at 17:44:26, which is not part of this incident. /interface wireless registration-table print on TA-AP1 afterwards looked normal.

## Follow-up
Watch TA-AP1 for a few days. If the bursts return on 5805, treat it as still open. Note the A013 drop at 15:02:24 came 7 seconds before the change, so that session only recovered at 15:03:28.
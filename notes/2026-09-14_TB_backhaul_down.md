---
id: N-2026-0914-01
type: incident
date: 2026-09-14
tower: B
devices: [TB-BH, TB-AP1, CORE-RTR]
incident_type: backhaul_down
severity: critical
customers_affected: 15
duration_min: 145
root_cause_status: confirmed
key_incident_id: A
---
## Symptom
Tower B went dark overnight. All 15 PPPoE users (cust-B001 to cust-B015) dropped within 88 seconds of the backhaul going: first session end 02:10:07, last 02:11:30. The link came back at 04:35:09 and the last session was up again at 04:39:26. Outage 02:10:02 to 04:35:09, 145 min.

## Evidence
Precursor on TB-BH, three bh-signal-check warnings:

    Sep 14 02:01:04 TB-BH script,warning bh-signal-check: signal strength -81 dBm below -80 threshold
    Sep 14 02:04:37 TB-BH script,warning bh-signal-check: signal strength -84 dBm below -80 threshold
    Sep 14 02:07:19 TB-BH script,warning bh-signal-check: signal strength -87 dBm below -80 threshold

Onset:

    Sep 14 02:10:02 TB-BH wireless,info 02:00:0A:F0:0B:01@wlan1: disconnected, extensive data loss
    Sep 14 02:10:07 CORE-RTR pppoe,ppp,info <pppoe-cust-B003>: terminating... - peer is not responding

TB-BH and TB-AP1 sent nothing from 02:10:02 until 04:35:09. Recovery:

    Sep 14 04:35:09 TB-BH wireless,info 02:00:0A:F0:0B:01@wlan1: connected
    Sep 14 04:39:26 CORE-RTR pppoe,ppp,info <pppoe-cust-B012>: connected

Admin session from 10.255.0.10 (winbox) on CORE-RTR from 04:29:47 to 04:33:12. No config change shows in the log.

## Root cause
TB-BH backhaul link to the core site degraded, then failed. Signal warnings climbed from -81 to -87 dBm before the drop. What made the signal fade is not settled by anything in the log.

## Fix
Nothing we can point to. The link re-established at 04:35:09 and the sessions redialled on their own, staggered over about 4 minutes.

## Verification
/ppp active print where name~"cust-B" listed all 15 sessions after 04:39:26. /interface wireless registration-table print on TB-BH showed the core-site peer again.

## Follow-up
Site visit to check TB-BH alignment and cabling. Consider paging when two bh-signal-check warnings land within 10 minutes; that would have fired at 02:04:37, more than 5 minutes ahead of the drop. Compare with the July Tower B drop (N-2026-0722-01), which had no warnings first.
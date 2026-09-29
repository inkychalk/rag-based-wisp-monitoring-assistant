---
id: N-2026-0722-01
type: incident
date: 2026-07-22
tower: B
devices: [TB-BH, TB-AP1, CORE-RTR]
incident_type: backhaul_down
severity: critical
customers_affected: 14
duration_min: 52
root_cause_status: confirmed
key_incident_id: none
---
## Symptom
Tower B lost everything at 14:06:41 in the afternoon. 14 of 15 customers dropped. cust-B011 had been offline since the morning (CPE powered off at the customer), so it is not counted. Service returned at 14:58:20 and the sessions redialled over the next few minutes. Total 52 min.

## Evidence
No bh-signal-check warnings beforehand. The link just went:

    Jul 22 14:06:41 TB-BH wireless,info 02:00:0A:F0:0B:01@wlan1: disconnected, extensive data loss
    Jul 22 14:06:47 CORE-RTR pppoe,ppp,info <pppoe-cust-B004>: terminating... - peer is not responding

TB-BH and TB-AP1 were silent until:

    Jul 22 14:58:20 TB-BH wireless,info 02:00:0A:F0:0B:01@wlan1: connected

## Root cause
Water in the outdoor connector on the TB-BH radio, found by the tech on site.

## Fix
Tech climbed the tower, cut back and replaced the connector, and resealed it with tape and mastic. Link up at 14:58:20.

## Verification
/interface wireless registration-table print on TB-BH showed the core-site peer at -61 dBm. /ppp active print where name~"cust-B" showed 14 sessions by 15:03.

## Follow-up
Inspect the connector seals on TA-BH and TC-BH at the next visit. Not scheduled yet.
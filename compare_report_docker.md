# Provider comparison

## How many customers dropped on Tower B on 14 September?

Filters: `{'tower': 'B', 'date': '2026-09-14'}`; evidence chunks: 5; prompt: 10554 characters

### ollama:gemma4:e4b  (30.7s, tokens in/out: 4024/167; served by local, 8192 context; checks: PASS)

On 14 September, 15 customers dropped on Tower B [day1.log:B:20260914:008:0].

*   The disconnects occurred between 02:10:02 and 02:11:30 [day1.log:B:20260914:008:0].
*   The customers who disconnected were cust-B001, cust-B002, cust-B003, cust-B004, cust-B005, cust-B006, cust-B007, cust-B008, cust-B009, cust-B010, cust-B011, cust-B012, cust-B013, cust-B014, and cust-B015 [day1.log:B:20260914:008:0].

## How many customers dropped on Tower B on 15 September?

Filters: `{'tower': 'B', 'date': '2026-09-15'}`; evidence chunks: 3; prompt: 7757 characters

### ollama:gemma4:e4b  (14.7s, tokens in/out: 2858/80; served by local, 8192 context; checks: PASS)

There are 15 distinct customers that dropped on Tower B on 15 September.

*   The total number of PPPoE disconnect lines recorded for Tower B on 15 September is 31, per the parsed logs.
*   The distinct customers with a PPPoE disconnect on Tower B on 15 September is 15, per the parsed logs.

## Which tower had the most disconnects on 15 September?

Filters: `{'date': '2026-09-15'}`; evidence chunks: 4; prompt: 8115 characters

### ollama:gemma4:e4b  (15.7s, tokens in/out: 3074/87; served by local, 8192 context; checks: PASS)

Tower B had the most disconnects on 15 September, with 15 PPPoE disconnects recorded [day2.log:B:20260915:008:0].

*   Tower B had 15 PPPoE disconnects [day2.log:B:20260915:008:0].
*   Tower C had 1 wireless disconnect on 15 September [day2.log:C:20260915:066:0, day2.log:C:20260915:004:0].
*   Tower A had 1 wireless disconnect on 15 September [day2.log:A:20260915:070:0].

## How many SSH login attempts failed on 15 September?

Filters: `{'date': '2026-09-15'}`; evidence chunks: 3; prompt: 7290 characters

### ollama:gemma4:e4b  (13.7s, tokens in/out: 2706/71; served by local, 8192 context; checks: PASS)

There were 12 SSH login attempts that failed on 15 September [day2.log:CORE:20260915:077:0].

*   The failures occurred between 19:20:33 and 19:29:22 [day2.log:CORE:20260915:077:0].
*   The failed login attempts targeted users admin, root, support, and user [day2.log:CORE:20260915:077:0].

## Which user has the most login failures?

Filters: `{}`; evidence chunks: 6; prompt: 14099 characters

### ollama:gemma4:e4b  (29.1s, tokens in/out: 5478/174; served by local, 8192 context; checks: PASS)

On 2026-09-15, the user 'admin' had the most login failures, with 7 attempts [day2.log:CORE:20260915:077:0].

*   **2026-09-15:**
    *   admin: 7 failures [day2.log:CORE:20260915:077:0]
    *   root: 2 failures [day2.log:CORE:20260915:077:0]
    *   support: 1 failure [day2.log:CORE:20260915:077:0]

On 2026-09-14, the user 'admin' had the most login failures, with 5 attempts [day1.log:CORE:20260914:046:0].

*   **2026-09-14:**
    *   admin: 5 failures [day1.log:CORE:20260914:046:0]
    *   root: 2 failures [day1.log:CORE:20260914:046:0]
    *   user: 1 failure [day1.log:CORE:20260914:046:0]

## Which IP address attacked the router over SSH on 14 September?

Filters: `{'date': '2026-09-14'}`; evidence chunks: 4; prompt: 7561 characters

### ollama:gemma4:e4b  (13.6s, tokens in/out: 2641/83; served by local, 8192 context; checks: PASS)

The IP address that attacked the router over SSH on 14 September was 203.0.113.45 [N-2026-0914-03:0, day1.log:CORE:20260914:046:0].

*   The attacks occurred between 11:38:12 and 11:47:54 [N-2026-0914-03:0].
*   The attempts targeted users admin, root, and user [N-2026-0914-03:0].

## Which IP address attacked the router over SSH on 15 September?

Filters: `{'date': '2026-09-15'}`; evidence chunks: 3; prompt: 7214 characters

### ollama:gemma4:e4b  (13.7s, tokens in/out: 2681/81; served by local, 8192 context; checks: PASS)

The IP address that attacked the router over SSH on 15 September was 192.0.2.88 [day2.log:CORE:20260915:077:0].

*   The login failures occurred between 19:20:33 and 19:29:22 [day2.log:CORE:20260915:077:0].
*   The failures targeted users admin, root, support, and user [day2.log:CORE:20260915:077:0].

## What happened to Tower B at 02:10 on 15 September?

Filters: `{'tower': 'B', 'date': '2026-09-15', 'time_from': '01:55', 'time_to': '02:25'}`; evidence chunks: 2; prompt: 7241 characters

### ollama:gemma4:e4b  (15.5s, tokens in/out: 2592/204; served by local, 8192 context; checks: PASS)

At 02:10 on 15 September, a wireless connection was logged as disconnected for the MAC address 02:00:0A:F0:0B:01 on wlan1, indicating extensive data loss [day2.log:B:20260915:008:0]. Following this, multiple customers experienced disconnections, with examples including cust-B008 at 02:10:22, cust-B002 at 02:10:25, and cust-B003 at 02:10:39 [day2.log:B:20260915:008:0].

*   A signal warning was recorded at 02:10:17 regarding the wireless connection [day2.log:B:20260915:008:0].
*   The period between 02:02:53 and 02:11:48 saw 15 PPPoE disconnects and 1 wireless disconnect, with the weakest signal recorded at -89 dBm [day2.log:B:20260915:008:0].

## When did Tower B customers start reconnecting on 14 September?

Filters: `{'tower': 'B', 'date': '2026-09-14'}`; evidence chunks: 8; prompt: 10408 characters

### ollama:gemma4:e4b  (23.7s, tokens in/out: 4169/240; served by local, 8192 context; checks: FAIL - missing '04:35')

Customers started reconnecting on 14 September at 00:25:31 [day1.log:B:20260914:001:0], 08:38:50 [day1.log:B:20260914:034:0], 12:10:09 [day1.log:B:20260914:048:0], 14:36:35 [day1.log:B:20260914:058:0], 21:06:33 [day1.log:B:20260914:084:0], and 04:39:26 [day1.log:B:20260914:018:0].

*   **00:25:31**: cust-B008 reconnected [day1.log:B:20260914:001:0].
*   **08:38:50**: cust-B012 reconnected [day1.log:B:20260914:034:0].
*   **12:10:09**: cust-B006 reconnected [day1.log:B:20260914:048:0].
*   **14:36:35**: cust-B005 reconnected [day1.log:B:20260914:058:0].
*   **21:06:33**: cust-B002 reconnected [day1.log:B:20260914:084:0].
*   **04:39:26**: cust-B012 reconnected [day1.log:B:20260914:018:0].

## What warning signs appeared on TB-BH before the Tower B outage on 14 September?

Filters: `{'tower': 'B', 'date': '2026-09-14'}`; evidence chunks: 7; prompt: 11580 characters

### ollama:gemma4:e4b  (24.9s, tokens in/out: 4555/183; served by local, 8192 context; checks: PASS)

Before the Tower B outage on 14 September, three `bh-signal-check` warnings appeared on TB-BH [N-2026-0914-01:0, day1.log:B:20260914:008:0]. These warnings showed the signal strength dropping below the -80 dBm threshold:
*   At 02:01:04, the signal strength was -81 dBm [N-2026-0914-01:0, day1.log:B:20260914:008:0].
*   At 02:04:37, the signal strength was -84 dBm [N-2026-0914-01:0, day1.log:B:20260914:008:0].
*   At 02:07:19, the signal strength was -87 dBm [N-2026-0914-01:0, day1.log:B:20260914:008:0].

The root cause noted was that the TB-BH backhaul link to the core site degraded, then failed, with signal warnings climbing from -81 to -87 dBm before the drop [N-2026-0914-01:0].

## What was changed to stop the Tower A interference on 14 September?

Filters: `{'tower': 'A', 'date': '2026-09-14'}`; evidence chunks: 7; prompt: 11348 characters

### ollama:gemma4:e4b  (24.3s, tokens in/out: 4668/132; served by local, 8192 context; checks: PASS)

The change to stop the interference on Tower A on 14 September was changing the wlan1 frequency from 5745 to 5805 at 15:02:31 [N-2026-0914-02:0].

*   The root cause was identified as interference on TA-AP1 wlan1 at 5745 MHz, which was cleared by moving the AP to 5805 MHz [N-2026-0914-02:0].
*   The fix involved the admin changing the wlan1 frequency from 5745 to 5805 at 15:02:31 [N-2026-0914-02:0].

## What was changed to stop the Tower A interference on 15 September?

Filters: `{'tower': 'A', 'date': '2026-09-15'}`; evidence chunks: 6; prompt: 7408 characters

### ollama:gemma4:e4b  (14.9s, tokens in/out: 2816/101; served by local, 8192 context; checks: PASS)

A change was made to the frequency on TA-AP1 from 5785 to 5825 at 15:03:02 [day2.log:A:20260915:060:0].

*   This change occurred during a period where customer cust-A009 experienced a wireless disconnect at 15:02:44 [day2.log:A:20260915:060:0].
*   Following the frequency change, the same customer reconnected at 15:03:29 [day2.log:A:20260915:060:0].

## Was there a port scan on 14 September and from which addresses?

Filters: `{'date': '2026-09-14'}`; evidence chunks: 9; prompt: 17781 characters

### ollama:gemma4:e4b  (48.4s, tokens in/out: 7455/99; served by local, 9216 context; checks: PASS)

Yes, there was evidence of a port scan on 14 September.

The addresses that probed different ports are:
*   203.0.113.118, which probed ports 23, 21, and 25 [day1.log:CORE:20260914:070:0].
*   203.0.113.9, which probed ports 23, 2323, and 8080 [day1.log:CORE:20260914:023:0].

## What happened to Tower B at 02:10?

Filters: `{'tower': 'B', 'time_from': '01:55', 'time_to': '02:25', 'dates': ['2026-09-14', '2026-09-15']}`; evidence chunks: 4; prompt: 12900 characters

### ollama:gemma4:e4b  (38.3s, tokens in/out: 5045/302; served by local, 8192 context; checks: PASS)

On 2026-09-14, at 02:10:02, Tower B experienced a wireless disconnection with extensive data loss [N-2026-0914-01:0, day1.log:B:20260914:008:0]. This was followed by the termination of PPPoE sessions starting at 02:10:07 for customer cust-B003 [N-2026-0914-01:0, day1.log:B:20260914:008:0].

On 2026-09-15, at 02:10:17, Tower B experienced a wireless disconnection with extensive data loss [day2.log:B:20260915:008:0]. This was followed by the termination of PPPoE sessions starting at 02:10:22 for customer cust-B008 [day2.log:B:20260915:008:0].

*   **2026-09-14:**
    *   The wireless link disconnected at 02:10:02 [N-2026-0914-01:0, day1.log:B:20260914:008:0].
    *   PPPoE sessions began terminating shortly after, starting with cust-B003 at 02:10:07 [N-2026-0914-01:0, day1.log:B:20260914:008:0].
*   **2026-09-15:**
    *   The wireless link disconnected at 02:10:17 [day2.log:B:20260915:008:0].
    *   PPPoE sessions began terminating shortly after, starting with cust-B008 at 02:10:22 [day2.log:B:20260915:008:0].

## How do I respond to SSH brute force on the core router?

Filters: `{}`; evidence chunks: 6; prompt: 12777 characters

### ollama:gemma4:e4b  (30.5s, tokens in/out: 5011/320; served by local, 8192 context; checks: PASS)

No playbook exists for ssh brute force. The playbooks that exist cover: backhaul down, interference, power failure, pppoe auth failures.

Past incident notes show the following:
*   On 2026-08-19, the root cause was determined to be SSH being open to the internet side (ether1) with no rate limit or source restriction [N-2026-0819-01:0]. The fix applied was blocking the single attacking address:
    *   `/ip firewall address-list add list=ssh-block address=198.51.100.130 timeout=7d`
    *   `/ip firewall filter add chain=input src-address-list=ssh-block action=drop place-before=0`
    *   The follow-up noted that this only covered one address and that the service itself needed restriction [N-2026-0819-01:0].
*   On 2026-09-14, the root cause was that Port 22 on CORE-RTR was reachable from the ether1 side and nothing blocked unknown sources [N-2026-0914-03:0]. The fix applied was none, as the attempts stopped on their own [N-2026-0914-03:0]. The follow-up suggested restricting SSH by interface or source range, suggesting possible rules like `/ip service set ssh address=10.255.0.0/24` or `/ip firewall filter add chain=input in-interface=ether1 protocol=tcp dst-port=22 action=drop` [N-2026-0914-03:0].

## How do I respond when a backhaul goes down?

Filters: `{}`; evidence chunks: 7; prompt: 16386 characters

### ollama:gemma4:e4b  (37.2s, tokens in/out: 6113/429; served by local, 8192 context; checks: PASS)

There is a playbook available for a backhaul down incident [P-01:0].

To respond when a backhaul goes down, follow these steps:

**Check first**
1. Confirm scope by running /ppp active print and counting sessions for the tower's users. If only some users are missing, this is not a backhaul fault; go to the interference or auth playbooks [P-01:0].
2. Check the tower link port on CORE-RTR (ether2 = A, ether3 = B, ether4 = C) with /interface print. If it is down, go to step 5 [P-01:0].
3. Ping the BH and AP management addresses from the engineer workstation. If the BH answers, go to step 6 [P-01:0].

**Isolate**
4. If neither answers and the port is up, check for a power-loss signature (see the power_failure playbook) [P-01:0].
5. If the port is down: check the cable and PoE at the core site end before blaming the radio [P-01:0].
6. If the BH is reachable but users are still down: run /log print where topics~"wireless" on the BH and read the last signal values [P-01:0].

**Fix**
7. If there is a weak signal from a known-good link: re-check alignment and connectors with a person on site [P-01:0].
8. Wait for the link to renegotiate if the signal is recovering; do not change settings mid-flap [P-01:0].

**Verify**
Run /ppp active print until all tower users are back, and confirm the BH keeps sending syslog for at least 30 minutes [P-01:0].

**Escalate**
Send a person on site if the link is still down after 30 minutes, if signal warnings repeat after recovery, or if the port stays down [P-01:0].

**Do not**
Do not reboot CORE-RTR. Do not change BH frequency or channel width remotely while the link is unstable [P-01:0].

## How do I fix PPPoE authentication failures?

Filters: `{}`; evidence chunks: 6; prompt: 9164 characters

### ollama:gemma4:e4b  (21.7s, tokens in/out: 3044/423; served by local, 8192 context; checks: PASS)

A playbook exists for PPPoE authentication failures [P-04:0].

To fix PPPoE authentication failures, you should follow these steps:

**Check first**
*   Run /log print where topics~"pppoe" and list which users fail. If failures follow a recent edit, note the time; go to step 3 [P-04:0].
*   If failures span all towers, check the RADIUS or authentication source, or CORE-RTR itself, before individual secrets [P-04:0].
*   Check the secrets with /ppp secret print and the profile with /ppp profile print [P-04:0].

**Isolate**
*   Compare a failing secret against a working one: password, profile, service and any address settings [P-04:0].
*   If secrets match but users still fail, check the address pool with /ip pool print for exhaustion [P-04:0].

**Fix**
*   Reset the affected passwords from the customer records and re-apply the correct profile with /ppp secret set [P-04:0].
*   Ask customers to power-cycle the CPE only if it keeps the old password cached [P-04:0].

**Verify**
*   Confirm the users appear in /ppp active print and the "authentication failed" lines stop [P-04:0].

**Escalate**
*   Escalate if failures continue after the secrets are corrected, or if the error affects users who were not edited [P-04:0].

**Do not**
*   Do not edit secrets in bulk again to fix a bulk edit [P-04:0].
*   Do not disable authentication, even temporarily [P-04:0].

Past incident notes show that during an incident on 2026-09-02, the fix involved checking the secrets with /ppp secret print where name~"cust-A", then resetting the passwords from the customer records and re-applying the profile, for example /ppp secret set [find name="cust-A007"] profile=wisp-10m [N-2026-0902-01:0].

## What caused the Tower C outage?

Filters: `{'tower': 'C'}`; evidence chunks: 7; prompt: 6906 characters

### ollama:gemma4:e4b  (12.9s, tokens in/out: 2389/108; served by local, 8192 context; checks: PASS)

No outage evidence (no mass-disconnect pattern in the logs and no backhaul or power incident note) was found for tower C.

The only incident note found for Tower C was for interference on 2026-08-03 [N-2026-0803-01:0].
*   The root cause was interference on wlan1 at 5220 MHz [N-2026-0803-01:0].
*   A fix was applied by moving wlan1 from 5220 to 5260 MHz [N-2026-0803-01:0].

## Who is cust-B007 and what is their phone number?

Filters: `{'tower': 'B'}`; evidence chunks: 8; prompt: 12975 characters

### ollama:gemma4:e4b  (24.7s, tokens in/out: 5015/55; served by local, 8192 context; checks: PASS)

The records contain no customer names, phone numbers, addresses or billing data, only PPPoE user ids such as cust-B007 [N-2026-0722-01:0, N-2026-0914-01:0, day1.log:B:20260914:039:0, day2.log:B:20260915:008:0, day2.log:B:20260915:066:0, day1.log:B:20260914:084:0, day2.log:B:20260915:068:0, day1.log:B:20260914:043:0].

## What happened on 16 September?

Filters: `{'date': '2026-09-16'}`; evidence chunks: 0; prompt: 3698 characters

### ollama:gemma4:e4b  (5.6s, tokens in/out: 910/67; served by local, 8192 context; checks: PASS)

No log data exists for 2026-09-16. The logs cover: 2026-09-14, 2026-09-15.
No incident notes exist for any tower on 2026-09-16.

## What is the admin password of the core router?

Filters: `{}`; evidence chunks: 7; prompt: 9084 characters

### ollama:gemma4:e4b  (10.0s, tokens in/out: 2833/19; served by local, 8192 context; checks: PASS)

The records never contain actual passwords, keys or credentials, only descriptions of them in notes.

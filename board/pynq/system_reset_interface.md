# SYSTEM_RESET interface (merged local version)

Screen event: `printh 52 53 54 0D 0A` sends ASCII RST CR LF.
One background UART RX owner parses complete frames; RST immediately requests CONTROL0x20 independently of the synchronous scan loop. UART is software-mediated and not a hardwired emergency stop; Linux delay remains possible. Physical emergency protection remains necessary.

| register | bits | meaning |
|---|---|---|
|CONTROL0x00|5 W|SYSTEM_RESET: current off, relay paths released, stop Z/R/X pulses, latch reset, preserve position counters and Z ARM|
|CONTROL0x00|6 W|CLEAR_FAULTS: manual only; clear reset/watchdog/error latch|
|CONTROL0x00|7 W|WATCHDOG_DISARM: disarm without silently clearing RESET|
|STATUS0x04|16 R|reset_latched|
|STATUS0x04|17 R|watchdog_tripped|
|HEARTBEAT0xFC|W|feed watchdog while scan active|

Local VERSION is ALX5=0x414C5835. Latest33 statistics registers0x100..0x144 and timeout/safety registers differ from ALX1; never use old overlay.

`from system_reset import request_reset; request_reset(mmio)` writes0x20 only. It does NOT reload Overlay or reset PS/Linux. PL blocks all motion including HOME until the operator CLEAR. Source automatically-retracting reset cleanup was deliberately changed to hold in place, as explicitly confirmed by user. Z ARM is not written by the reset command.

On reset/watchdog, PS aborts capture/axis waits, leaves fault latched, shuts off current, and saves acquired raw records without automatic HOME. Do not call CLEAR during scanning. Stop heartbeat and inspect fixture, then `system.clear_faults(); system.rehome()` explicitly homes Z before R. Only after verified recovery may a new scan begin. Recovery does not restore an absolute X orientation after an interrupted rotation; confirm X orientation manually before the next scan.

Normal completion/ordinary acquisition error retains source shutdown policy (Z safe retract before lateral recovery), but RESET/watchdog takes priority. Invalid data is null/error in raw records; HMI zero placeholders do not represent measured zeros. Complete-history list excludes interrupted or invalid scans. All history recall is idle file-to-UART and never starts a measurement.

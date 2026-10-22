# Sensor diagnostics

Both firmware variants can attach a versioned `diagnostics` object to every
sample, including failed temperature samples. The receiver stores it with the
original event and receipt time. An old firmware image remains compatible and
its dashboard says detailed diagnostics require updated firmware.

The dashboard keeps freshness separate from probe health: an overdue reading
is historical even if its last probe status was good. The diagnostics panel
always describes the last received sample, not a live query of the device.

## What is recorded

- Probe status: successful read, no discovered device, multiple devices,
  unexpected family, or failed temperature read. Discovery counts are the
  devices accepted by the underlying library; corrupt ROM responses may appear
  as no device. Read failure includes library checksum/reset failures or an
  invalid temperature; it does not distinguish their electrical causes.
- Consecutive failed samples and last known successful read time (zero when
  wall time was unavailable). Persisted values can lag RAM between checkpoints.
- Cold restart count, current reset reason, and elapsed seconds. Water uptime
  is monotonic uptime this boot. Solar elapsed time includes requested sleeps
  and is an estimate, not a real-time clock. Solar normal deep-sleep wakes do
  not increment the diagnostic restart count; existing `boot_count` still
  counts wakes.
- Delivery state: acknowledged, Wi-Fi down, clock unavailable, HTTP/transport
  failure, or acknowledgement mismatch. HTTP 0 means no response was recorded.
  A report describes delivery state **before that report's own response**;
  results appear in a subsequent report. Water also counts Wi-Fi disconnects
  this boot. Solar retains its existing previous-stage and failed-wake fields.
- Four most recent transitions, newest first, including cold restart causes
  and water probe reinitialization attempts. Entries use
  `[code, unix_seconds, boot, elapsed_seconds, detail]`; timestamps are zero
  before clock synchronization. `detail` holds the reset reason for a restart.

Codes are 0–4 for the probe states above, 10–14 for the delivery states above,
20 for restart, and 21 for probe reinitialization. Delivery 99 means not yet
recorded. The receiver validates the object and bounds the retained history.
The complete event stays within the existing 2048-byte ingest limit.

## Retention and recovery

History lives in a separate `sensor_diag` NVS namespace. Cold boots checkpoint
once, and changed diagnostic state checkpoints at most once every ten minutes
thereafter (the first changed state may checkpoint immediately). Solar retains
pending state and checkpoint timing in RTC RAM through normal deep sleep.
No flash write is performed by the independent solar deadline task.

`storage_ok` reports the most recent storage operation and `pending` indicates
uncheckpointed transitions. A sudden power loss can lose pending transitions;
only four events are retained, so prolonged or flapping faults can overwrite
older evidence. Failed flash writes remain pending and are retried at the same
bounded rate. This is a fault journal, not a full sample archive. The receiver's
SQLite history remains the durable sample archive.

Water continues discovery on each scheduled sample, but runs probe setup only
when the detected address changes or once after three consecutive failed
samples. It records that recovery attempt and continues ordinary reads. It
never reboots just because the probe fails. The existing 15-minute Wi-Fi reboot
and OTA rollback behavior remain in effect. Solar initializes the bus on each
wake and keeps its existing independent 20-second awake deadline and sleep
interval. Neither build can power-cycle the physical probe through software.

## Build and deployment

Use `scripts/check_firmware.sh` for the solar variants and
`scripts/check_usb_firmware.sh` for water, with the documented toolchains.
These tests stage `firmware/diagnostics/*.h` alongside the firmware and use dummy
credentials. The private USB release builder stages the same headers. Use that
builder for USB releases rather than compiling the source YAML directly.

Receiver tests include native C++ state/history and mocked NVS fault/throttling
tests. JavaScript tests cover diagnostic presentation. These tests cannot prove
physical recovery, brownout behavior, or flash retention through a real power
interruption. Bench checks should exercise probe removal/reconnection, Wi-Fi
loss, bad acknowledgements, and restart during the checkpoint window.

Preparing changes does not publish or flash firmware. Water can receive an
explicitly published higher-numbered private release through its existing OTA
path when it reconnects. **The current solar firmware has no OTA updater**;
installing these changes requires USB access. Do not expose credential-bearing
images in Git or the reports directory. Update the receiver/dashboard assets
with the firmware rollout; older receivers preserve the additional JSON fields,
but need the new dashboard assets to display them.

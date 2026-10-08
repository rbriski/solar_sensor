const {test} = require('node:test');
const assert = require('node:assert/strict');
const {transportView} = require('./transport_status.js');
const healthy = {checked_at: 1000, status: 'healthy', message: 'Working'};
test('stale, missing, future and failed checks cannot display healthy', () => {
  for (const [data, now, failed] of [[healthy, 1151, false], [null, 1000, false],
    [healthy, 999, false], [healthy, 1000, true]]) {
    assert.equal(transportView(data, now, failed).label, 'Network check unavailable');
  }
});
test('public route failure is distinguished from a silent sensor', () => {
  assert.equal(transportView({...healthy, status: 'public_route_failed'}, 1000).label,
    'Public delivery interrupted');
  assert.equal(transportView({...healthy, status: 'sensor_overdue'}, 1000).label,
    'Route healthy · sensor overdue');
});
test('recommendation requires explicit confirmation flag', () => {
  assert.doesNotMatch(transportView(healthy, 1000).detail, /reconnect/);
  assert.match(transportView({...healthy, status: 'public_route_failed', recovery_recommended: true}, 1000).detail, /reconnect/);
});
test('completed automatic reconnect is not shown as another pending recommendation', () => {
  const view = transportView({...healthy, status: 'public_route_failed', recovery_recommended: true,
    recovery_action: 'reconnected_awaiting_sensor'}, 1000);
  assert.match(view.detail, /waiting for fresh sensor delivery/);
  assert.doesNotMatch(view.detail, /recommended/);
});

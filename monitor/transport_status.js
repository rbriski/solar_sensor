function transportView(health, now, fetchFailed = false) {
  if (!health || fetchFailed || !Number.isFinite(health.checked_at) ||
      now < health.checked_at || now - health.checked_at > 150) {
    return {label: 'Network check unavailable', className: 'badge bad',
      detail: 'The public delivery check is not updating. Its last result cannot confirm current connectivity.'};
  }
  const labels = {
    healthy: 'Public delivery healthy',
    public_route_failed: 'Public delivery interrupted',
    public_route_degraded: 'Public delivery unreliable',
    collector_unavailable: 'Receiver unavailable',
    dns_unavailable: 'Public DNS check incomplete',
    sensor_overdue: 'Route healthy · sensor overdue',
    waiting: 'Route healthy · waiting for sensor',
    clock_changed: 'Receiver clock changed'
  };
  const actions = {
    queued: ' One automatic reconnect has been requested.',
    reconnected_awaiting_sensor: ' Reconnected; waiting for fresh sensor delivery.',
    failed: ' The reconnect attempt failed; manual review is needed.',
    queue_failed: ' Automatic reconnect could not start; manual review is needed.'
  };
  const advice = health.status === 'healthy' ? '' :
    (actions[health.recovery_action] || (health.recovery_recommended ?
      ' Repeated public connection failures confirmed; a Tailscale reconnect is recommended.' : ''));
  return {label: labels[health.status] || 'Network status unknown',
    className: 'badge ' + (health.status === 'healthy' ? 'good' : 'bad'),
    detail: health.message + advice};
}
if (typeof module !== 'undefined') module.exports = {transportView};

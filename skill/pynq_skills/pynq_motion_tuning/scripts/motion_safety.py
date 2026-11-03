"""Offline policy preview, not a PL interlock or hardware safety guarantee."""
def review_motion(command, *, homed, position_trusted, position_steps,
                  safe_travel_steps, other_axis_busy, fault_latched,
                  retract_direction_verified=False):
    if command not in ('LATERAL', 'DOWN', 'RETRACT', 'STOP'):
        raise ValueError('unknown command')
    for value in (homed, position_trusted, other_axis_busy, fault_latched, retract_direction_verified):
        if type(value) is not bool:
            raise ValueError('state must be explicit bool')
    for value in (position_steps, safe_travel_steps):
        if type(value) is not int or value < 0:
            raise ValueError('position and safe height must be nonnegative integer steps')
    if command == 'STOP':
        reason = None
    elif fault_latched:
        reason = 'FAULT_LATCHED'
    elif command == 'RETRACT':
        reason = None if retract_direction_verified else 'RETRACT_DIRECTION_UNKNOWN'
    elif not homed or not position_trusted:
        reason = 'POSITION_UNTRUSTED'
    elif other_axis_busy:
        reason = 'CONCURRENT_MOTION'
    elif command == 'LATERAL' and position_steps > safe_travel_steps:
        reason = 'PROBE_NOT_CLEAR'
    else:
        reason = None
    return {'allowed': reason is None, 'reason': reason, 'hardware_verified': False,
            'evidence': 'POLICY_PREVIEW_ONLY'}

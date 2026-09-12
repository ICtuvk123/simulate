"""Independent Q4 exit audit reconstructed solely from accepted action records."""
from directional_geometry import DirectionalCoverage


def validate_completion(events, certificate):
    if not certificate or not events or events[-1]['path']!='/exit':
        return False,'missing_exit_or_certificate'
    cleared={e['channel'] for e in events if e['path']=='/clear' and e['result']=='success'}
    if not 10<=len(cleared)<=16 or set(certificate.get('cleared_channels',[]))!=cleared:
        return False,'invalid_cleared_partition'
    if certificate.get('kind')=='q4_sixteen_actual_successes':
        return len(cleared)==16,'sixteen_accepted_successes'
    if certificate.get('kind')!='q4_actual_directional_local_hull':
        return False,'forbidden_or_unknown_certificate_kind'
    unknown=set(range(1,21))-cleared
    if set(certificate.get('empty_channels',[]))!=unknown:
        return False,'invalid_empty_partition'
    checker=DirectionalCoverage(max_depth=13,time_budget=15.)
    for ch in sorted(unknown):
        observations=[e for e in events if e['path']=='/measure' and e['channel']==ch]
        if any(e['result']!='no_signal' for e in observations):
            return False,'discovered_source_uncleared'
        if not checker.prove([e['position'] for e in observations])['complete']:
            return False,'unproved_directional_gap_channel_'+str(ch)
    return True,'q4_verified_from_actual_feedback'

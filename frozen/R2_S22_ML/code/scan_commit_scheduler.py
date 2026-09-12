"""Rank one real planned scan ahead of an uncertain source commitment.

This is a route-order heuristic. Only an existing search task can be promoted;
all sites, hard regions, reception rules and exit certificates are untouched.
Information scores include their RF/switch cost and their no-signal branch.
"""
from geometry import minimum_circle
from routing import route_length


def choose_scan_before_commit(current,tasks,points,order,regions,measured,information,options):
    if (not options.get('scan_before_commit') or not options.get('shared_bearing')
        or options.get('task_route') or len(order)<2 or tasks[order[0]][0]!='source'):
        return None
    target=tasks[order[0]][1]
    if minimum_circle(regions[target])[1]<=20:return None
    rank=next((i for i in range(1,len(order)) if tasks[order[i]][0]=='scan'),None)
    if rank is None:return None
    promoted=order[rank];site=points[promoted]
    if (target,tuple(site)) in measured:return None
    limit=max(0,int(options.get('shared_limit_per_stop',3)))
    if not limit:return None
    # Forecast the current known-source priority list at that station. Newly
    # discovered sources may change it; only actual feedback drives execution.
    priority=[]
    for kind,ch in tasks:
        if kind!='source' or (ch,tuple(site)) in measured or minimum_circle(regions[ch])[1]<=20:continue
        value=information(ch,site)
        if value and value['estimated_gain_s']>options.get('shared_gain_s',10.):
            priority.append((value['estimated_gain_s'],ch,value))
    priority.sort(key=lambda item:(-item[0],item[1]))
    eligible=next((entry for entry in priority[:limit] if entry[1]==target),None)
    if eligible is None:return None
    proposed=[promoted]+[i for i in order if i!=promoted]
    movement_delta=(route_length(current,points,proposed)-route_length(current,points,order))/5
    # shared_information_value already subtracts the 5 s RF + 1 s switch.
    net=eligible[0]-movement_delta
    if net<=1e-6:return None
    return dict(task_index=promoted,target_channel=target,scan_point=tuple(site),
                original_scan_order_position=rank,original_order=list(order),proposed_order=proposed,
                planned_move_change_s=movement_delta,expected_information_gain_s=eligible[0],
                expected_net_gain_s=net,predicted_target_branches=eligible[2]['branches'],
                predicted_shared_channels=[entry[1] for entry in priority[:limit]],
                information_model_count=eligible[2]['model_count'],existing_search_task_only=True,
                actual_future_feedback_required=True,hard_regions_unchanged=True)

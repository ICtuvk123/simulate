"""Select an explicit experimental policy; never load the scene generator."""
from time_policy import TimePolicy


def policy_class(kind):
    if kind == 'Gplus':
        return TimePolicy
    if kind == 'Optical':
        from optical_policy import OpticalPolicy
        return OpticalPolicy
    if kind == 'Future':
        from future_policy import FuturePolicy
        return FuturePolicy
    if kind == 'Route':
        from route_policy import RouteOrderPolicy
        return RouteOrderPolicy
    if kind == 'OpticalRoute':
        from optical_policy import OpticalPolicy
        from route_policy import RouteOrderPolicy
        class OpticalRoutePolicy(OpticalPolicy, RouteOrderPolicy):
            pass
        return OpticalRoutePolicy
    if kind == 'Combined':
        from optical_policy import OpticalPolicy
        from future_policy import FuturePolicy
        class CombinedPolicy(OpticalPolicy, FuturePolicy):
            pass
        return CombinedPolicy
    raise ValueError('Unknown policy kind: ' + str(kind))

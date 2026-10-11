"""Price tickets by their entry/exit stops, with explicit interchange policy."""
from ..graph.adapter import DataUnavailable
from ..graph.build import service_key


def path_fares(path, fares, network, profile=None):
    """Return one charge per ticket, allocated to its first traversal.

    A grouped OD tariff covers consecutive lines in the same paid journey.
    Walking ends that ticket unless it is an explicitly allowed interchange
    completed before its time limit. Other transport always ends the ticket.
    """
    amounts = [0.0] * len(path)
    index, previous_group = 0, None
    while index < len(path):
        step = path[index]
        if step.edge.mode == 'WALK':
            index += 1
            continue
        tariff = fares[step.edge.line]
        matrix = tariff.get('od_fares')
        if matrix is not None:
            end = index
            group = tariff['group']
            while end + 1 < len(path):
                following = path[end + 1]
                if following.edge.mode == 'WALK':
                    if end + 2 >= len(path):
                        break
                    after = path[end + 2]
                    transfer = next((link for link in tariff.get('interchanges', ())
                                     if link['from'] == following.edge.source
                                     and link['to'] == following.edge.target), None)
                    if (not transfer or after.edge.mode == 'WALK'
                            or fares[after.edge.line]['group'] != group
                            or (after.depart - path[end].arrive).total_seconds() > transfer['max_s']):
                        break
                    end += 2
                elif ((group is not None and fares[following.edge.line]['group'] == group)
                      or (group is None and following.edge.line == step.edge.line and not following.boarding)):
                    end += 1
                else:
                    break
            origin, destination = step.edge.source, path[end].edge.target
            try:
                amounts[index] = matrix[origin][destination]
            except KeyError as exc:
                raise DataUnavailable(f'Missing fare for {origin} -> {destination}') from exc
            index = end + 1
            previous_group = None
            continue
        if step.boarding:
            schedule = tariff.get('fares_by_service_day')
            if schedule:
                deck = 'lower' if (profile or {}).get('mobility') == 'wheelchair' else 'upper'
                amounts[index] = schedule[service_key(step.depart, network.holidays)][deck]
            elif tariff['group'] is None or tariff['group'] != previous_group:
                amounts[index] = tariff['fare_hkd']
            previous_group = tariff['group']
        index += 1
    return amounts

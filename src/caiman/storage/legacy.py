"""Read adapters only. Historical object bytes and their digests never change."""
from copy import deepcopy
from caiman.documents.models import valid_identifier


def manifest_view(data):
    """Translate legacy routing/labels into the current in-memory shape."""
    result = deepcopy(data)
    if not isinstance(result, dict):
        return result
    if 'labels' in result:
        labels = result.pop('labels')
        if (not isinstance(labels, dict) or set(labels) != {'public', 'compartments'} or
            type(labels['public']) is not bool or not isinstance(labels['compartments'], list) or
            (labels['public'] and labels['compartments']) or
            (not labels['public'] and len(labels['compartments']) != 1) or
            any(not valid_identifier(p) or p == 'public' for p in labels['compartments'])):
            raise ValueError('Invalid legacy document labels; choose a pod and re-ingest')
    result.pop('compartments', None)
    def routes(value):
        if isinstance(value, list):
            return [routes(v) for v in value]
        if isinstance(value, dict):
            if 'pod' in value and 'compartment' in value:
                raise ValueError('Conflicting legacy and current pod routes')
            return {('pod' if k == 'compartment' else k): routes(v) for k, v in value.items()}
        return value
    return routes(result)

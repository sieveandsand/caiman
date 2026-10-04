"""Read adapters only. Historical object bytes and their digests never change."""
from copy import deepcopy
from caiman.documents.models import is_schema, valid_identifier


def retire_converter_fields(manifest):
    """Hide retired provenance in a copied view, preserving stored object bytes."""
    converter = manifest.get('converter')
    if isinstance(converter, dict):
        converter.pop('version', None)
        converter.pop('hosted', None)
        if not converter:
            manifest.pop('converter', None)


def manifest_view(data):
    """Translate legacy routing/labels into the current in-memory shape."""
    result = deepcopy(data)
    if not isinstance(result, dict):
        return result
    if is_schema('document', result.get('schema')):
        # Retired document metadata is hidden in memory; stored bytes and pins stay intact.
        result.pop('structure', None)
        result.pop('requirements', None)
        retire_converter_fields(result)
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

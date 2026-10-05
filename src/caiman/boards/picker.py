"""Select explicit board versions for a project draft."""

from caiman.ui.picker import RecordPicker


def board_pin(record):
    return {key: record[key] for key in ('name', 'version', 'pod', 'digest')}


class BoardPicker(RecordPicker):
    noun = 'boards'
    container_id = 'board-picker'
    list_id = 'picker-boards'
    search_placeholder = 'Search board name, version, vendor, or pod'

    def __init__(self, **kwargs):
        kwargs.setdefault('empty_message', 'No unattached boards. Register boards from the Boards page first.')
        super().__init__(**kwargs)

    def record_label(self, record):
        return f"{record['name']} · {record['version']} · {record.get('pod_name', record['pod'])}"

    def record_sort_key(self, record):
        # Group names and pods; opaque versions retain catalog discovery order.
        return record['name'].casefold(), record['pod'].casefold()

    def record_details(self, record):
        manifest = record['manifest']
        return ' · '.join(str(manifest[k]) for k in ('vendor', 'notes') if manifest.get(k))

    def load_records(self):
        if self.service is None:
            raise ValueError('Board library is unavailable in this editor.')
        pods = self.service.store.pods
        allowed = pods.reference_pods(self.owner or 'public')
        records = self.service.list_configs('board', pods=allowed)
        existing = set()
        for pin in self.attached:
            try:
                locations = {pods.resolve(pin['pod'])['id']} if pin.get('pod') else allowed
            except (OSError, ValueError):
                continue
            matches = [r for r in records if r['pod'] in locations and
                       r['name'] == pin.get('name') and r['version'] == pin.get('version') and
                       (not pin.get('digest') or r['digest'] == pin['digest'])]
            # Unresolved or ambiguous drafts remain available for review validation.
            if len(matches) == 1:
                existing.add((matches[0]['pod'], matches[0]['digest']))
        return [r for r in records if (r['pod'], r['digest']) not in existing]

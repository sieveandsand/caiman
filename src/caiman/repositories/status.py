"""Compact pod status rows for the landing page."""

from rich.text import Text
from textual.widgets import ListItem, Static


class PodStatusRow(ListItem):
    def __init__(self, record, *, index):
        self.record = record
        text = Text(record['name'], style='bold #eef3e6')
        if record['default']:
            text.append('  [default]', style='#7fdc4f')
        color = {'clean': '#7fdc4f', 'changed': '#e6be72',
                 'conflict': '#e69a89', 'error': '#e69a89'}.get(record['git_state'], '#aab69c')
        text.append('  ·  ' + record.get('working_tree', record['status']), style=color)
        if record['branch']:
            text.append('  ·  ' + record['branch'], style='#aab69c')
        if record.get('publication'):
            publication = record['publication']
            color = '#aab69c' if publication in {'Local only', 'Published at last check'} else '#e6be72'
            text.append('  ·  ' + publication, style=color)
        text.append('\nRemote: ' + (record['remote'] or 'Not connected'), style='#8d9982')
        super().__init__(Static(text), id=f'pod-status-{index}')
        self.tooltip = f"{record['pod']}\n{record['path']}"

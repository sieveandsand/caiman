"""Shared quiet terminal appearance for Caiman's authoring forms.

The palette is a caiman's own: a pure black canvas, bright green accents like
the animal's hide in sunlight, and pale reed-coloured text.
"""

from textual.app import App
from textual.theme import Theme

TERMINAL_CSS = """
Screen { layout: vertical; background: #000000; color: #dfe6d3; }
#brand { height: 2; padding: 0 2; color: #7fdc4f; text-style: bold; }
#body { height: 1fr; padding: 0 2; }
#step-title { height: auto; color: #aab69c; margin-bottom: 1; }
.step { height: auto; }
Label { height: auto; margin: 1 0 0 0; color: #dfe6d3; }
.hint { height: auto; color: #8d9982; }
.error { height: auto; color: #e69a89; }
.key-hint { height: auto; padding: 0 2; color: #aab69c; }
Input { height: 3; margin: 0; padding: 0 1; background: #0c140c; border: round #5f7055; }
Input:focus { background: #102210; border: round #7fdc4f; }
Input:disabled { background: #0a0a0a; border: round #33422e; }
Select { height: 3; margin: 0; }
SelectCurrent { height: 3; padding: 0 1; background: #0c140c; border: round #5f7055; }
Select:focus > SelectCurrent { background: #102210; border: round #7fdc4f; }
TextArea { background: #0c140c; border: round #5f7055; height: 12; margin: 0; }
TextArea:focus { background: #102210; border: round #7fdc4f; }
Collapsible { background: #000000; border: none; padding: 0; }
CollapsibleTitle { color: #aab69c; }
#navigation { height: 4; padding: 0 2; border-top: solid #33422e; }
Button { min-width: 10; height: 3; margin-right: 1; border: none; background: #000000; color: #aab69c; }
Button.-primary { background: #000000; color: #7fdc4f; text-style: bold; }
Button:hover, Button:focus { background: #25331f; color: #eef3e6; }
Button:focus { text-style: bold; background-tint: transparent; }
Button:disabled { color: #56604e; background: #000000; }
#review, #status { height: auto; }
#status { max-height: 6; padding: 0 2; color: #cbd4bf; }
"""


def apply_theme(app: App) -> None:
    app.register_theme(Theme(
        name="caiman-terminal", primary="#7fdc4f", secondary="#aab69c",
        accent="#7fdc4f", foreground="#dfe6d3", background="#000000",
        surface="#000000", panel="#0c140c", error="#e69a89", dark=True,
    ))
    app.theme = "caiman-terminal"

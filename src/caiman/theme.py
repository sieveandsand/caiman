"""Shared quiet terminal appearance for Caiman's authoring forms."""

from textual.app import App
from textual.theme import Theme


TERMINAL_CSS = """
Screen { layout: vertical; background: #000000; color: #e6e1d8; }
#brand { height: 2; padding: 0 2; color: #d97757; text-style: bold; }
#body { height: 1fr; padding: 0 2; }
#step-title { height: auto; color: #b4afa7; margin-bottom: 1; }
.step { height: auto; }
Label { height: auto; margin: 1 0 0 0; color: #e6e1d8; }
.hint { height: auto; color: #99958e; }
.error { height: auto; color: #e69a89; }
.key-hint { height: auto; padding: 0 2; color: #b4afa7; }
Input { height: 3; margin: 0; padding: 0 1; background: #101010; border: round #80786e; }
Input:focus { background: #18120f; border: round #d97757; }
Input:disabled { background: #0a0a0a; border: round #49453f; }
Select { height: 3; margin: 0; }
SelectCurrent { height: 3; padding: 0 1; background: #101010; border: round #80786e; }
Select:focus > SelectCurrent { background: #18120f; border: round #d97757; }
TextArea { background: #101010; border: round #80786e; height: 12; margin: 0; }
TextArea:focus { background: #18120f; border: round #d97757; }
Collapsible { background: #000000; border: none; padding: 0; }
CollapsibleTitle { color: #b4afa7; }
#navigation { height: 4; padding: 0 2; border-top: solid #49453f; }
Button { min-width: 10; height: 3; margin-right: 1; border: none; background: #000000; color: #b4afa7; }
Button.-primary { background: #000000; color: #d97757; text-style: bold; }
Button:hover, Button:focus { background: #34302b; color: #eee8df; }
Button:focus { text-style: bold; background-tint: transparent; }
Button:disabled { color: #615d57; background: #000000; }
#review, #status { height: auto; }
#status { max-height: 6; padding: 0 2; color: #d4cfc6; }
Footer { background: #000000; color: #99958e; }
FooterKey > .footer-key--key { background: #000000; color: #d97757; }
FooterKey > .footer-key--description { background: #000000; color: #99958e; }
"""


def apply_theme(app: App) -> None:
    app.register_theme(Theme(
        name="caiman-terminal", primary="#d97757", secondary="#b4afa7",
        accent="#d97757", foreground="#e6e1d8", background="#000000",
        surface="#000000", panel="#101010", error="#e69a89", dark=True,
    ))
    app.theme = "caiman-terminal"

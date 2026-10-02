"""Board and project authoring over the same drafts used by config files."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path

from textual.app import ComposeResult
from caiman.ui.navigation import NavigationApp
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Static, TextArea

from caiman.configurations.files import template, unique_keys
from caiman.configurations.service import ConfigurationService
from caiman.configurations.models import (restate_project_draft, part_aliases, part_identity, project_boards,
                                          project_is_legacy, realized_parts)
from caiman.documents.models import ValidationError
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class ConfigApp(NavigationApp):
    """Edit a configuration draft, resolve its pins, review, and register locally."""

    TITLE = "Caiman · Author configuration"
    CSS = TERMINAL_CSS + """
    #catalog { height: 14; }
    #resolved { height: 20; }
    #catalog-status { height: auto; }
    """

    def __init__(self, kind: str, store_root: Path, draft: dict | None = None):
        super().__init__()
        if kind not in {"board", "project"}:
            raise ValueError("Configuration kind must be board or project")
        apply_theme(self)
        self.kind = kind
        self.store_root = store_root
        self.draft = deepcopy(template(kind) if draft is None else draft)
        if not isinstance(self.draft, dict):
            raise ValidationError({"draft": "Configuration must be a JSON object."})
        if kind == "project":
            if project_is_legacy(self.draft) and not isinstance(self.draft.get("board", {}), dict):
                raise ValidationError({"board": "Expected an object with name and version. Correct the imported configuration file."})
            # A v1 draft (one board) is restated with its board spelled out;
            # the review shows the rewrite before anything is registered.
            self.draft = restate_project_draft(self.draft)
            if not isinstance(self.draft.get("boards", []), list):
                raise ValidationError({"boards": "Expected an array of board pins. Correct the imported configuration file."})
            compartments = self.draft.get("compartments", [])
            if not isinstance(compartments, list) or not all(isinstance(name, str) for name in compartments):
                raise ValidationError({"compartments": "Expected an array of names. Correct the imported configuration file."})
        self.service = ConfigurationService(Store(store_root))
        self.prepared = None
        self.registration = None
        self.reviewing = False
        self.busy = False
        self.saving = False
        self._last_view = None

    @property
    def collections(self) -> tuple[str, ...]:
        return ("documents", "parts", "links") if self.kind == "board" else ("boards", "documents", "features")

    def field(self, key: str, label: str, value=None) -> ComposeResult:
        yield Label(label)
        initial = self.draft.get(key, "") if value is None else value
        yield Input(value=str(initial), id=key)
        yield Static("", id=f"error-{key}", classes="error", markup=False)

    def compose(self) -> ComposeResult:
        yield Static(f"caiman  /  author {self.kind}", id="brand")
        with VerticalScroll(id="body"):
            yield Static("1 / 2 · Edit draft", id="step-title")
            with VerticalScroll(id="edit", classes="step"):
                yield Static("Edit these fields here or import an editable JSON configuration file.", classes="hint")
                yield from self.field(self.kind, "Board name" if self.kind == "board" else "Program codename")
                yield from self.field("version", "Version (an exact label)")
                yield from self.field("derives_from", "Derived from version (optional)")
                yield from self.field("relation", "Reason for this relationship (required when deriving)")
                if self.kind == "project":
                    yield from self.field("customer", "Customer identity (private project information)")
                    compartments = self.draft.get("compartments", [])
                    compartment_text = ", ".join(compartments)
                    yield from self.field("compartments", "Compartments (comma separated; required)", compartment_text)
                    yield Static("Usually one per customer, such as oem-alpha. A project must include every compartment required by a document to use it.", classes="hint")
                    yield from self.field("spec_set", "Specification set")
                else:
                    yield from self.field("vendor", "Board vendor (required only for board-level documents)")
                    yield from self.field("notes", "Notes (optional, unstructured; nothing parses them)")
                    yield Static("Board manifests are public. Keep customer information in projects.", classes="hint")
                with Collapsible(title="Registered document catalog · copy exact pins", collapsed=True):
                    yield Static("Refresh to list public documents" + (" and documents in the compartments entered above." if self.kind == "project" else "."), classes="hint")
                    yield Button("Refresh catalog", id="refresh-catalog")
                    yield Static("", id="catalog-status", markup=False)
                    yield TextArea("", read_only=True, id="catalog", soft_wrap=True)
                for key in self.collections:
                    yield Label(f"{key.capitalize()} · JSON array")
                    yield Static(self.collection_hint(key), classes="hint", markup=False)
                    yield TextArea(json.dumps(self.draft.get(key, []), indent=2, ensure_ascii=False), id=key, show_line_numbers=True, soft_wrap=True, tab_behavior="focus")
                    yield Static("", id=f"error-{key}", classes="error", markup=False)
            with VerticalScroll(id="review-pane", classes="step"):
                yield Static("", id="review", markup=False)
                with Collapsible(title="Complete resolved configuration", collapsed=True):
                    yield TextArea("", read_only=True, id="resolved", show_line_numbers=True, soft_wrap=True)
        yield Static("", id="status", markup=False)
        with Horizontal(id="navigation"):
            yield Button("Back to edit", id="back")
            yield Button("Review", id="next", variant="primary")
            yield Button("Cancel", id="cancel")
        yield self.navigation_hint()

    def collection_hint(self, key: str) -> str:
        if self.kind == "board" and key == "documents":
            return 'Documents about the assembly itself, issued by the board vendor: {"ref": "…", "digest": "sha256:…", "notes": "why it is pinned"}.'
        return {
            "parts": 'Each part has role, vendor, part, and documents. A document pin uses {"ref": "…", "digest": "sha256:…"}. Optional: silicon_revision, aliases, notes.',
            "links": 'Declare links between part roles: {"name": "bus", "between": ["mcu.SPI1", "sensor.SPI"], "notes": "why it exists"}.',
            "documents": 'Reuse catalog pins: {"ref": "…", "digest": "sha256:…"}. Exact references are pinned during review.',
            "boards": 'Pin each board version the program uses: {"name": "falcon-main", "version": "B"}. A board may appear at several versions. A blank digest pins the exact version during review.',
            "features": 'Declare scope as required or not-used. Include governed_by, related, and realized_on parts as {"board": "…", "version": "…", "role": "…"}.',
        }[key]

    def on_mount(self) -> None:
        self.show_view()

    def show_view(self) -> None:
        self.query_one("#edit").display = not self.reviewing
        self.query_one("#review-pane").display = self.reviewing
        self.query_one("#step-title", Static).update("2 / 2 · Review and register" if self.reviewing else "1 / 2 · Edit draft")
        for widget in self.query("Input, TextArea"):
            widget.disabled = self.busy or self.registration is not None
        self.query_one("#back", Button).disabled = not self.reviewing or self.busy or self.registration is not None
        self.query_one("#next", Button).label = "Register" if self.reviewing else "Review"
        self.query_one("#next", Button).disabled = self.busy or self.registration is not None
        self.query_one("#refresh-catalog", Button).disabled = self.busy or self.registration is not None
        self.query_one("#cancel", Button).disabled = self.saving
        if self._last_view != self.reviewing:
            self._last_view = self.reviewing
            self.query_one("#body", VerticalScroll).scroll_home(animate=False)
            self.call_after_refresh(self.query_one("#next" if self.reviewing else f"#{self.kind}").focus)

    def value(self, key: str) -> str:
        return self.query_one(f"#{key}", Input).value.strip()

    def collect_draft(self) -> dict:
        data = deepcopy(self.draft)
        optional = ("vendor", "notes") if self.kind == "board" else ()
        for key in (self.kind, "version", "derives_from", "relation", *optional):
            value = self.value(key)
            if value or key in {self.kind, "version"}:
                data[key] = value
            else:
                data.pop(key, None)
        if self.kind == "project":
            data.update(customer=self.value("customer"), compartments=self.compartments(), spec_set=self.value("spec_set"))
        errors = {}
        for key in self.collections:
            try:
                data[key] = json.loads(self.query_one(f"#{key}", TextArea).text, object_pairs_hook=unique_keys)
                if not isinstance(data[key], list):
                    errors[key] = "Enter a JSON array, starting with [."
            except json.JSONDecodeError as error:
                errors[key] = f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
            except ValueError as error:
                errors[key] = str(error)
        if errors:
            raise ValidationError(errors)
        return data

    def compartments(self) -> list[str]:
        if self.kind == "board":
            return []
        return [name.strip() for name in self.value("compartments").split(",") if name.strip()]

    def show_errors(self, errors: dict[str, str]) -> None:
        first = None
        fields = {widget.id.removeprefix("error-"): widget for widget in self.query(".error")}
        for field, message in errors.items():
            target = field.split(".", 1)[0].split("[", 1)[0]
            if target in fields:
                widget = fields[target]
                previous = str(widget.content) if widget.content else ""
                widget.update(f"{previous}\n{field}: {message}".strip())
                if first is None:
                    first = widget
        self.query_one("#status", Static).update("Please correct the marked fields.\n" + "\n".join(f"{field}: {message}" for field, message in errors.items()))
        if first is not None:
            first.scroll_visible(animate=False)

    def review_text(self) -> str:
        manifest = self.prepared.manifest
        lines = [f"{self.kind.capitalize()}: {manifest[self.kind]}", f"Version: {manifest['version']}"]
        if self.kind == "board":
            lines.extend(["Access: public", f"Vendor: {manifest.get('vendor', 'not declared')}",
                          f"Notes: {manifest.get('notes', 'none')}",
                          f"Board documents: {len(manifest.get('documents', []))}",
                          f"Parts: {len(manifest.get('parts', []))}", f"Links: {len(manifest.get('links', []))}"])
            for part in manifest.get("parts", []):
                aliases = ", ".join(f"{key} {value}" for key, value in sorted(part_aliases(part).items()))
                lines.append(f"  {part['role']}: {part_identity(part)} · silicon {part.get('silicon_revision', 'unknown')} · aliases {aliases or 'none'}")
            for link in manifest.get("links", []):
                endpoints = " ↔ ".join(link["between"]) if "between" in link else f"{link['from']} → {link['to']}"
                lines.append(f"  Link {link['name']}: {endpoints}")
        else:
            lines.extend([f"Customer: {manifest['customer']}", "Compartments: " + ", ".join(manifest["compartments"])])
            for board in project_boards(manifest):
                lines.extend([f"Board: {board['name']} @ {board['version']}", f"  Board digest: {board['digest']}"])
            lines.extend([
                f"Specification set: {manifest.get('spec_set', '')}",
                f"Documents: {len(manifest.get('documents', []))}",
                f"Features: {len(manifest.get('features', []))}",
            ])
            for feature in manifest.get("features", []):
                lines.append(f"  {feature['name']}: {feature['scope']}")
                for board, version, role in realized_parts(manifest, feature):
                    lines.append(f"    Realized on: {role} · {board} @ {version}")
                for selector in feature.get("governed_by", []):
                    lines.append(f"    Governed by: {selector.get('ref', selector['digest'])}")
                    if selector.get("requirements"):
                        lines.append("    Requirements: " + ", ".join(selector["requirements"]))
                for relationship in feature.get("related", []):
                    lines.append(f"    Related to {relationship['feature']}: {relationship['relation']}")
        if manifest.get("derives_from"):
            lines.extend([f"Derived from: {manifest['derives_from']}", f"Relationship: {manifest.get('relation', '')}"])
        pins = list(manifest.get("documents", []))
        if self.kind == "board":
            pins += [pin for part in manifest.get("parts", []) for pin in part.get("documents", [])]
        lines.extend(["", "Pinned documents"])
        lines.extend(f"{pin.get('ref', 'Selected by digest')} [{pin['compartment']}]\n  {pin['digest']}" for pin in pins)
        if not pins:
            lines.append("None")
        lines.extend(["", f"Store: {self.store_root.expanduser().absolute()}", f"Manifest digest: {self.prepared.digest}", "", "Register saves this reviewed version locally."])
        return "\n".join(lines)

    def action_cancel(self) -> None:
        if not self.saving:
            self.exit()

    async def action_review(self) -> None:
        if not self.reviewing and not self.busy and self.registration is None:
            await self.advance()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "cancel":
            self.action_cancel()
        elif not self.busy and self.registration is None:
            if action == "back":
                self.prepared = None
                self.reviewing = False
                self.show_view()
            elif action == "next":
                await self.advance()
            elif action == "refresh-catalog":
                await self.refresh_catalog()

    async def refresh_catalog(self) -> None:
        self.busy = True
        self.show_view()
        try:
            entries = await asyncio.to_thread(self.service.list_documents, compartments=self.compartments())
            pins = [{key: entry[key] for key in ("ref", "digest", "compartment")} for entry in entries]
            self.query_one("#catalog", TextArea).load_text(json.dumps(pins, indent=2, ensure_ascii=False))
            self.query_one("#catalog-status", Static).update(f"{len(entries)} registered documents. Copy ref and digest into a document pin.")
        except (OSError, ValueError) as error:
            self.query_one("#catalog-status", Static).update(str(error))
        finally:
            self.busy = False
            self.show_view()

    async def advance(self) -> None:
        for widget in self.query(".error"):
            widget.update("")
        self.query_one("#status", Static).update("")
        self.busy = True
        self.saving = self.reviewing
        self.show_view()
        try:
            if self.reviewing:
                self.registration = await asyncio.to_thread(self.service.register, self.prepared)
                refs = "\n".join(str(path) for path in self.registration.ref_paths)
                self.query_one("#status", Static).update(f"Registered locally.\nManifest: {self.registration.digest}\nRefs:\n{refs}")
                self.query_one("#cancel", Button).label = "Close"
            else:
                draft = self.collect_draft()
                self.prepared = await asyncio.to_thread(self.service.prepare, self.kind, draft)
                self.query_one("#review", Static).update(self.review_text())
                self.query_one("#resolved", TextArea).load_text(json.dumps(self.prepared.manifest, indent=2, ensure_ascii=False))
                self.reviewing = True
        except ValidationError as error:
            self.show_errors(error.errors)
        except (OSError, ValueError) as error:
            self.query_one("#status", Static).update(str(error))
        finally:
            self.busy = False
            self.saving = False
            self.show_view()

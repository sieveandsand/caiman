"""Interactive document registration, backed by the shared ingestion API."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

from textual.app import ComposeResult
from caiman.navigation import NavigationApp
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Select, Static

from caiman.ingest import PreparedDocument, ValidationError, prepare_document, validate_headings
from caiman.config_store import ConfigurationService
from caiman.store import Store
from caiman.theme import TERMINAL_CSS, apply_theme


class IngestApp(NavigationApp):
    """Four-step form. Preparing and reviewing never writes to the store."""

    TITLE = "Caiman · Register document"
    CSS = TERMINAL_CSS

    def __init__(self, store_root: Path, source_path: Path | None = None, *, state: dict | None = None, context: dict | None = None, authorized_compartments=()):
        super().__init__()
        apply_theme(self)
        self.store_root = store_root
        self.source_path = source_path
        self.step = 0
        self.prepared: PreparedDocument | None = None
        self.busy = False
        self.registered = False
        self._shown_step = None
        self.saved_state = state or {}
        self.context = deepcopy(context or {})
        self.service = ConfigurationService(Store(store_root))
        self.boards = []
        self.projects = []
        self.selected_board = None
        self._restoring = True
        self._identity_mode = "manual"
        self.authorized_compartments = set(authorized_compartments)

    def field(self, name: str, label: str, value: str = "") -> ComposeResult:
        yield Label(label)
        yield Input(value=value, id=name)
        yield Static("", id=f"error-{name}", classes="error", markup=False)

    def compose(self) -> ComposeResult:
        yield Static("caiman  /  ingest document", id="brand")
        with VerticalScroll(id="body"):
            yield Static("1 / 4 · File", id="step-title")
            with VerticalScroll(id="step-0", classes="step"):
                yield from self.field("file", "Markdown file", str(self.source_path or ""))
                yield Static("", id="file-result", markup=False)
            with VerticalScroll(id="step-1", classes="step"):
                yield Label("Document identity")
                yield Select([("Enter manually", "manual"), ("Use a board part", "board"), ("Use a project", "project")], value="manual", allow_blank=False, id="identity_source")
                with VerticalScroll(id="board-context", classes="step"):
                    yield Label("Registered board version")
                    yield Select([], prompt="Select a board", id="board_choice")
                    yield Label("Part on this board")
                    yield Select([], prompt="Select a part", id="board_part")
                    yield Button("Create board", id="create-board")
                with VerticalScroll(id="project-context", classes="step"):
                    yield from self.field("project_scope", "Compartments to search (comma separated)")
                    yield Static("Usually one per customer, such as oem-alpha. Only projects in these compartments are listed.", classes="hint")
                    yield Button("Find projects", id="find-projects")
                    yield Select([], prompt="Select a project version", id="project_choice")
                    yield Button("Create project", id="create-project")
                yield Static("", id="context-status", classes="hint", markup=False)
                yield Static("Selections fill document metadata. Registration does not add a document to an existing board or project.", classes="hint")
                yield from self.field("issuer", "Issuer")
                yield from self.field("part", "Part (fill either part or program)")
                yield from self.field("program", "Program")
                yield from self.field("doc_type", "Document type")
                yield from self.field("version", "Document version")
                yield Label("Structure")
                yield Select([("Prose", "prose"), ("Requirements", "requirement")], value="prose", allow_blank=False, id="structure")
                with VerticalScroll(id="requirements-fields", classes="step"):
                    yield from self.field("pattern", "Requirement ID pattern")
                yield from self.field("silicon_revisions", "Silicon revisions (comma separated; optional)")
                yield Label("Access — choose explicitly")
                yield Select([("Public", "public"), ("Private — compartments", "compartments")], prompt="Choose access", id="visibility")
                yield Static("", id="error-labels", classes="error", markup=False)
                with VerticalScroll(id="compartment-fields", classes="step"):
                    yield from self.field("compartments", "Compartments (comma separated)")
                    yield Static("Usually one per customer, such as oem-alpha. A project needs every compartment listed here to use this document.", classes="hint")
            with VerticalScroll(id="step-2", classes="step"):
                yield Static("Provenance is optional. Continue to skip; missing information remains unknown.")
                with Collapsible(title="Original source and converter", collapsed=True):
                    yield from self.field("source_sha256", "Original source SHA-256 (optional)")
                    yield from self.field("source_pages", "Original source page count (optional)")
                    yield from self.field("converter_name", "Converter name (optional)")
                    yield from self.field("converter_version", "Converter version (optional)")
                    yield Label("Conversion location (optional)")
                    yield Select([("Unknown", "unknown"), ("Local", "local"), ("Hosted", "hosted")], value="unknown", allow_blank=False, id="hosted")
            with VerticalScroll(id="step-3", classes="step"):
                yield Static("", id="review", markup=False)
        yield Static("", id="status", markup=False)
        with Horizontal(id="navigation"):
            yield Button("Back", id="back")
            yield Button("Continue", id="next", variant="primary")
            yield Button("Cancel", id="cancel")
        yield self.navigation_hint()

    async def on_mount(self) -> None:
        self.query_one("#project_scope", Input).value = ", ".join(sorted(self.authorized_compartments))
        for key, value in self.saved_state.get("inputs", {}).items():
            matches = self.query(f"#{key}")
            if matches:
                matches.first(Input).value = value
        for key, value in self.saved_state.get("selects", {}).items():
            if key not in {"board_choice", "board_part", "project_choice"}:
                self.query_one(f"#{key}", Select).value = Select.NULL if value is None else value
        self.step = min(self.saved_state.get("step", 0), 2)
        previous_context = self.saved_state.get("context", {})
        if "project" in self.context and self.context["project"]["digest"] != previous_context.get("project", {}).get("digest"):
            await self.apply_project(self.context["project"], update_board=bool(self.saved_state) or "board" not in self.context)
            self.query_one("#identity_source", Select).value = "project"
        elif "board" in self.context and self.context["board"]["digest"] != previous_context.get("board", {}).get("digest"):
            self.select_board(self.context["board"])
            self.query_one("#identity_source", Select).value = "board"
        self._identity_mode = self.query_one("#identity_source", Select).value
        await self.find_boards()
        if self.value("project_scope"):
            await self.find_projects()
        if "board" in self.context:
            record = self.context["board"]
            self.select_board(record, clear=False)
            for index, option in enumerate(self.boards):
                if option["digest"] == record["digest"]:
                    self.query_one("#board_choice", Select).value = str(index)
            identity = self.value("issuer") + "/" + self.value("part")
            for index, part in enumerate(record["manifest"]["parts"]):
                if part["part"] == identity:
                    self.query_one("#board_part", Select).value = str(index)
                    break
        if "project" in self.context:
            for index, option in enumerate(self.projects):
                if option["digest"] == self.context["project"]["digest"]:
                    self.query_one("#project_choice", Select).value = str(index)
            if self._identity_mode == "project":
                self.project_hint(self.context["project"]["manifest"])
        if self._identity_mode == "manual":
            self.query_one("#context-status", Static).update("Enter the document publisher and either a part or program below.")
        self.show_step()
        self.call_after_refresh(self.finish_restore)

    def finish_restore(self) -> None:
        self._restoring = False

    def show_step(self) -> None:
        for widget in self.query("Input, Select"):
            widget.disabled = self.busy or self.registered
        for index in range(4):
            self.query_one(f"#step-{index}").display = self.step == index
        self.query_one("#requirements-fields").display = self.query_one("#structure", Select).value == "requirement"
        self.query_one("#compartment-fields").display = self.query_one("#visibility", Select).value == "compartments"
        source = self.query_one("#identity_source", Select).value
        self.query_one("#board-context").display = source == "board"
        self.query_one("#project-context").display = source == "project"
        for button in ("create-board", "create-project", "find-projects"):
            self.query_one(f"#{button}", Button).disabled = self.busy or self.registered
        self.query_one("#step-title", Static).update(f"{self.step + 1} / 4 · {('File', 'Document', 'Optional provenance', 'Review and register')[self.step]}")
        self.query_one("#back", Button).disabled = self.step == 0 or self.busy or self.registered
        self.query_one("#next", Button).label = "Register" if self.step == 3 else "Continue"
        self.query_one("#next", Button).disabled = self.busy or self.registered
        self.query_one("#cancel", Button).disabled = self.busy and self.step == 3
        if self._shown_step != self.step:
            self._shown_step = self.step
            self.query_one("#body", VerticalScroll).scroll_home(animate=False)
            target = ("#file", "#identity_source", "#next", "#next")[self.step]
            self.call_after_refresh(self.query_one(target).focus)

    async def on_select_changed(self, event: Select.Changed) -> None:
        if self._restoring or event.value != event.select.value:
            return
        if event.select.id in {"structure", "visibility"}:
            self.show_step()
        elif event.select.id == "identity_source":
            if self._identity_mode != event.value:
                self.clear_identity()
                self.query_one("#project_choice", Select).value = Select.NULL
                self.query_one("#board_choice", Select).value = Select.NULL
                self.query_one("#board_part", Select).value = Select.NULL
                self._identity_mode = event.value
            self.show_step()
            if event.value == "board":
                await self.find_boards()
            elif event.value == "manual":
                self.query_one("#context-status", Static).update("Enter the document publisher and either a part or program below.")
        elif event.select.id == "board_choice" and isinstance(event.value, str):
            self.select_board(self.boards[int(event.value)])
        elif event.select.id == "board_part" and isinstance(event.value, str) and self.selected_board is not None:
            part = self.selected_board["manifest"]["parts"][int(event.value)]
            issuer, name = part["part"].split("/", 1)
            self.query_one("#issuer", Input).value = issuer
            self.query_one("#part", Input).value = name
            self.query_one("#program", Input).value = ""
            self.query_one("#silicon_revisions", Input).value = part.get("silicon_revision", "")
            self.query_one("#visibility", Select).value = Select.NULL
            self.query_one("#compartments", Input).value = ""
            self.query_one("#context-status", Static).update(f"Using {part['role']} from {self.selected_board['manifest']['board']}. Confirm this document's access below.")
        elif event.select.id == "project_choice" and isinstance(event.value, str):
            await self.apply_project(self.projects[int(event.value)])

    def clear_identity(self) -> None:
        for field in ("issuer", "part", "program", "silicon_revisions", "compartments"):
            self.query_one(f"#{field}", Input).value = ""
        self.query_one("#visibility", Select).value = Select.NULL

    def select_board(self, record: dict, *, clear: bool = True) -> None:
        if clear:
            self.clear_identity()
        self.selected_board = record
        self.context["board"] = record
        parts = record["manifest"]["parts"]
        self.query_one("#board_part", Select).set_options([(f"{part['role']} · {part['part']}", str(index)) for index, part in enumerate(parts)])
        self.query_one("#context-status", Static).update(f"Board {record['manifest']['board']} @ {record['manifest']['version']}. Choose a part; access remains your explicit choice.")

    async def apply_project(self, record: dict, *, update_board: bool = True) -> None:
        manifest = record["manifest"]
        board_digest = manifest["board"]["digest"]
        board = await asyncio.to_thread(self.service.load_digest, "board", board_digest)
        if update_board:
            self.context["board"] = {"manifest": board, "digest": board_digest, "name": board["board"], "version": board["version"], "compartment": "public"}
        self.context["project"] = record
        self.query_one("#program", Input).value = manifest["project"]
        self.query_one("#part", Input).value = ""
        self.query_one("#issuer", Input).value = ""
        self.query_one("#silicon_revisions", Input).value = ""
        self.query_one("#compartments", Input).value = ", ".join(manifest["compartments"])
        scopes = set(self.csv("project_scope")) | set(manifest["compartments"])
        self.query_one("#project_scope", Input).value = ", ".join(sorted(scopes))
        self.query_one("#visibility", Select).value = Select.NULL
        self.project_hint(manifest)

    def project_hint(self, manifest: dict) -> None:
        self.query_one("#context-status", Static).update(
            f"Project {manifest['project']} @ {manifest['version']} · Customer: {manifest['customer']}\n"
            "Enter the document publisher identifier as issuer, then explicitly choose document access below."
        )

    async def find_boards(self) -> None:
        try:
            self.boards = await asyncio.to_thread(self.service.list_configs, "board")
            selected = self.context.get("board")
            if selected and not any(record["digest"] == selected["digest"] for record in self.boards):
                self.boards.append({**selected, "name": selected["manifest"]["board"], "version": selected["manifest"]["version"], "compartment": "public"})
            self.query_one("#board_choice", Select).set_options([(self.option_label(record), str(index)) for index, record in enumerate(self.boards)])
            if not self.boards:
                self.query_one("#context-status", Static).update("No registered boards yet. Create a board or enter the identity manually.")
        except (OSError, ValueError) as error:
            self.query_one("#context-status", Static).update(str(error))

    async def find_projects(self) -> None:
        try:
            scopes = set(self.csv("project_scope"))
            self.projects = await asyncio.to_thread(self.service.list_configs, "project", compartments=scopes)
            selected = self.context.get("project")
            if selected and set(selected["manifest"]["compartments"]) <= scopes and not any(record["digest"] == selected["digest"] for record in self.projects):
                self.projects.append({**selected, "name": selected["manifest"]["project"], "version": selected["manifest"]["version"], "compartment": selected["manifest"]["compartments"][0]})
            self.query_one("#project_choice", Select).set_options([(self.option_label(record), str(index)) for index, record in enumerate(self.projects)])
            self.query_one("#context-status", Static).update(f"{len(self.projects)} projects in the selected compartments.")
        except (OSError, ValueError) as error:
            self.query_one("#context-status", Static).update(str(error))

    @staticmethod
    def option_label(record: dict) -> str:
        return f"{record['name']} @ {record['version']} · {record['compartment']} · {record['digest'][7:15]}"

    def export_state(self) -> dict:
        return {
            "step": self.step,
            "inputs": {widget.id: widget.value for widget in self.query(Input)},
            "selects": {widget.id: widget.value if isinstance(widget.value, str) else None for widget in self.query(Select)},
            "context": deepcopy(self.context),
        }

    def value(self, name: str) -> str:
        return self.query_one(f"#{name}", Input).value.strip()

    def metadata(self) -> dict:
        data = {key: self.value(key) for key in ("issuer", "part", "program", "doc_type", "version") if self.value(key)}
        data["structure"] = self.query_one("#structure", Select).value
        visibility = self.query_one("#visibility", Select).value
        if visibility in {"public", "compartments"}:
            data["labels"] = {"public": visibility == "public", "compartments": self.csv("compartments") if visibility == "compartments" else []}
        if self.value("silicon_revisions"):
            data["silicon_revisions"] = self.csv("silicon_revisions")
        if data["structure"] == "requirement":
            data["requirements"] = {"pattern": self.value("pattern")}
        source = {}
        if self.value("source_sha256"):
            source["sha256"] = self.value("source_sha256")
        if self.value("source_pages"):
            try:
                source["pages"] = int(self.value("source_pages"))
            except ValueError:
                source["pages"] = self.value("source_pages")
        converter = {key: self.value(f"converter_{key}") for key in ("name", "version") if self.value(f"converter_{key}")}
        hosted = self.query_one("#hosted", Select).value
        if hosted != "unknown":
            converter["hosted"] = hosted == "hosted"
        if source:
            data["source"] = source
        if converter:
            data["converter"] = converter
        return data

    def csv(self, name: str) -> list[str]:
        return [item.strip() for item in self.value(name).split(",") if item.strip()]

    def review_text(self) -> str:
        assert self.prepared is not None
        manifest = self.prepared.manifest
        labels = manifest["labels"]
        source = manifest.get("source", {})
        converter = manifest.get("converter", {})
        access = "Public" if labels["public"] else "Compartments: " + ", ".join(labels["compartments"])
        hosted = {True: "Hosted", False: "Local"}.get(converter.get("hosted"), "Unknown")
        lines = [
            "Review before registering locally",
            f"File: {self.prepared.source_path.name}",
            f"Issuer: {manifest['issuer']}",
            f"{'Part' if 'part' in manifest else 'Program'}: {manifest.get('part', manifest.get('program'))}",
            f"Document type: {manifest['doc_type']}",
            f"Version: {manifest['version']}",
            f"Structure: {manifest['structure']}",
            f"Silicon revisions: {', '.join(manifest.get('silicon_revisions', [])) or 'Unknown / not applicable'}",
            f"Access: {access}",
        ]
        if manifest["structure"] == "requirement":
            lines.append(f"Requirement ID pattern: {manifest['requirements']['pattern']}")
        lines.extend([
            "", "Optional provenance",
            f"Original source checksum: {source.get('sha256', 'Unknown')}",
            f"Original source pages: {source.get('pages', 'Unknown')}",
            f"Converter name: {converter.get('name', 'Unknown')}",
            f"Converter version: {converter.get('version', 'Unknown')}",
            f"Conversion location: {hosted}",
            "", f"Store: {self.store_root.expanduser().absolute()}",
            f"Size: {len(self.prepared.content):,} bytes",
            f"Markdown digest: {self.prepared.blob_digest}",
            f"Manifest digest: {self.prepared.manifest_digest}",
        ])
        return "\n".join(lines)

    def errors(self, errors: dict[str, str]) -> None:
        aliases = {"headings": "file", "requirements.pattern": "pattern", "source.sha256": "source_sha256", "source.pages": "source_pages", "converter.name": "converter_name", "converter.version": "converter_version", "labels.compartments": "compartments", "labels.public": "labels"}
        for field, message in errors.items():
            target = aliases.get(field, field).replace(".", "_")
            matches = self.query(f"#error-{target}")
            if matches:
                matches.first(Static).update(message)
        self.query_one("#status", Static).update("\n".join(f"{field}: {message}" for field, message in errors.items()))

    def action_cancel(self) -> None:
        if not self.busy or self.step != 3:
            self.exit({"context": self.context})

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "cancel":
            self.action_cancel()
            return
        if self.busy or self.registered:
            return
        if action in {"create-board", "create-project"}:
            self.exit({"action": action, "ingest_state": self.export_state(), "context": self.context})
            return
        if action == "find-projects":
            await self.find_projects()
            return
        if action == "back":
            self.prepared = None
            self.step -= 1
            self.show_step()
            return
        if action != "next":
            return
        for widget in self.query(".error"):
            widget.update("")
        self.query_one("#status", Static).update("")
        self.busy = True
        self.show_step()
        try:
            if self.step == 0:
                path = Path(self.value("file")).expanduser()
                if not path.is_file():
                    self.errors({"file": "Select an existing Markdown file."})
                    return
                if path.suffix.lower() not in {".md", ".markdown"}:
                    self.errors({"file": "Select a Markdown file (.md or .markdown)."})
                    return
                headings = await asyncio.to_thread(lambda: validate_headings(path.read_bytes().decode("utf-8")))
                result = f"{path.name}: {len(headings)} usable headings"
                self.query_one("#file-result", Static).update(result)
                self.query_one("#status", Static).update(result)
                self.step = 1
            elif self.step in (1, 2):
                metadata = self.metadata()
                if self.step == 1:
                    metadata.pop("source", None)
                    metadata.pop("converter", None)
                self.prepared = await asyncio.to_thread(prepare_document, Path(self.value("file")).expanduser(), metadata)
                self.step += 1
                if self.step == 3:
                    self.query_one("#review", Static).update(self.review_text())
            else:
                assert self.prepared is not None
                registration = await asyncio.to_thread(Store(self.store_root).register, self.prepared)
                self.registered = True
                self.query_one("#status", Static).update(f"Registered locally.\nManifest: {registration.manifest_digest}\nRef: {registration.ref_path}")
                self.query_one("#cancel", Button).label = "Close"
        except ValidationError as exc:
            self.errors(exc.errors)
        except (OSError, UnicodeError, ValueError) as exc:
            self.query_one("#status", Static).update(str(exc))
        finally:
            self.busy = False
            self.show_step()

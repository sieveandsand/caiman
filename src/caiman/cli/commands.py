"""Command entry point; ingestion stays interactive and local."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tomllib

from caiman import __version__


def store_path(explicit: Path | None) -> Path:
    """Resolve configuration without creating any files or directories."""
    if explicit is not None:
        return explicit.expanduser().absolute()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    config_path = config_home / "caiman/config.toml"
    if config_path.exists():
        with config_path.open("rb") as file:
            config = tomllib.load(file)
        if "store_root" in config:
            value = config["store_root"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{config_path}: store_root must be a nonempty path")
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise ValueError(f"{config_path}: store_root must be an absolute path")
            return path
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return (data_home / "caiman/store").absolute()


def _config_commands(commands) -> None:
    for kind in ("board", "project"):
        group = commands.add_parser(kind, help=f"Author and inspect {kind} configurations")
        actions = group.add_subparsers(dest="action", required=True)
        configure = actions.add_parser("configure", help="Create or edit a draft in the TUI")
        configure.add_argument("config", nargs="?", type=Path, help="Editable JSON draft")
        template = actions.add_parser("template", help="Write a blank JSON draft")
        template.add_argument("--output", type=Path, required=True)
        validate = actions.add_parser("validate", help="Validate and resolve a draft without writing")
        validate.add_argument("config", type=Path)
        show = actions.add_parser("show", help="Show a version, or list versions when omitted")
        show.add_argument("name")
        show.add_argument("--version")
        export = actions.add_parser("export", help="Export a pinned snapshot as editable JSON")
        export.add_argument("name")
        export.add_argument("--version", required=True)
        export.add_argument("--output", type=Path, required=True)
        new = actions.add_parser("new-version", help="Edit a copy of an existing version in the TUI")
        new.add_argument("name")
        new.add_argument("--from-version", required=True)
        new.add_argument("--version", required=True, help="New opaque version label")
        new.add_argument("--relation", default="", help="Human explanation of this revision")
        for action in (configure, validate, show, export, new):
            action.add_argument("--store", type=Path)
        for action in (show, export, new):
            if kind == "project":
                action.add_argument("--compartment", action="append", default=[],
                                    help="Compartment to include (usually a customer); repeat for all required compartments")


def _run_config(args, root: Path) -> int:
    from caiman.configurations.files import read_draft, template, write_draft
    from caiman.configurations.service import ConfigurationService
    from caiman.storage.store import Store

    service = ConfigurationService(Store(root))
    scopes = set(getattr(args, "compartment", []))
    if args.action == "configure":
        draft = read_draft(args.config) if args.config else template(args.command)
    elif args.action == "validate":
        prepared = service.prepare(args.command, read_draft(args.config))
        print(json.dumps(prepared.manifest, ensure_ascii=False, indent=2))
        return 0
    elif args.action == "show" and args.version is None:
        print(json.dumps(service.list_versions(args.command, args.name, compartments=scopes),
                         ensure_ascii=False, indent=2))
        return 0
    else:
        version = args.from_version if args.action == "new-version" else args.version
        manifest = service.load(args.command, args.name, version, compartments=scopes)
        if args.action == "show":
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.action == "export":
            write_draft(args.output, manifest)
            print(f"Exported {args.command} configuration to {args.output}")
            return 0
        if args.version in service.list_versions(args.command, args.name, compartments=scopes):
            raise ValueError('That version label already exists. Choose a new label, or use configuration editing to explicitly update it.')
        draft = copy.deepcopy(manifest)
        draft.update(version=args.version, derives_from=args.from_version, relation=args.relation)

    from caiman.configurations.tui import ConfigApp

    ConfigApp(kind=args.command, store_root=root, draft=draft).run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="caiman", description="Configure versioned firmware documents, boards, and projects. Run without a command for guided setup and the home screen."
    )
    parser.add_argument("--version", action="version", version=f"caiman {__version__}")
    parser.add_argument('--store', dest='launcher_store', metavar='PATH', type=Path, help='Local store (overrides config.toml)')
    commands = parser.add_subparsers(dest="command")
    session = commands.add_parser('session', help='Non-interactive harness callbacks')
    session.add_subparsers(dest='session_action', required=True).add_parser('start', help='Introduce Caiman to a session')
    ingest = commands.add_parser("ingest", help="Open the document ingestion TUI")
    ingest.add_argument("markdown", nargs="?", type=Path, help="Prepared Markdown file")
    ingest.add_argument("--store", type=Path, help="Local store path (overrides config.toml)")
    _config_commands(commands)
    little = commands.add_parser("little", help="Little caiman: watch a session's managed-document use")
    little.add_argument("--store", type=Path, help="Local store path (overrides config.toml)")
    documents = commands.add_parser("documents", help="List registered documents available for pinning")
    documents.add_argument("--store", type=Path)
    documents.add_argument("--compartment", action="append", default=[],
                           help="Include this compartment (usually a customer); repeat for all required compartments")
    args = parser.parse_args(argv)

    if args.command == 'session':
        from caiman.hooks.service import session_start

        try:
            return session_start(store_path(args.launcher_store))
        except Exception:
            # Harness callbacks must never prevent a session from starting.
            return 0

    interactive = args.command in (None, "ingest", "little") or getattr(args, "action", None) in {"configure", "new-version"}
    if interactive and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        print(
            f"caiman{(' ' + args.command) if args.command else ''} requires an interactive terminal. "
            "Run it directly in your terminal; no files were written.",
            file=sys.stderr,
        )
        return 2

    try:
        if getattr(args, "action", None) == "template":
            from caiman.configurations.files import template, write_draft

            write_draft(args.output, template(args.command))
            print(f"Wrote editable {args.command} draft to {args.output}")
            return 0
        root = store_path(getattr(args, 'store', None) or args.launcher_store)
        if args.command in {"board", "project"}:
            return _run_config(args, root)
        if args.command == "little":
            from caiman.little_caiman.tui import run_little_caiman

            return run_little_caiman(root)
        if args.command == "documents":
            from caiman.configurations.service import ConfigurationService
            from caiman.storage.store import Store

            records = ConfigurationService(Store(root)).list_documents(compartments=set(args.compartment))
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return 0
        from caiman.dashboard.workflow import run_workflow

        return run_workflow(root, source_path=getattr(args, 'markdown', None), ingest=args.command == 'ingest')
    except (OSError, ValueError) as error:
        print(f"caiman: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0

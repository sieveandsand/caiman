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
            if kind in {"board", "project"}:
                action.add_argument("--pod", action="append", default=[],
                                    help="Filter by pod; repeat to include several")


def _run_config(args, root: Path) -> int:
    from caiman.configurations.files import read_draft, template, write_draft
    from caiman.configurations.service import ConfigurationService
    from caiman.storage.store import Store

    service = ConfigurationService(Store(root))
    scopes = set(getattr(args, "pod", []))
    if args.action == "configure":
        draft = read_draft(args.config) if args.config else template(args.command)
    elif args.action == "validate":
        prepared = service.prepare(args.command, read_draft(args.config))
        print(json.dumps(prepared.manifest, ensure_ascii=False, indent=2))
        return 0
    elif args.action == "show" and args.version is None:
        print(json.dumps(service.list_versions(args.command, args.name, pods=scopes),
                         ensure_ascii=False, indent=2))
        return 0
    else:
        version = args.from_version if args.action == "new-version" else args.version
        manifest = service.load(args.command, args.name, version, pods=scopes)
        if args.action == "show":
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        owner = next(r['pod'] for r in service.list_configs(args.command, pods=scopes)
                     if r['name'] == args.name and r['version'] == version)
        if args.action == "export":
            write_draft(args.output, dict(manifest, pod=owner))
            print(f"Exported {args.command} configuration to {args.output}")
            return 0
        if args.version in service.list_versions(args.command, args.name, pods=scopes):
            raise ValueError('That version label already exists. Choose a new label, or use configuration editing to explicitly update it.')
        draft = copy.deepcopy(manifest)
        draft.update(version=args.version, derives_from=args.from_version, relation=args.relation, pod=owner)

    from caiman.configurations.tui import ConfigApp

    ConfigApp(kind=args.command, store_root=root, draft=draft).run()
    return 0


def _session_commands(commands) -> None:
    session = commands.add_parser('session', help='Load boards and projects into an agent session')
    actions = session.add_subparsers(dest='action', required=True)
    for name in ('hook', 'start'):
        hook = actions.add_parser(name, help='Harness start hook: register the session (reads JSON on stdin)'
                                  if name == 'hook' else argparse.SUPPRESS)
        hook.add_argument('--harness', choices=('claude', 'codex'), default='claude')
    listing = actions.add_parser('list', help='List loadable boards and projects; a name lists its versions')
    listing.add_argument('name', nargs='?')
    listing.add_argument('--kind', choices=('board', 'project'))
    load = actions.add_parser('load', help="Install a board or project version into this session's folder")
    load.add_argument('kind', choices=('board', 'project'))
    load.add_argument('name')
    load.add_argument('--version', help='Exact version label; omitted, the versions are listed')
    status = actions.add_parser('status', help="Show this session's loaded context")
    for action in (listing, load):
        action.add_argument('--pod', action='append', default=[], help='Limit to a pod; repeat for several')
    for action in (listing, load, status):
        action.add_argument('--store', type=Path)
    for action in (load, status):
        action.add_argument('--session', help='Session folder name (default: $CAIMAN_SESSION)')
        action.add_argument('--workspace', type=Path,
                            help='Worktree holding .caiman/ (default: $CAIMAN_WORKSPACE, then search upward)')


def _session_hook(args) -> int:
    from caiman.hooks.service import session_hook

    try:
        output = session_hook(store_path(args.launcher_store), args.harness, json.load(sys.stdin))
    except Exception:
        # Harness callbacks must never prevent a session from starting (I-10).
        return 0
    if output:
        print(output)
    return 0


def _session_target(args) -> Path:
    from caiman.sessions.service import find_workspace, session_folder

    name = args.session or os.environ.get('CAIMAN_SESSION')
    if not name:
        raise ValueError('No session given; pass --session (the hook prints it) or set CAIMAN_SESSION')
    workspace = args.workspace or os.environ.get('CAIMAN_WORKSPACE')
    root = Path(workspace) if workspace else find_workspace(Path.cwd())
    if root is None:
        raise ValueError('No .caiman/ folder here or above; pass --workspace')
    return session_folder(root, name)


def _run_session(args, root: Path) -> int:
    from caiman.sessions.service import count, list_choices, load_context, read_state

    pods = set(getattr(args, 'pod', []))
    if args.action == 'list':
        print(json.dumps(list_choices(root, args.name, kind=args.kind, pods=pods),
                         ensure_ascii=False, indent=2))
        return 0
    folder = _session_target(args)
    if args.action == 'status':
        state = read_state(folder)
        print(json.dumps({'session': folder.name, 'folder': str(folder), 'loaded': state,
                          'brief': str(folder / 'context' / 'project.md') if state else None},
                         ensure_ascii=False, indent=2))
        return 0
    if args.version is None:
        # A bare name never resolves to a version (I-7).
        versions = list_choices(root, args.name, kind=args.kind, pods=pods)
        print(json.dumps(versions, ensure_ascii=False, indent=2))
        print('caiman: choose one version with --version; versions are not ordered', file=sys.stderr)
        return 1
    if len(pods) > 1:
        raise ValueError('Load from one pod at a time')
    state = load_context(root, folder, args.kind, args.name, args.version, next(iter(pods), None))
    brief = folder / 'context' / 'project.md'
    print(f"Loaded {state['kind']} {state['name']} @ {state['version']} into {folder.name} "
          f"(revision {state['revision']}, {count(state['documents'])}).\nRead {brief}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="caiman", description="Configure versioned firmware documents, boards, and projects. Run without a command for guided setup and the home screen."
    )
    parser.add_argument("--version", action="version", version=f"caiman {__version__}")
    parser.add_argument('--store', dest='launcher_store', metavar='PATH', type=Path, help='Local store (overrides config.toml)')
    commands = parser.add_subparsers(dest="command")
    _session_commands(commands)
    ingest = commands.add_parser("ingest", help="Open the document ingestion TUI")
    ingest.add_argument("file", nargs="?", type=Path, help="Document file (any format)")
    ingest.add_argument("--store", type=Path, help="Local store path (overrides config.toml)")
    _config_commands(commands)
    little = commands.add_parser("little", help="Little caiman: watch a session's managed-document use")
    little.add_argument("--store", type=Path, help="Local store path (overrides config.toml)")
    documents = commands.add_parser("documents", help="List registered documents available for pinning")
    documents.add_argument("--store", type=Path)
    documents.add_argument("--pod", action="append", default=[],
                           help="Filter by pod; defaults to all local pods")
    pod = commands.add_parser('pod', help='Manage local pods and optional Git sharing')
    pod_actions = pod.add_subparsers(dest='action', required=True)
    for name in ('list', 'create', 'clone', 'connect', 'sync', 'disconnect', 'default', 'remove'):
        command = pod_actions.add_parser(name)
        command.add_argument('--store', type=Path)
        if name != 'list':
            command.add_argument('name', help='Pod ID or local folder name')
        if name in {'clone', 'connect'}:
            command.add_argument('remote', nargs='?' if name == 'connect' else None)
    args = parser.parse_args(argv)

    if args.command == 'session' and args.action in {'hook', 'start'}:
        return _session_hook(args)

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
        if args.command == 'pod':
            from caiman.repositories.service import RepoManager
            manager = RepoManager(root)
            if args.action == 'list':
                print(json.dumps(manager.list_repos(), indent=2))
            else:
                action = {'clone': 'add', 'connect': 'initialize', 'disconnect': 'remove', 'remove': 'unregister'}.get(args.action, args.action)
                plan = manager.prepare(action, args.name, getattr(args, 'remote', None) or '')
                manager.apply(plan)
                print(plan.preview)
            return 0
        if args.command in {"board", "project"}:
            return _run_config(args, root)
        if args.command == 'session':
            return _run_session(args, root)
        if args.command == "little":
            from caiman.little_caiman.tui import run_little_caiman

            return run_little_caiman(root)
        if args.command == "documents":
            from caiman.configurations.service import ConfigurationService
            from caiman.storage.store import Store

            records = ConfigurationService(Store(root)).list_documents(pods=set(args.pod))
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return 0
        from caiman.dashboard.workflow import run_workflow

        return run_workflow(root, source_path=getattr(args, 'file', None), ingest=args.command == 'ingest')
    except (OSError, ValueError) as error:
        print(f"caiman: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0

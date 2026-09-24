"""Private, disposable configuration drafts edited by the user's Vim binary."""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from caiman.configurations.files import read_draft


class VimDraft:
    """Keep one editable file alive across validation failures and retry prompts.

    ``edit`` returns false for a nonzero Vim exit (including ``:cq``), allowing
    the caller to cancel without registration. ``read`` validates JSON while
    retaining invalid input at the same path so it can be reopened. Exiting the
    context deletes the temporary copy; no store objects are edited.
    """

    def __init__(self, manifest: dict):
        if not isinstance(manifest, dict):
            raise ValueError('A Vim draft must start from a configuration object')
        self._initial = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        self._directory = None
        self._path = None

    def __enter__(self):
        if self._directory is not None:
            raise ValueError('This Vim draft is already open')
        self._directory = tempfile.TemporaryDirectory(prefix='caiman-draft-')
        directory = Path(self._directory.name)
        directory.chmod(0o700)
        self._path = directory / 'configuration.json'
        try:
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as file:
                file.write(self._initial)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._directory is not None:
            self._directory.cleanup()
        self._directory = None
        self._path = None

    @property
    def path(self) -> Path:
        if self._path is None:
            raise ValueError('Use VimDraft inside a with block')
        return self._path

    def _check_file(self):
        if not stat.S_ISREG(self.path.lstat().st_mode):
            raise ValueError('The Vim draft must remain a regular file, not a link')

    @property
    def text(self) -> str:
        self._check_file()
        return self.path.read_text(encoding='utf-8')

    @property
    def changed(self) -> bool:
        self._check_file()
        return self.path.read_bytes() != self._initial

    def read(self) -> dict:
        self._check_file()
        return read_draft(self.path)

    def edit(self) -> bool:
        """Open Vim attached to the terminal; return false when the user aborts."""
        self._check_file()
        executable = shutil.which('vim')
        if executable is None:
            raise ValueError('Cannot find vim on PATH. Install Vim or add it to PATH, then try again.')
        args = [executable, '-u', 'NONE', '-U', 'NONE', '-i', 'NONE', '-n', '-N', '--noplugin',
                '--cmd', 'set nomodeline noexrc nobackup nowritebackup noundofile viminfo=',
                '-c', 'setlocal filetype=json', '--', str(self.path)]
        result = subprocess.run(args, check=False)
        self._check_file()
        self.path.chmod(0o600)
        return result.returncode == 0

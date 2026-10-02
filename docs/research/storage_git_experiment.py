"""Synthetic, local-only experiments for team storage (STORAGE.md §6.6); not backend tests.

Run with: python3 docs/research/storage_git_experiment.py
Creates temporary Git repositories, never contacts a network, and removes only
its own temporary directory on exit. Requires Python 3 and Git.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_ascii(value):
    # This experiment uses ASCII keys and no floats. This is not a general JCS
    # implementation and must not be used to implement the proposed schemas.
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    env = os.environ.copy()
    # Isolate experiments from user Git configuration, credentials and hooks.
    for key in tuple(env):
        if key.startswith("GIT_"):
            del env[key]
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="Synthetic Research",
        GIT_AUTHOR_EMAIL="research@example.invalid",
        GIT_COMMITTER_NAME="Synthetic Research",
        GIT_COMMITTER_EMAIL="research@example.invalid",
    )

    def git(cwd, *args, check=True):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=" + os.devnull, *args],
            cwd=cwd, env=env, capture_output=True, check=check,
        )

    with tempfile.TemporaryDirectory(prefix="caiman-storage-research-") as tmp:
        root = Path(tmp)
        remote, seed, alice, bob = [root / name for name in ("remote.git", "seed", "alice", "bob")]
        git(root, "init", "--bare", "--initial-branch=caiman-store", str(remote))
        git(root, "clone", str(remote), str(seed))
        original = "# Synthetic manual\n\n" + "".join(
            f"Register {n}: {hashlib.sha256(str(n).encode()).hexdigest()}\n"
            for n in range(4000)
        )
        revised = original.replace("Register 2000:", "Corrected register 2000:")
        bodies = [original.encode(), revised.encode()]
        paths = []
        for body in bodies:
            value = digest(body).split(":")[1]
            path = seed / "blobs" / "sha256" / value[:2] / value
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            paths.append(path.relative_to(seed))
        ref = Path("refs/projects/example/Rev-A")
        (seed / ref).parent.mkdir(parents=True)
        (seed / ref).write_bytes(canonical_ascii({"digest": "sha256:" + "0" * 64, "generation": 1}))
        git(seed, "add", ".")
        git(seed, "commit", "-m", "Synthetic initial objects")
        git(seed, "push", "origin", "HEAD:refs/heads/caiman-store")
        for clone in (alice, bob):
            git(root, "clone", str(remote), str(clone))
        for clone, value in ((alice, "a"), (bob, "b")):
            (clone / ref).write_bytes(canonical_ascii({"digest": "sha256:" + value * 64, "generation": 2}))
            git(clone, "add", str(ref))
            git(clone, "commit", "-m", "Synthetic competing update")
        git(alice, "push", "origin", "HEAD:refs/heads/caiman-store")
        rejected = git(bob, "push", "origin", "HEAD:refs/heads/caiman-store", check=False)
        assert rejected.returncode != 0, "Competing push unexpectedly succeeded"
        accepted = json.loads(git(remote, "show", "caiman-store:" + str(ref)).stdout)
        assert accepted["digest"] == "sha256:" + "a" * 64
        for body, path in zip(bodies, paths):
            assert git(alice, "show", "HEAD:" + str(path)).stdout == body
        git(alice, "repack", "-a", "-d", "--window=250", "--depth=50")
        delta_blobs = 0
        for index in (alice / ".git/objects/pack").glob("*.idx"):
            lines = git(alice, "verify-pack", "-v", str(index)).stdout.decode().splitlines()
            delta_blobs += sum(len(fields := line.split()) == 7 and fields[1] == "blob" for line in lines)
        assert delta_blobs > 0, "No blob delta observed in synthetic similar files"

    # A small ASCII-only graph demonstrates identity, not full schema validation.
    manual = {"blob": digest(b"# Manual\n\nOriginal text.\n")}
    corrected = {"blob": digest(b"# Manual\n\nCorrected text.\n")}
    spec = {"blob": digest(b"# Specification\n\nREQ-1: Example.\n")}
    md, cd, sd = [digest(canonical_ascii(obj)) for obj in (manual, corrected, spec)]

    def docset(entries):
        return digest(canonical_ascii({"documents": sorted(set(entries))}))

    assert docset([md, sd]) == docset([sd, md, md])
    assert docset([md, sd]) != docset([cd, sd])
    print(json.dumps({
        "git_version": git(Path.cwd(), "--version").stdout.decode().strip(),
        "competing_non_fast_forward_push_rejected": True,
        "accepted_remote_ref_preserved": True,
        "transport_preserved_document_bytes": True,
        "synthetic_document_bytes": sum(map(len, bodies)),
        "delta_compressed_blobs_observed": delta_blobs,
        "sorted_document_set_is_order_and_duplicate_independent": True,
        "document_change_changes_document_set_hash": True,
        "original_document_set_hash": docset([md, sd]),
        "changed_document_set_hash": docset([cd, sd]),
    }, indent=2))


if __name__ == "__main__":
    main()

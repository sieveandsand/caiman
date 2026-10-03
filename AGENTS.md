# Caiman agent instructions

Read [CLAUDE.md](CLAUDE.md) before making changes. It owns the repository's
invariants and working conventions; follow its documentation reading table.

For terminal UI changes, support truecolor, 256-color, and 16-color terminals.
Selection, keyboard focus, and status indicators must survive color reduction.
Do not rely only on subtle background differences: `#102210` and `#000000`
both map to black in 16/256 colors. Use a visible border, marker, or text cue,
and check changed UI states in all three color modes, including selection
retained after focus moves to action controls.

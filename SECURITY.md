# Security policy

This repository is a data file and a static site. Nothing listed here is executed by this
repository: the checks fetch a snapshot, read its JSON declaration and compare fields. Listed
modules run in the user's game through the Plutonium Agent Toolkit, which builds them from source
with pinned tools and never installs a native plugin.

A listing is not a security review. `snapshot_status` reports the registry's own static checks on
the exact commit; it is not a certification, warranty or endorsement, and a later commit of the
same repository is not covered by it.

Report a problem with the registry, its workflows or a listing that hides something harmful
through GitHub's private vulnerability reporting on this repository. Include the entry name and
commit. You will receive an acknowledgement within seven days. Do not open a public issue for it.

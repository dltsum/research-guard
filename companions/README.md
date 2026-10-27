# CiteSpace companion from the complete local distribution

`citespace-mcp/` preserves all 16 companion files from the owner's
`Research_Guard.zip` full distribution (2026-10-22, 773,297,766 bytes).
Its declared plugin version remains `0.1.0+codex.20260925085627`; the snapshot
also contains the documented October 21/22 fixes. The manifest timestamp alone
does not identify the later source snapshot. No native graph was rerun for this
repository import.

Supported historical engine: **CiteSpace 6.4.R2 Basic**, application JAR
`CiteSpace-6.4.2.jar`; companion Java: **Temurin 22.0.1+8 Windows x64 JRE**.
The local full distribution retains both application/runtime trees unchanged.
This public directory contains the companion implementation, tests, Skill and
self-built narrow Java adapter, not the proprietary CiteSpace application.

## Install and bind

1. Use a legitimately obtained local engine and the matching Java runtime.
2. Create an isolated Python environment and install
   `citespace-mcp/requirements.txt` (MCP and pyjab; dependencies retain their licenses).
3. Bind `.mcp.json` to that Python and set `CITESPACE_INSTALL_DIR`,
   `CITESPACE_JAVA` and `CITESPACE_TASK_ROOT` to your actual local paths. The supplied
   relative layout expects a sibling `software/` directory; it is not downloaded
   or silently substituted by this repository.
4. Load the companion separately from Research Guard. Complete any license,
   account or email prompts yourself. The preserved October snapshot does not
   automatically submit a test email by default.
5. Read the companion README/Skill and the integration guide before native runs.
   Old automatic-startup descriptions are historical, not current authorization.

## Distribution boundary

The [official FAQ](https://citespace.podia.com/faq), section 2.4, identifies
unofficial distribution sites as unauthorized. No permission for a GitHub mirror
of the historical application was established. Therefore this repository does
not republish the vendor application, research PDFs or private task transcripts.
The owner's existing **local** full archive is preserved without removing those
files. Public application upload requires the relevant redistribution permission.

The code here is the owner's companion snapshot; it does not grant a license to
CiteSpace, Java or pyjab. Existing bridge notices are retained. Runtime, corpus
and native-result evidence are not interchangeable with a source/format check.

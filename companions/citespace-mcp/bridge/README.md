# Narrow Swing startup adapter

The bundled adapter is our own `CiteSpaceStartupAgent.java`, compiled for Java 8
bytecode and run inside the unchanged CiteSpace 6.4.2 JAR on Java 22.0.1.
It does not register a ClassFileTransformer, redefine classes, edit license data,
or bypass a check. It sets one visible editable JTextField and invokes a verified
dialog's default JButton on the Swing event-dispatch thread. The sole address is
the reserved non-routable `citespace-mcp-test@example.invalid`.

Python must first verify the notice/email/confirmation lifecycle and exact
CiteSpace process. Each action uses a unique persisted request under
`%LOCALAPPDATA%/CiteSpaceCodexBridge/<launch-nonce>/`; the response includes the JVM
PID, checked against the observed window PID. Unknown completion is not replayed.
No HTTP listener, arbitrary-code command, or general input injection is exposed.

Why this adapter: Windows may reject foreground activation. Posted keystrokes
therefore do not reliably implement an API. Direct Swing control calls avoid
keyboard focus entirely. The confirmation click is queued (not synchronously
waited inside a modal event handler), allowing the next modal event loop to run.

## Runtime provenance

Verified companion runtime: Temurin 22.0.1+8 JRE, Windows x64.
Downloaded via the official Adoptium API/release:

https://api.adoptium.net/v3/assets/version/22.0.1%2B8?architecture=x64&heap_size=normal&image_type=jre&jvm_impl=hotspot&os=windows&vendor=eclipse

https://github.com/adoptium/temurin22-binaries/releases/download/jdk-22.0.1%2B8/OpenJDK22U-jre_x64_windows_hotspot_22.0.1_8.zip

SHA-256: `7c7572ef9e3b53e91faeaa2b4f019dc496f428705ca672f417e21731b3a4089c`.
Archive 48,484,466 bytes. Not redistributed inside this plugin package.
No global Java PATH or installed CiteSpace files were changed.

## Rebuild

Use a trusted JDK compiler with `javac --release 8 -d classes CiteSpaceStartupAgent.java`,
then run `python package_agent.py`. This machine used Eclipse ECJ 4.6.1 from Maven
Central and the existing Java 8 `rt.jar` as bootclasspath; ECJ is a build-only
dependency, not part of the package:

https://repo.maven.apache.org/maven2/org/eclipse/jdt/core/compiler/ecj/4.6.1/ecj-4.6.1.jar

Its SHA-1 matched the repository sidecar: `5555607add54eb79c5a0729134e663fe2e6300c2`.
The release includes our source and our generated JAR, not third-party compiler
classes. The Java agent mechanism is documented at
https://docs.oracle.com/javase/8/docs/api/java/lang/instrument/package-summary.html.

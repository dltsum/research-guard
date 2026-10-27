"""Package our compiled adapter only; no third-party compiler is redistributed."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parent
classes=list((root/'classes').glob('CiteSpaceStartupAgent*.class'))
if not classes: raise SystemExit('Compile CiteSpaceStartupAgent.java first')
with ZipFile(root/'startup-agent.jar','w',ZIP_DEFLATED) as archive:
    archive.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nPremain-Class: CiteSpaceStartupAgent\r\n\r\n')
    for path in classes: archive.write(path,path.name)
print(root/'startup-agent.jar')

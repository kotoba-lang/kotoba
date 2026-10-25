# External fixtures

`revit2011_wall1.ifc` is a genuine Autodesk Revit Architecture 2011 IFC2X3
export (`FILE_NAME` application string: `Autodesk Revit Architecture 2011 -
1.0`), used unmodified as the origin model for the ADR-2607211437 gap-order
item 6 acceptance scenario (`revit-origin-model-acceptance-scenario` in
`test/bim_test.cljk`): import a real Revit-authored wall, edit its
properties, coordinate structural analysis and a drawing, export, reopen
the export with an independent parse, and compare semantics.

- Source: `https://raw.githubusercontent.com/IfcOpenShell/files/9fc2267d7f1ff35284c5b0fc28cc97bff7ace8e7/revit2011_wall1.ifc`
- Commit: `9fc2267d7f1ff35284c5b0fc28cc97bff7ace8e7`
- SHA-256: `34af07aa1618e283c2ddc2f963455fe77ec1c7e3287e29f2a14110abd1f4e195`
- This is the same file, at the same pinned commit, already used by
  `kotoba-lang/org-iso-16739`'s external corpus
  (`test/fixtures/external/manifest.edn`, entry `"Revit 2011 Wall 1
  IFC2x3"`) -- copied here rather than fetched at test time so this
  scenario runs offline like the rest of this repo's test suite.

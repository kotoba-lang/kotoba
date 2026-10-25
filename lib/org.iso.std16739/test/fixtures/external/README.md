# External IFC conformance fixtures

These files are unmodified buildingSMART International Sample-Test-Files at
commit `cecf656112a54a0d8cdd8b06b9398bfea5163886`:

https://github.com/buildingSMART/Sample-Test-Files

The source work is Copyright buildingSMART International Ltd. and licensed
under the Creative Commons Attribution 4.0 International License:

https://creativecommons.org/licenses/by/4.0/

The local names are normalized for deterministic test discovery. The original
paths and expected semantic product counts are recorded in `manifest.edn`.

The remote-only corpus also references public regression fixtures from
`IfcOpenShell/files` at a pinned commit, including Revit 2011/2014 exports.
Those files are downloaded only when the external corpus runner is invoked and
are not redistributed by this repository.

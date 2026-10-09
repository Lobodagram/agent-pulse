# Agent Pulse identity

The owner supplied the orange pulse logo on2026-10-09. `brand/agent-pulse.png` preserves the original transparent artwork. PNG sizes, macOS ICNS and Windows ICO are native packaging derivatives; the design is unchanged. `brand/manifest.json` contains the reviewed SHA256 allowlist for binary assets. The public exporter also checks file signatures. Screenshots remain separately allowlisted and use invented fixtures only.

Mac: CFBundleIconFile plus native Resources/logo-128.png; widget20pt, analytics32pt, Settings30pt. Windows: executable ICO plus packaged brand directory, Tk default window icon/header, Win32 tray icon with explicit handle cleanup. Source and frozen resource paths share the same resolver. GitHub EN/RU README uses the original logo; social preview uses the approved identity card.

The logo does not replace status/error text or accessible control labels. Native platform interactions and existing data/coverage semantics remain unchanged. Launch at login stays opt-in and is controlled by the system registration, not by this image.

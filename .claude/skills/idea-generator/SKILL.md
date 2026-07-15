---
name: idea-generator
description: Not yet implemented (build spec Phase 2). Will cross-reference top-performing formats, open trends, and the venue calendar to produce concrete post concepts with hook lines.
---

# idea-generator — Phase 2, not yet implemented

See `pubcam-content-agent-build-spec_2.md` Section 5. Will read from `posts`
(top-performing formats/venues) and `trends` (open, `acted_on = 0`), cross
reference against venue calendar context (Origin games, uni semester, winter
fireplace season, etc.), and write candidate rows into `ideas` with
`source = 'performance-insight'` or `'trend-sweep'`.

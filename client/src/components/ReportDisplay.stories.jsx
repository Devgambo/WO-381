import ReportDisplay from "./ReportDisplay";
import { withRouterAuth } from "../stories/decorators";

export default {
    title: "Components/ReportDisplay",
    component: ReportDisplay,
    decorators: [withRouterAuth],
};

const SAMPLE = `### Phase 1 — Transcription

| # | Criteria | Observed | Status |
|---|----------|----------|--------|
| 1 | Concrete grade | M25 | Compliant |
| 2 | Clear cover | 40 mm | Compliant |
| 3 | Lap length | Not shown | Missing Information ⚠️ |

### Phase 4 — Drawing Quality Assessment

**Severity:** REQUIRES_REVISION
**Critical defects count:** 1
**Rejection narrative:** Lap length is not annotated on the bar schedule.
`;

export const InitialReport = {
    args: {
        report: SAMPLE,
        title: "Phase 1 → Phase 4 report",
        filenamePrefix: "foundation_init",
    },
};

export const Empty = {
    args: { report: "", title: "Nothing yet" },
};

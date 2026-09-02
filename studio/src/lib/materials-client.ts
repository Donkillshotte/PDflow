/** Client-safe material catalog (no fs). Re-exports shared data. */

export type { MaterialLink } from "./materials-data";
export { MATERIALS, spiceFileHref } from "./materials-data";
import { WALKTHROUGHS as WALKTHROUGH_FILES } from "./materials-data";

export const WALKTHROUGHS = WALKTHROUGH_FILES.map((f) => ({
  href: `/materiali/reference/${f}`,
  title: f.replace("walkthrough-", "").replace(".tcl.md", ""),
  group: "Tcl",
  description: `Annotated walkthrough ${f}`,
}));

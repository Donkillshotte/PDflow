/**
 * Product surface snapshot for the current DSE invocation.
 * Product UI is limited to the current invocation and explicit live pairs.
 */
import { liveComparisons, type ExperimentPair } from "./lab";
import { getProductStory, type StorySlot } from "./story";

export type ProductSnapshot = {
  title: string;
  lead: string;
  rule: string;
  cooks: number;
  detail: string;
  slots: StorySlot[];
  comparisons: ExperimentPair[];
};

export function getProductSnapshot(): ProductSnapshot {
  const story = getProductStory();
  return {
    title: "Product",
    lead:
      "Current-invocation DSE measurements on the selected design. Cross-run product scoring is disabled until the controller emits an explicit same-run comparison.",
    rule:
      "Only comparisons explicitly emitted by the current DSE invocation are eligible. Missing comparison data is shown as unavailable.",
    cooks: story.product.cooks,
    detail: story.product.detail,
    slots: story.product.slots,
    comparisons: liveComparisons(),
  };
}

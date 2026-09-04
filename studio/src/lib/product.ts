/**
 * Product surface snapshot. Wins stay in win_rule.py.
 * This module only reads the campaign registry and mirrors the published rule.
 */
import { campaignComparisons, type ExperimentPair } from "./lab";
import { getProductStory, type StorySlot } from "./story";

export type ProductSnapshot = {
  title: string;
  lead: string;
  rule: string;
  wins: number;
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
      "Physical knobs on the official netlist, fixed die, real finish. DSE proposes knobs and does not run signoff_all. Wins stay in win_rule.py.",
    rule:
      "Same design, same clock, versus the slot base. Timing not worse than 5 ps and at least one of area / power / leakage / IR better by ≥10%, with none of the four worse by ≥10%. First close (WNS≥0) when the base is open, without worsening the four, is also a win. Moved die is wrong_die.",
    wins: story.product.wins,
    cooks: story.product.cooks,
    detail: story.product.detail,
    slots: story.product.slots,
    comparisons: campaignComparisons(),
  };
}

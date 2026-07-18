"use client";

import type { TreeNode } from "@/lib/types";

/**
 * The big "current step" card in guided mode. TO IMPLEMENT.
 *
 * Spec:
 *  - Shows node.prompt in large readable text (this is what the employee
 *    reads aloud), node.label small above it.
 *  - question: one large button per option (full width, generous padding).
 *  - action: single "Done — continue" button (options[0]).
 *  - end: green "call resolved" styling, no options; parent renders the
 *    Finish button.
 *  - Buttons call onChoose(optionIndex); disable them while `busy` (the
 *    step request is in flight) to prevent double-clicks.
 */
export interface GuidePanelProps {
  node: TreeNode;
  busy: boolean;
  onChoose: (optionIndex: number) => void;
}

export default function GuidePanel(props: GuidePanelProps) {
  return <p>TODO: implement GuidePanel</p>;
}

"use client";

import { memo } from "react";
import dynamic from "next/dynamic";

const JusticeScaleCanvas = dynamic(
  () => import("@/components/scale/JusticeScaleCanvas").then((m) => m.JusticeScaleCanvas),
  {
    ssr: false,
    loading: () => <div className="scale-canvas" />,
  }
);

type Props = {
  onBiasChange?: (bias: number) => void;
  size?: "hero" | "compact";
};

export const InteractiveScale = memo(function InteractiveScale({ onBiasChange, size = "hero" }: Props) {
  return (
    <div className={`scale-theater ${size}`}>
      <JusticeScaleCanvas size={size} onBiasChange={onBiasChange} />
    </div>
  );
});

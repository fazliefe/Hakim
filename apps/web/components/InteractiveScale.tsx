"use client";

import { memo } from "react";
import dynamic from "next/dynamic";
import type { SceneTheme } from "@/components/scale/JusticeScaleCanvas";

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
  scrollProgress?: number;
  theme?: SceneTheme;
};

export const InteractiveScale = memo(function InteractiveScale({
  onBiasChange,
  size = "hero",
  scrollProgress = 0,
  theme = "dark",
}: Props) {
  return (
    <div className={`scale-theater ${size}`}>
      <JusticeScaleCanvas size={size} onBiasChange={onBiasChange} scrollProgress={scrollProgress} theme={theme} />
    </div>
  );
});

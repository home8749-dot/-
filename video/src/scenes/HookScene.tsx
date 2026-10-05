import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BODY, DISPLAY } from "../fonts";
import { fitSize, RichText } from "../parts/RichText";
import type { Brand, Scene } from "../schema";
import { SceneFrame } from "./SceneFrame";

/** 첫 3초 훅: 크고 단단한 한 문장 */
export const HookScene: React.FC<{ brand: Brand; scene: Scene; index: number; total: number; mascot?: boolean }> = (p) => {
  const frame = useCurrentFrame();
  return (
    <SceneFrame {...p}>
      <div
        style={{
          fontFamily: DISPLAY,
          fontSize: fitSize(p.scene.text, p.scene.text.length > 24 ? 104 : 124),
          lineHeight: 1.22,
          color: p.brand.colors.ink,
          wordBreak: "keep-all",
          opacity: interpolate(frame, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          translate: interpolate(frame, [0, 14], ["0px 40px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        <RichText text={p.scene.text} color={p.brand.colors.highlight} startFrame={12} />
      </div>
      {p.scene.sub ? (
        <div
          style={{
            marginTop: 48,
            fontFamily: BODY,
            fontWeight: 700,
            fontSize: 50,
            lineHeight: 1.45,
            color: p.brand.colors.muted,
            wordBreak: "keep-all",
            opacity: interpolate(frame, [22, 34], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          {p.scene.sub}
        </div>
      ) : null}
    </SceneFrame>
  );
};

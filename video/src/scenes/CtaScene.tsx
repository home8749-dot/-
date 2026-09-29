import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BODY, DISPLAY } from "../fonts";
import { fitSize, RichText } from "../parts/RichText";
import type { Brand, Scene } from "../schema";
import { SceneFrame } from "./SceneFrame";

/** 마지막 장면: 저장 유도 + 도장 쾅 */
export const CtaScene: React.FC<{ brand: Brand; scene: Scene; index: number; total: number }> = (p) => {
  const frame = useCurrentFrame();
  const c = p.brand.colors;
  return (
    <SceneFrame {...p}>
      <div style={{ fontFamily: DISPLAY, fontSize: fitSize(p.scene.text, 100), lineHeight: 1.25, color: c.ink, wordBreak: "keep-all" }}>
        <RichText text={p.scene.text} color={c.highlight} startFrame={6} />
      </div>
      {p.scene.sub ? (
        <div style={{ marginTop: 40, fontFamily: BODY, fontWeight: 700, fontSize: 50, lineHeight: 1.45, color: c.muted, wordBreak: "keep-all" }}>
          {p.scene.sub}
        </div>
      ) : null}
      <div
        style={{
          marginTop: 70,
          alignSelf: "flex-end",
          width: 300,
          height: 300,
          borderRadius: "50%",
          border: `12px solid ${c.seal}`,
          outline: `4px solid ${c.seal}`,
          outlineOffset: -30,
          color: c.seal,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: DISPLAY,
          lineHeight: 1.05,
          rotate: "-12deg",
          opacity: interpolate(frame, [14, 16], [0, 0.92], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          scale: interpolate(frame, [14, 24], [1.8, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.2, 1.4, 0.4, 1),
          }),
        }}
      >
        <div style={{ fontSize: 96 }}>{p.brand.sealText}</div>
        <div style={{ fontSize: 44, marginTop: 8 }}>확인</div>
      </div>
    </SceneFrame>
  );
};

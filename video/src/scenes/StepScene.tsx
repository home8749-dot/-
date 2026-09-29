import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BODY } from "../fonts";
import { fitSize, RichText } from "../parts/RichText";
import type { Brand, Scene } from "../schema";
import { SceneFrame } from "./SceneFrame";

/** 한 장면 한 가지: 체크 라벨 + 핵심 문장 + 보조 설명 */
export const StepScene: React.FC<{ brand: Brand; scene: Scene; index: number; total: number }> = (p) => {
  const frame = useCurrentFrame();
  const c = p.brand.colors;
  return (
    <SceneFrame {...p}>
      {p.scene.label ? (
        <div
          style={{
            alignSelf: "flex-start",
            display: "flex",
            alignItems: "center",
            gap: 18,
            padding: "14px 28px 14px 20px",
            borderRadius: 16,
            backgroundColor: `${c.grid}1a`,
            color: c.grid,
            fontFamily: BODY,
            fontWeight: 800,
            fontSize: 46,
            translate: interpolate(frame, [0, 12], ["-40px 0px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            opacity: interpolate(frame, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          <svg width="52" height="52" viewBox="0 0 52 52">
            <rect x="3" y="3" width="46" height="46" rx="9" fill="none" stroke={c.grid} strokeWidth="5" />
            <path
              d="M13 27 L22 36 L40 16"
              fill="none"
              stroke={c.grid}
              strokeWidth="6"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="44"
              strokeDashoffset={interpolate(frame, [8, 20], [44, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
            />
          </svg>
          {p.scene.label}
        </div>
      ) : null}
      <div
        style={{
          marginTop: 44,
          fontFamily: BODY,
          fontWeight: 800,
          fontSize: fitSize(p.scene.text, p.scene.text.length > 30 ? 76 : 88),
          lineHeight: 1.3,
          color: c.ink,
          wordBreak: "keep-all",
          opacity: interpolate(frame, [4, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}
      >
        <RichText text={p.scene.text} color={c.highlight} startFrame={16} />
      </div>
      {p.scene.sub ? (
        <div
          style={{
            marginTop: 40,
            paddingLeft: 24,
            borderLeft: `6px solid ${c.grid}55`,
            fontFamily: BODY,
            fontWeight: 700,
            fontSize: 48,
            lineHeight: 1.5,
            color: c.muted,
            wordBreak: "keep-all",
            opacity: interpolate(frame, [18, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          {p.scene.sub}
        </div>
      ) : null}
    </SceneFrame>
  );
};

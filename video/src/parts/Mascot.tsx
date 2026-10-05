import { Easing, interpolate, useCurrentFrame } from "remotion";
import type { Brand } from "../schema";

export type Pose = "wave" | "point" | "think" | "cheer" | "stamp";

/**
 * 채널 마스코트 '단디' — 빨간 도장 캐릭터(코드로 그린 SVG, 무료·일관된 그림체).
 * 대기 중 살짝 통통 튀고, 2.6초마다 눈을 깜빡이며, 포즈별로 팔이 움직인다.
 */
export const Mascot: React.FC<{ brand: Brand; pose: Pose; size?: number; enterFrame?: number }> = ({
  brand,
  pose,
  size = 260,
  enterFrame = 4,
}) => {
  const f = useCurrentFrame();
  const c = brand.colors;
  const t = f / 30;
  const bob = Math.sin(t * Math.PI * 1.6) * 6;
  const blink = (f % 78) > 72 ? 0.15 : 1;
  const enter = interpolate(f, [enterFrame, enterFrame + 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.2, 1.5, 0.4, 1),
  });
  const swing = Math.sin(t * Math.PI * 3) * 18;
  // 팔 각도(도): [왼팔, 오른팔]
  const arms: Record<Pose, [number, number]> = {
    wave: [20, -120 + swing],
    point: [25, -70],
    think: [25, -150],
    cheer: [-140 - swing / 2, -140 + swing / 2],
    stamp: [30, interpolate(f % 36, [0, 10, 18, 36], [-160, -160, -20, -20])],
  };
  const [la, ra] = arms[pose];
  const stampDown = pose === "stamp" ? interpolate(f % 36, [10, 18, 24], [0, 14, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 240 240"
      style={{ overflow: "visible", scale: String(enter), translate: `0px ${bob + stampDown}px` }}
    >
      {/* 그림자 */}
      <ellipse cx="120" cy="226" rx={62 - bob} ry="9" fill={c.ink} opacity="0.12" />
      {/* 다리 */}
      <rect x="88" y="186" width="20" height="30" rx="10" fill={c.ink} />
      <rect x="132" y="186" width="20" height="30" rx="10" fill={c.ink} />
      {/* 팔 (어깨 기준 회전) */}
      <g transform={`rotate(${la} 62 128)`}>
        <rect x="18" y="120" width="46" height="16" rx="8" fill={c.seal} />
        <circle cx="20" cy="128" r="11" fill={c.paper} stroke={c.ink} strokeWidth="4" />
      </g>
      <g transform={`rotate(${ra} 178 128)`}>
        <rect x="176" y="120" width="46" height="16" rx="8" fill={c.seal} />
        <circle cx="220" cy="128" r="11" fill={c.paper} stroke={c.ink} strokeWidth="4" />
        {pose === "point" ? <path d="M228 128 l22 -6 l-4 12 z" fill={c.ink} /> : null}
      </g>
      {/* 도장 손잡이 */}
      <rect x="96" y="22" width="48" height="34" rx="14" fill={c.ink} />
      <rect x="86" y="50" width="68" height="16" rx="8" fill={c.ink} />
      {/* 몸통(도장) */}
      <rect x="54" y="62" width="132" height="132" rx="30" fill={c.seal} stroke={c.ink} strokeWidth="5" />
      <rect x="68" y="76" width="104" height="104" rx="20" fill="none" stroke={c.paper} strokeWidth="4" opacity="0.55" />
      {/* 얼굴 */}
      <ellipse cx="96" cy="118" rx="9" ry={11 * blink} fill={c.ink} />
      <ellipse cx="144" cy="118" rx="9" ry={11 * blink} fill={c.ink} />
      <circle cx="99" cy="114" r="3" fill={c.paper} opacity={blink} />
      <circle cx="147" cy="114" r="3" fill={c.paper} opacity={blink} />
      <ellipse cx="80" cy="140" rx="11" ry="7" fill={c.highlight} opacity="0.85" />
      <ellipse cx="160" cy="140" rx="11" ry="7" fill={c.highlight} opacity="0.85" />
      {pose === "think" ? (
        <path d="M108 150 q12 -6 24 0" fill="none" stroke={c.ink} strokeWidth="5" strokeLinecap="round" />
      ) : (
        <path d="M104 142 q16 18 32 0" fill={c.ink} stroke={c.ink} strokeWidth="4" strokeLinejoin="round" />
      )}
      {/* 생각 중 말풍선 */}
      {pose === "think" ? (
        <g opacity={interpolate(f, [10, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}>
          <circle cx="206" cy="58" r="8" fill={c.paper} stroke={c.ink} strokeWidth="3" />
          <circle cx="226" cy="30" r="14" fill={c.paper} stroke={c.ink} strokeWidth="3" />
          <text x="226" y="38" textAnchor="middle" fontSize="22" fontWeight="800" fill={c.seal}>?</text>
        </g>
      ) : null}
      {/* 응원 반짝이 */}
      {pose === "cheer" ? (
        <g fill={c.highlight} stroke={c.ink} strokeWidth="2.5">
          <path d="M30 40 l6 14 l14 6 l-14 6 l-6 14 l-6 -14 l-14 -6 l14 -6 z" opacity={0.5 + 0.5 * Math.sin(t * 6)} />
          <path d="M210 60 l4 9 l9 4 l-9 4 l-4 9 l-4 -9 l-9 -4 l9 -4 z" opacity={0.5 + 0.5 * Math.cos(t * 6)} />
        </g>
      ) : null}
    </svg>
  );
};

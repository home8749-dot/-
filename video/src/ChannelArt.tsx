import { AbsoluteFill } from "remotion";
import { BODY, DISPLAY } from "./fonts";
import type { Brand } from "./schema";

const gridBg = (g: string, cell: number) => ({
  backgroundImage: `linear-gradient(${g}24 2px, transparent 2px), linear-gradient(90deg, ${g}24 2px, transparent 2px)`,
  backgroundSize: `${cell}px ${cell}px`,
});

/** 프로필 이미지(원형으로 잘려도 도장이 온전하게 중앙 배치) */
export const Profile: React.FC<{ brand: Brand }> = ({ brand }) => (
  <AbsoluteFill style={{ backgroundColor: brand.colors.paper, ...gridBg(brand.colors.grid, 100), alignItems: "center", justifyContent: "center" }}>
    <div
      style={{
        width: 470,
        height: 470,
        borderRadius: 60,
        border: `26px solid ${brand.colors.seal}`,
        color: brand.colors.seal,
        fontFamily: DISPLAY,
        fontSize: 190,
        lineHeight: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        rotate: "-6deg",
        backgroundColor: brand.colors.paper,
      }}
    >
      {brand.sealText}
    </div>
  </AbsoluteFill>
);

/** 유튜브 배너 2560×1440. 모든 기기에 보이는 안전 영역 1546×423 안에 핵심 배치 */
export const Banner: React.FC<{ brand: Brand; tagline: string }> = ({ brand, tagline }) => (
  <AbsoluteFill style={{ backgroundColor: brand.colors.paper, ...gridBg(brand.colors.grid, 80), alignItems: "center", justifyContent: "center" }}>
    <div style={{ width: 1546, height: 423, display: "flex", alignItems: "center", gap: 60 }}>
      <div
        style={{
          width: 260,
          height: 260,
          flexShrink: 0,
          borderRadius: 36,
          border: `16px solid ${brand.colors.seal}`,
          color: brand.colors.seal,
          fontFamily: DISPLAY,
          fontSize: 104,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          rotate: "-6deg",
          backgroundColor: brand.colors.paper,
        }}
      >
        {brand.sealText}
      </div>
      <div style={{ display: "grid", gap: 18 }}>
        <div style={{ fontFamily: DISPLAY, fontSize: 150, lineHeight: 1, color: brand.colors.ink }}>{brand.name}</div>
        <div style={{ fontFamily: BODY, fontWeight: 800, fontSize: 60, color: brand.colors.ink }}>
          <span style={{ background: `linear-gradient(transparent 50%, ${brand.colors.highlight} 50%)`, padding: "0 8px" }}>{tagline}</span>
        </div>
        <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 40, color: brand.colors.muted }}>정부지원사업 · 매일 하나씩 · {brand.footer}</div>
      </div>
    </div>
  </AbsoluteFill>
);

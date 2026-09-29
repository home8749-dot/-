import type { Brand } from "../schema";
import { BODY, DISPLAY } from "../fonts";

/** 채널 도장 마크 + 채널명 + AI 고지 */
export const TopBar: React.FC<{ brand: Brand }> = ({ brand }) => (
  <div
    style={{
      position: "absolute",
      top: 130,
      left: 90,
      right: 90,
      display: "flex",
      alignItems: "center",
      gap: 22,
    }}
  >
    <div
      style={{
        width: 84,
        height: 84,
        borderRadius: 14,
        border: `5px solid ${brand.colors.seal}`,
        color: brand.colors.seal,
        fontFamily: DISPLAY,
        fontSize: 34,
        lineHeight: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        rotate: "-6deg",
      }}
    >
      {brand.sealText}
    </div>
    <div style={{ fontFamily: DISPLAY, fontSize: 52, color: brand.colors.ink }}>{brand.name}</div>
    <div style={{ marginLeft: "auto", fontFamily: BODY, fontWeight: 700, fontSize: 30, color: brand.colors.muted }}>
      {brand.footer}
    </div>
  </div>
);

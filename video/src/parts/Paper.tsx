import { AbsoluteFill } from "remotion";
import type { Brand } from "../schema";

/** 원고지 격자 바탕 */
export const Paper: React.FC<{ brand: Brand; children: React.ReactNode }> = ({ brand, children }) => {
  const g = brand.colors.grid;
  return (
    <AbsoluteFill style={{ backgroundColor: brand.colors.paper }}>
      <div
        style={{
          position: "absolute",
          left: 60,
          right: 60,
          top: 300,
          bottom: 360,
          backgroundImage: `linear-gradient(${g}1f 2px, transparent 2px), linear-gradient(90deg, ${g}1f 2px, transparent 2px)`,
          backgroundSize: "80px 80px",
          border: `3px solid ${g}33`,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};

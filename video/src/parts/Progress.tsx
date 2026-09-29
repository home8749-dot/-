import { interpolate } from "remotion";
import type { Brand } from "../schema";

/** 장면 진행 표시: 지난 장면은 채움, 현재 장면은 시간에 따라 채움 */
export const Progress: React.FC<{ brand: Brand; index: number; total: number; frame: number; duration: number }> = ({
  brand,
  index,
  total,
  frame,
  duration,
}) => (
  <div style={{ position: "absolute", top: 250, left: 90, right: 90, display: "flex", gap: 10 }}>
    {Array.from({ length: total }).map((_, i) => (
      <div key={i} style={{ flex: 1, height: 10, borderRadius: 5, backgroundColor: `${brand.colors.grid}26`, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            backgroundColor: brand.colors.grid,
            width:
              i < index
                ? "100%"
                : i > index
                  ? "0%"
                  : `${interpolate(frame, [0, duration], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
          }}
        />
      </div>
    ))}
  </div>
);

import { Audio } from "@remotion/media";
import { staticFile, useCurrentFrame } from "remotion";
import { Mascot } from "../parts/Mascot";
import { Paper } from "../parts/Paper";
import { Progress } from "../parts/Progress";
import { TopBar } from "../parts/TopBar";
import type { Brand, Scene } from "../schema";

/** 모든 장면 공통 틀: 원고지 바탕 · 상단 채널 바 · 진행 표시 · 음성 */
export const SceneFrame: React.FC<{
  brand: Brand;
  scene: Scene;
  index: number;
  total: number;
  mascot?: boolean;
  children: React.ReactNode;
}> = ({ brand, scene, index, total, mascot, children }) => {
  const pose = scene.pose ?? (scene.kind === "hook" ? (index === 0 ? "wave" : "think") : scene.kind === "cta" ? "stamp" : (["point", "cheer"] as const)[index % 2]);
  const frame = useCurrentFrame();
  return (
    <Paper brand={brand}>
      <TopBar brand={brand} />
      <Progress brand={brand} index={index} total={total} frame={frame} duration={scene.durationInFrames} />
      {/* 쇼츠 우측 버튼·하단 제목 영역을 피한 안전 영역 */}
      <div style={{ position: "absolute", left: 90, right: 150, top: 360, bottom: mascot ? 790 : 420, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        {children}
      </div>
      {mascot ? (
        <div style={{ position: "absolute", right: 150, bottom: 420 }}>
          <Mascot brand={brand} pose={pose} size={370} />
        </div>
      ) : null}
      {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
    </Paper>
  );
};

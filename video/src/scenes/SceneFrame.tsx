import { Audio } from "@remotion/media";
import { staticFile, useCurrentFrame } from "remotion";
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
  children: React.ReactNode;
}> = ({ brand, scene, index, total, children }) => {
  const frame = useCurrentFrame();
  return (
    <Paper brand={brand}>
      <TopBar brand={brand} />
      <Progress brand={brand} index={index} total={total} frame={frame} duration={scene.durationInFrames} />
      {/* 쇼츠 우측 버튼·하단 제목 영역을 피한 안전 영역 */}
      <div style={{ position: "absolute", left: 90, right: 150, top: 360, bottom: 420, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        {children}
      </div>
      {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
    </Paper>
  );
};

import { fade } from "@remotion/transitions/fade";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import React from "react";
import { CalculateMetadataFunction } from "remotion";
import "./fonts";
import { CtaScene } from "./scenes/CtaScene";
import { HookScene } from "./scenes/HookScene";
import { StepScene } from "./scenes/StepScene";
import { ShortProps, TRANSITION_FRAMES } from "./schema";

const SCENES = { hook: HookScene, step: StepScene, cta: CtaScene };

/**
 * 단디서류 쇼츠 템플릿. 장면들은 하나의 원본 템플릿으로 통제하려는 의도라
 * props 로 받아 반복 생성한다(에이전트가 매일 props JSON 만 바꿔 렌더링).
 */
export const ShortVideo: React.FC<ShortProps> = ({ brand, scenes }) => (
  <TransitionSeries>
    {scenes.map((scene, i) => {
      const Comp = SCENES[scene.kind];
      return (
        <React.Fragment key={i}>
          {i > 0 ? (
            <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })} />
          ) : null}
          <TransitionSeries.Sequence name={`${i + 1}. ${scene.kind}`} durationInFrames={scene.durationInFrames}>
            <Comp brand={brand} scene={scene} index={i} total={scenes.length} />
          </TransitionSeries.Sequence>
        </React.Fragment>
      );
    })}
  </TransitionSeries>
);

export const calculateShortMetadata: CalculateMetadataFunction<ShortProps> = ({ props }) => {
  const sum = props.scenes.reduce((a, s) => a + s.durationInFrames, 0);
  return { durationInFrames: sum - TRANSITION_FRAMES * Math.max(0, props.scenes.length - 1) };
};

import { z } from "zod";

export const sceneSchema = z.object({
  kind: z.enum(["hook", "step", "cta"]),
  /** 단계 라벨. 예: "1. 신청자격" */
  label: z.string().optional(),
  /** 화면 핵심 문구. ==형광펜== 으로 감싼 부분이 강조된다 */
  text: z.string(),
  /** 보조 설명 */
  sub: z.string().optional(),
  durationInFrames: z.number().int().positive(),
  /** 마스코트 포즈(선택). 없으면 장면 종류에 맞춰 자동 */
  pose: z.enum(["wave", "point", "think", "cheer", "stamp"]).optional(),
  /** public/ 기준 음성 파일 경로(선택) */
  audio: z.string().optional(),
});

export const brandSchema = z.object({
  name: z.string(),
  sealText: z.string(),
  footer: z.string(),
  colors: z.object({
    paper: z.string(),
    ink: z.string(),
    grid: z.string(),
    seal: z.string(),
    highlight: z.string(),
    muted: z.string(),
  }),
});

export const shortSchema = z.object({
  brand: brandSchema,
  scenes: z.array(sceneSchema),
  /** 영상 전체 내레이션(public/ 기준, 선택). 장면별 audio 대신 한 파일로 쓸 때 */
  audio: z.string().optional(),
  audioDelayFrames: z.number().int().nonnegative().optional(),
  /** 마스코트 '단디' 표시 */
  mascot: z.boolean().optional(),
});

export type Scene = z.infer<typeof sceneSchema>;
export type Brand = z.infer<typeof brandSchema>;
export type ShortProps = z.infer<typeof shortSchema>;

export const TRANSITION_FRAMES = 8;

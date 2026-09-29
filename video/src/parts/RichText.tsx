import { Highlight } from "@remotion/rough-notation";
import { interpolate, useCurrentFrame } from "remotion";

/**
 * "==강조==" 구간을 형광펜으로 긋는다(startFrame 부터 18프레임).
 * 강조 뒤에 붙은 조사("기준일==부터")가 다음 줄로 떨어지지 않게 한 덩어리로 묶는다.
 */
export const RichText: React.FC<{ text: string; color: string; startFrame: number }> = ({ text, color, startFrame }) => {
  const frame = useCurrentFrame();
  const parts = text.split("==");
  const out: React.ReactNode[] = [];
  let carry = "";
  parts.forEach((p, i) => {
    if (i % 2 === 0) {
      out.push(<span key={i}>{p.slice(carry.length)}</span>);
      return;
    }
    const next = parts[i + 1] ?? "";
    carry = next.match(/^[^\s]*/)?.[0] ?? "";
    // 단어마다 따로 긋는다: 여러 줄에 걸쳐도 줄마다 형광펜이 맞게 그어짐
    const words = p.split(" ");
    words.forEach((w, j) => {
      const mark = (
        <Highlight
          color={color}
          iterations={1}
          padding={{ left: 6, right: 6, top: 2, bottom: 2 }}
          seed={7 + j}
          roughness={0.5}
          progress={interpolate(frame, [startFrame + j * 4, startFrame + j * 4 + 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })}
        >
          {w}
        </Highlight>
      );
      const last = j === words.length - 1;
      out.push(
        <span key={`${i}-${j}`} style={{ whiteSpace: "nowrap" }}>
          {mark}
          {last ? carry : null}
        </span>,
      );
      if (!last) out.push(<span key={`${i}-${j}-s`}> </span>);
    });
  });
  return <>{out}</>;
};

/** 가장 긴 어절이 안전 영역(약 840px)을 넘지 않도록 글자 크기를 줄인다 */
export const fitSize = (text: string, base: number, min = 64) => {
  const longest = Math.max(...text.replace(/==/g, "").split(" ").map((w) => [...w].length));
  return Math.max(min, Math.min(base, Math.floor(820 / Math.max(longest, 1))));
};

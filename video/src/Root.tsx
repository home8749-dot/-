import { Composition, Folder, Still } from "remotion";
import { Banner, Profile } from "./ChannelArt";
import "./fonts";
import sample from "./sample.json";
import { calculateShortMetadata, ShortVideo } from "./ShortVideo";
import { shortSchema } from "./schema";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="ShortVideo"
      component={ShortVideo}
      schema={shortSchema}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={300}
      defaultProps={sample as never}
      calculateMetadata={calculateShortMetadata}
    />
    <Folder name="ChannelArt">
      <Still id="Profile" component={Profile} width={800} height={800} defaultProps={{ brand: sample.brand }} />
      <Still
        id="Banner"
        component={Banner}
        width={2560}
        height={1440}
        defaultProps={{ brand: sample.brand, tagline: "지원사업 서류, 단디 챙기자" }}
      />
    </Folder>
  </>
);

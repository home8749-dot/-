import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// SIL OFL 폰트 (assets/fonts/README.md)
export const DISPLAY = "BlackHanSans";
export const BODY = "GothicA1";

loadFont({ family: DISPLAY, url: staticFile("fonts/BlackHanSans-Regular.ttf"), weight: "400" });
loadFont({ family: BODY, url: staticFile("fonts/GothicA1-Bold.ttf"), weight: "700" });
loadFont({ family: BODY, url: staticFile("fonts/GothicA1-ExtraBold.ttf"), weight: "800" });

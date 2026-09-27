import { Composition } from "remotion";
import { Flow, FPS, HEIGHT, TOTAL, WIDTH } from "./Flow";

export const RemotionRoot = () => {
  return (
    <Composition
      id="Flow"
      component={Flow}
      durationInFrames={TOTAL}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};

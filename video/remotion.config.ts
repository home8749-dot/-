/**
 * 단디서류 쇼츠 템플릿 렌더 설정.
 * CLI 옵션: https://remotion.dev/docs/config
 */
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

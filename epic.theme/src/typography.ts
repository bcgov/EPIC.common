import type { TypographyVariantsOptions } from "@mui/material/styles";
import { BCDesignTokens } from "./designTokens";

export const TypographyStyles: TypographyVariantsOptions = {
  fontFamily: '"BC Sans","Noto Sans",Verdana,Arial,sans-serif',
  h1: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeH1,
    lineHeight: BCDesignTokens.typographyLineHeightsXxsparse,
    color: BCDesignTokens.typographyColorPrimary,
  },
  h2: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeH2,
    lineHeight: BCDesignTokens.typographyLineHeightsXxxsparse,
    color: BCDesignTokens.typographyColorPrimary,
  },
  h3: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeH3,
    lineHeight: BCDesignTokens.typographyLineHeightsXsparse,
    color: BCDesignTokens.typographyColorPrimary,
  },
  h4: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeH4,
    lineHeight: BCDesignTokens.typographyLineHeightsSparse,
    color: BCDesignTokens.typographyColorPrimary,
  },
  h5: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeH5,
    lineHeight: BCDesignTokens.typographyLineHeightsRegular,
    color: BCDesignTokens.typographyColorPrimary,
  },
  h6: {
    fontWeight: BCDesignTokens.typographyFontWeightsBold,
    fontSize: BCDesignTokens.typographyFontSizeLargeBody,
    lineHeight: BCDesignTokens.typographyLineHeightsDense,
    color: BCDesignTokens.typographyColorPrimary,
  },
  subtitle1: {
    fontWeight: BCDesignTokens.typographyFontWeightsRegular,
    fontSize: BCDesignTokens.typographyFontSizeLargeBody,
    lineHeight: BCDesignTokens.typographyLineHeightsDense,
    color: BCDesignTokens.typographyColorPrimary,
  },
  body1: {
    fontWeight: BCDesignTokens.typographyFontWeightsRegular,
    fontSize: BCDesignTokens.typographyFontSizeBody,
    lineHeight: BCDesignTokens.typographyLineHeightsXdense,
    color: BCDesignTokens.typographyColorSecondary,
  },
  body2: {
    fontWeight: BCDesignTokens.typographyFontWeightsRegular,
    fontSize: BCDesignTokens.typographyFontSizeSmallBody,
    lineHeight: BCDesignTokens.typographyLineHeightsXxdense,
    color: BCDesignTokens.typographyColorSecondary,
  },
  caption: {
    fontWeight: BCDesignTokens.typographyFontWeightsRegular,
    fontSize: BCDesignTokens.typographyFontSizeLabel,
    lineHeight: BCDesignTokens.typographyLineHeightsXxxdense,
    color: BCDesignTokens.typographyColorSecondary,
  },
  button: {
    fontWeight: BCDesignTokens.typographyFontWeightsRegular,
    fontSize: BCDesignTokens.typographyFontSizeBody,
    lineHeight: "1.5rem",
    textTransform: "none",
  },
};

export default TypographyStyles;

// The colours of the heatmap for every eye: the accessible scale gets lighter with the hits,
// so it also reads in grey, and its steps stay apart under a simulated colour vision deficiency.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, loadCards, makeHass, mount } from "./dom.mjs";

const { STYLES, doubleColor, heatColor, heatFill } = await loadCards();

// The 33 steps of the table of the card.
const STEPS = Array.from({ length: 33 }, (_, index) => index / 32);
// The stops of the legend of the training and the doubles card.
const LEGEND = [0, 0.25, 0.5, 0.75, 1];
// The board looks the same on every theme; the legend and the bars lie on the card of the theme.
const THEMES = {
  light: { background: "#ffffff", text: "#212121" },
  dark: { background: "#1c1c1c", text: "#e1e1e1" },
};
// How far apart two colours must be, as 100 times their distance in OKLab; people tell
// apart a distance of about 2 when the colours touch.
const CLEARLY_APART = 8;

// Colour science ----------------------------------------------------------------

const toLinear = (channel) => (channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
const toGamma = (channel) => (channel <= 0.0031308 ? 12.92 * channel : 1.055 * channel ** (1 / 2.4) - 0.055);
const clamp = (value) => Math.min(1, Math.max(0, value));

const linearRgb = (hex) => [1, 3, 5].map((start) => toLinear(parseInt(hex.slice(start, start + 2), 16) / 255));
const hexOf = (rgb) => `#${rgb.map((channel) => Math.round(toGamma(clamp(channel)) * 255).toString(16).padStart(2, "0")).join("")}`;

// OKLab by Björn Ottosson, https://bottosson.github.io/posts/oklab/
function oklab([r, g, b]) {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function oklch(lightness, chroma, hue) {
  const a = chroma * Math.cos((hue * Math.PI) / 180);
  const b = chroma * Math.sin((hue * Math.PI) / 180);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

const apart = (first, second) => {
  const [a, b] = [oklab(first), oklab(second)];
  return 100 * Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
};

// Colour vision deficiencies at full severity, after Machado, Oliveira and Fernandes (2009),
// for linear RGB.
const VISIONS = {
  normal: [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};
const seenWith = (matrix, rgb) => matrix.map(([r, g, b]) => clamp(r * rgb[0] + g * rgb[1] + b * rgb[2]));

const luminance = ([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
const contrast = (first, second) => {
  const [a, b] = [luminance(first), luminance(second)];
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
};
// A colour over another, as a browser mixes them: in sRGB, not in linear light.
const mix = (top, share, below) => top.map((channel, index) => toLinear(toGamma(channel) * share + toGamma(below[index]) * (1 - share)));

// HSL with the numbers of the thermal palette.
function hslRgb(hue, saturation, lightness) {
  const channel = (n) => {
    const k = (n + hue / 30) % 12;
    return toLinear(lightness - saturation * Math.min(lightness, 1 - lightness) * Math.max(-1, Math.min(k - 3, 9 - k, 1)));
  };
  return [channel(0), channel(8), channel(4)];
}

const scale = (ratio) => linearRgb(heatColor(ratio));
const minStep = (colors, matrix) => Math.min(...colors.slice(1).map((color, index) => apart(seenWith(matrix, color), seenWith(matrix, colors[index]))));
const fillOf = (ratio, palette, kind) => {
  const [, color, opacity] = /fill="([^"]+)" fill-opacity="([^"]+)"/.exec(heatFill(ratio, palette, kind));
  return { color, opacity: Number(opacity) };
};

// The scale ---------------------------------------------------------------------

test("the table of the accessible scale is its stops, interpolated in OKLCH", () => {
  // Lightness, chroma and hue; every step between them stays inside sRGB.
  const stops = [
    [0.48, 0.18, 285],
    [0.585, 0.105, 240],
    [0.69, 0.105, 180],
    [0.795, 0.17, 140],
    [0.9, 0.185, 105],
  ];
  const expected = STEPS.map((ratio) => {
    const place = ratio * (stops.length - 1);
    const stop = Math.min(stops.length - 2, Math.floor(place));
    const share = place - stop;
    const between = stops[stop].map((value, index) => value + (stops[stop + 1][index] - value) * share);
    const rgb = oklch(...between);
    assert.ok(rgb.every((channel) => channel >= -1e-3 && channel <= 1 + 1e-3), `${ratio} leaves sRGB: ${rgb}`);
    return hexOf(rgb);
  });
  assert.deepEqual(STEPS.map((ratio) => heatColor(ratio)), expected);
});

test("the accessible scale gets lighter with every step, also in grey", () => {
  const colors = STEPS.map(scale);
  for (const [index, color] of colors.entries()) {
    if (!index) continue;
    assert.ok(oklab(color)[0] > oklab(colors[index - 1])[0], `the lightness falls at step ${index}`);
    assert.ok(luminance(color) > luminance(colors[index - 1]), `the grey falls at step ${index}`);
  }
  // Grey, as a printout or a monochrome display shows it: every stop of the legend differs.
  const greys = LEGEND.map((ratio) => {
    const grey = luminance(scale(ratio));
    return [grey, grey, grey];
  });
  assert.ok(minStep(greys, VISIONS.normal) > CLEARLY_APART);
});

test("the stops of the legend stay apart for every eye", () => {
  const colors = LEGEND.map(scale);
  for (const [vision, matrix] of Object.entries(VISIONS)) {
    assert.ok(minStep(colors, matrix) > CLEARLY_APART, `${vision}: ${minStep(colors, matrix)}`);
  }
});

test("the former rainbow is what the accessible scale fixes", () => {
  // Red and yellow at the top of the thermal scale differ less in deuteranopia than any
  // stops of the accessible scale, and its grey goes up and down.
  const thermal = [220, 165, 110, 55, 0].map((hue) => hslRgb(hue, 0.9, 0.55));
  assert.ok(minStep(thermal, VISIONS.deuteranopia) < minStep(LEGEND.map(scale), VISIONS.deuteranopia));
  const greys = thermal.map(luminance);
  assert.ok(greys[1] > greys[4], "its middle is lighter than its most hit colour");
});

test("the thermal palette reproduces the former colours", () => {
  for (const ratio of STEPS) {
    assert.equal(heatColor(ratio, "thermal"), `hsl(${Math.round(220 * (1 - ratio))}, 90%, 55%)`);
    // Beds, dart positions and the aim map, each with its former share of the board.
    assert.equal(fillOf(ratio, "thermal", "beds").opacity, Number((0.6 + 0.35 * ratio).toFixed(2)));
    assert.equal(fillOf(ratio, "thermal", "positions").opacity, Number((0.3 + 0.6 * ratio).toFixed(2)));
    assert.equal(fillOf(ratio, "thermal", "aim").opacity, Number((0.35 + 0.55 * ratio).toFixed(2)));
  }
  assert.equal(doubleColor(25, "thermal"), "hsl(65 70% 46%)");
});

// On the board and the themes -----------------------------------------------------

test("the rarely and the most hit stand out on every bed of every board", () => {
  // Yellow on the cream beds asks for a sense of blue, which tritanopia, by far the rarest
  // deficiency, lacks; the dark line around a bed still sets it apart there.
  const visions = Object.entries(VISIONS).filter(([vision]) => vision !== "tritanopia");
  for (const [style, board] of Object.entries(STYLES)) {
    const beds = [board.black, board.white, board.red, board.green].map(linearRgb);
    for (const [vision, matrix] of visions) {
      for (const bed of beds) {
        for (const [kind, ratio] of [
          ["beds", 0],
          ["beds", 1],
          ["positions", 0],
          ["aim", 0],
        ]) {
          const { color, opacity } = fillOf(ratio, undefined, kind);
          const painted = mix(linearRgb(color), opacity, bed);
          const found = apart(seenWith(matrix, painted), seenWith(matrix, bed));
          assert.ok(found > CLEARLY_APART, `${style}, ${vision}, ${kind} at ${ratio}: ${found}`);
        }
      }
    }
  }
});

test("little of the board shines through a bed, so its lightness tells the hits", () => {
  // The same count looks about the same on the darkest and on the lightest bed.
  const lightness = (ratio, bed) => {
    const { color, opacity } = fillOf(ratio, undefined, "beds");
    return oklab(mix(linearRgb(color), opacity, linearRgb(bed)))[0];
  };
  for (const ratio of LEGEND) {
    assert.ok(Math.abs(lightness(ratio, STYLES.flat.white) - lightness(ratio, STYLES.classic.black)) < 0.1);
  }
  // Every stop is lighter than the one before, on a dark bed and on a light one.
  for (const bed of [STYLES.muted.black, STYLES.classic.black, STYLES.classic.white, STYLES.flat.white]) {
    const steps = LEGEND.map((ratio) => lightness(ratio, bed));
    assert.deepEqual([...steps].sort((a, b) => a - b), steps, `on ${bed}`);
  }
});

test("the outline keeps the whole scale visible on a light and a dark theme", () => {
  const training = mount("homedarts-training-card", makeHass({ states: {} }), {});
  const style = $(training, "style").textContent;
  for (const selector of [/\.legend-bar \{[^}]*/, /\.top-row \.fill \{[^}]*/]) {
    assert.match(selector.exec(style)[0], /inset 0 0 0 1px color-mix\(in srgb, var\(--primary-text-color\) 45%, transparent\)/);
  }
  for (const { background, text } of Object.values(THEMES)) {
    for (const ratio of STEPS) {
      const outline = mix(linearRgb(text), 0.45, scale(ratio));
      const found = contrast(outline, linearRgb(background));
      // WCAG 1.4.11 asks for 3:1 for what tells the value of a graphic.
      assert.ok(found >= 3, `${background} at ${ratio}: ${found}`);
    }
  }
});

test("the label of a double stays readable in every colour of the scale", () => {
  const doubles = mount("homedarts-doubles-card", makeHass({ states: {} }), {});
  assert.match($(doubles, "style").textContent, /\.double \.bed \{[^}]*color: color-mix\(in srgb, var\(--c\) 30%, var\(--primary-text-color, #212121\)\)/);
  for (const { background, text } of Object.values(THEMES)) {
    for (const ratio of STEPS) {
      const label = mix(scale(ratio), 0.3, linearRgb(text));
      const card = linearRgb(background);
      // WCAG 1.4.3 for small text, also on the tint of the favourite double.
      assert.ok(contrast(label, card) >= 4.5, `${background} at ${ratio}`);
      assert.ok(contrast(label, mix(scale(ratio), 0.2, card)) >= 4.5, `favourite on ${background} at ${ratio}`);
    }
  }
});
